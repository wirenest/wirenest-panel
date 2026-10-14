"""Panel client with Cloudflare bypass via curl_cffi (browser-TLS impersonation).

Drop-in replacement for panel.py's transport: same Panel API surface, but all
HTTP goes through curl_cffi with chrome impersonation, which passes Cloudflare
managed challenges that block plain httpx.
"""
import datetime
import asyncio
from curl_cffi import requests as creq


class PanelError(Exception):
    pass


_SHARED_SESS = None


def _shared_session():
    """One curl_cffi session for all Panel instances (avoids per-object leaks)."""
    global _SHARED_SESS
    if _SHARED_SESS is None:
        _SHARED_SESS = creq.Session(impersonate="chrome")
    return _SHARED_SESS


class Panel:
    """Unified panel client. type in {marzban, pasarguard, sanaei}."""

    def __init__(self, base_url: str, username: str, password: str,
                 ptype: str = "marzban", role_id: int = 3):
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.ptype = (ptype or "marzban").lower()
        self.role_id = role_id
        self._token: str | None = None
        self._sess = _shared_session()

    # ---------------- auth ----------------
    def _login_paths(self):
        if self.ptype == "sanaei":
            return ["/api/admin/token", "/api/admins/token", "/login"]
        if self.ptype == "pasarguard":
            return ["/api/admin/token", "/api/admins/token", "/api/admins/login"]
        return ["/api/admin/token", "/login"]

    async def _auth(self, client=None):
        last_err = None
        for path in self._login_paths():
            try:
                r = await asyncio.to_thread(
                    self._sess.post,
                    f"{self.base_url}{path}",
                    data={"username": self.username, "password": self.password},
                    headers={"Accept": "application/json"},
                    timeout=25,
                )
                if r.status_code == 200:
                    j = r.json()
                    tok = j.get("access_token") or j.get("token") or (j.get("data") or {}).get("token")
                    if tok:
                        self._token = tok
                        return
                last_err = f"{path}: {r.status_code}"
            except Exception as e:
                last_err = f"{path}: {str(e)[:60]}"
        raise PanelError(f"login failed ({self.ptype}): {last_err}")

    def _req_sync(self, method: str, path: str, **kw):
        """Synchronous request via curl_cffi session, with re-login on 401."""
        headers = kw.pop("headers", {}) or {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        r = self._sess.request(method, f"{self.base_url}{path}",
                               headers=headers, timeout=30, **kw)
        if r.status_code == 401:
            self._token = None
            # re-auth once
            self._reauth_sync()
            headers["Authorization"] = f"Bearer {self._token}"
            r = self._sess.request(method, f"{self.base_url}{path}",
                                   headers=headers, timeout=30, **kw)
        if r.status_code >= 400 and r.status_code not in (404,):
            body = (r.text or "")[:120]
            if "just a moment" in body.lower():
                raise PanelError(f"{path}: Cloudflare blocked ({r.status_code})")
        return r

    def _reauth_sync(self):
        # runs inside asyncio.to_thread (called from async _req retry path)
        last_err = None
        for path in self._login_paths():
            try:
                r = self._sess.post(
                    f"{self.base_url}{path}",
                    data={"username": self.username, "password": self.password},
                    headers={"Accept": "application/json"}, timeout=25)
                if r.status_code == 200:
                    j = r.json()
                    tok = j.get("access_token") or j.get("token") or (j.get("data") or {}).get("token")
                    if tok:
                        self._token = tok
                        return
                last_err = f"{path}: {r.status_code}"
            except Exception as e:
                last_err = str(e)[:60]
        raise PanelError(f"re-login failed: {last_err}")

    async def _req(self, method: str, path: str, **kw):
        """Async wrapper — curl_cffi is sync; run in default executor via asyncio.to_thread."""
        import asyncio
        return await asyncio.to_thread(self._req_sync, method, path, **kw)

    # ---------------- compat helpers ----------------
    def _user_path(self, username: str) -> str:
        if self.ptype in ("sanaei",):
            return f"/api/admins/user/{username}"
        return f"/api/admin/user/{username}"

    # ---------------- system ----------------
    async def system_stats(self) -> dict:
        for path in ("/api/admin/system", "/api/admins/system", "/api/system"):
            try:
                r = await self._req("GET", path)
                if r.status_code == 200:
                    return r.json()
            except PanelError:
                continue
        return {}

    async def users_count(self) -> int:
        s = await self.system_stats()
        return s.get("total_user") or s.get("users_count") or 0

    # ---------------- users ----------------
    async def create_user(self, username: str, data_limit_gb: float, months: int,
                          proxies: dict | None = None, note: str = "") -> dict:
        expire = int((datetime.datetime.now() + datetime.timedelta(days=30 * months)).timestamp())
        body = {
            "username": username,
            "proxies": proxies or {"vless": {}, "vmess": {}},
            "expire": expire,
            "data_limit": int(data_limit_gb * (1024 ** 3)),
            "data_limit_reset_strategy": "no_reset",
            "note": note,
        }
        path = "/api/admins/user" if self.ptype == "sanaei" else "/api/admin/user"
        r = await self._req("POST", path, json=body)
        if r.status_code >= 400:
            raise PanelError(f"create_user: {r.status_code} {(r.text or '')[:100]}")
        return r.json()

    async def get_user(self, username: str) -> dict | None:
        r = await self._req("GET", self._user_path(username))
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise PanelError(f"get_user: {r.status_code}")
        return r.json()

    async def modify_user(self, username: str, **fields) -> dict:
        r = await self._req("PUT", self._user_path(username), json=fields)
        if r.status_code >= 400:
            raise PanelError(f"modify_user: {r.status_code} {(r.text or '')[:100]}")
        return r.json()

    async def delete_user(self, username: str) -> None:
        try:
            await self._req("DELETE", self._user_path(username))
        except PanelError:
            pass

    # ---------------- admins (limited panel creation) ----------------

    async def list_roles(self) -> list[dict]:
        """Live role list from the panel (id/name/is_owner). Falls back to [] if unsupported."""
        for path in ("/api/admin-roles/simple", "/api/admin-roles"):
            try:
                r = await self._req("GET", path)
                if r.status_code != 200:
                    continue
                j = r.json()
                roles = j.get("roles") if isinstance(j, dict) else j
                if isinstance(roles, list) and roles:
                    out = []
                    for x in roles:
                        if not isinstance(x, dict) or "id" not in x:
                            continue
                        out.append({"id": int(x["id"]),
                                    "name": str(x.get("name") or f"role {x['id']}"),
                                    "is_owner": bool(x.get("is_owner"))})
                    if out:
                        return out
            except PanelError:
                continue
        return []

    async def modify_admin_role(self, username: str, role_id: int) -> bool:
        """Change an existing admin's role (PasarGuard: PUT /api/admin/{username})."""
        body = {"role_id": role_id}
        for method, path in (("PUT", f"/api/admin/{username}"),
                             ("PATCH", f"/api/admin/{username}"),
                             ("PUT", f"/api/admins/{username}")):
            try:
                r = await self._req(method, path, json=body)
                if r.status_code in (200, 204):
                    return True
            except PanelError:
                continue
        return False

    async def delete_admin(self, username: str) -> None:
        try:
            await self._req("DELETE", f"/api/admin/{username}")
        except PanelError:
            try:
                await self._req("DELETE", f"/api/admins/{username}")
            except PanelError:
                pass

    @staticmethod
    def strong_password() -> str:
        """PasarGuard policy: >=12 chars, 2+ uppercase, digits, special char."""
        import secrets
        U = "ABCDEFGHJKLMNPQRSTUVWXYZ"
        L = "abcdefghijkmnpqrstuvwxyz"
        D = "23456789"
        S = "!@#$%^&*"
        pw = [secrets.choice(U), secrets.choice(U), secrets.choice(L),
              secrets.choice(L), secrets.choice(D), secrets.choice(D),
              secrets.choice(S)]
        pw += [secrets.choice(U + L + D + S) for _ in range(6)]
        secrets.SystemRandom().shuffle(pw)
        return "".join(pw)

    async def create_admin(self, username: str, password: str, data_limit_gb: float,
                           role_id: int | None = None,
                           telegram_id: int | str | None = None) -> dict:
        """Create a limited admin with data quota (no expiry).

        Marzban:    POST /api/admin/user (weak pw ok)
        PasarGuard: POST /api/admin with role_id (3=operator, 5=CDN, 2=owner) + strong password
                    + telegram_id (buyer's TG numeric id, shown in panel profile/contacts)
        """
        body = {
            "username": username,
            "password": password,
            "data_limit": int(data_limit_gb * (1024 ** 3)),
        }
        last = None
        if self.ptype == "pasarguard":
            body["role_id"] = role_id if role_id is not None else self.role_id
            if telegram_id:
                body["telegram_id"] = int(telegram_id)
            if len(password) < 12 or not any(c in "!@#$%^&*" for c in password):
                body["password"] = self.strong_password()
            try:
                r = await self._req("POST", "/api/admin", json=body)
                if r.status_code in (200, 201):
                    res = r.json()
                    if isinstance(res, dict):
                        res["password_used"] = body["password"]
                    return res
                last = PanelError(f"/api/admin: {r.status_code} {(r.text or '')[:150]}")
            except PanelError as e:
                last = e
            # fallback: older pasarguard builds used /api/admins/user
            try:
                r = await self._req("POST", "/api/admins/user", json=body)
                if r.status_code in (200, 201):
                    res = r.json()
                    if isinstance(res, dict):
                        res["password_used"] = body["password"]
                    return res
                last = PanelError(f"/api/admins/user: {r.status_code} {(r.text or '')[:150]}")
            except PanelError as e:
                last = e
            return _raise(last)
        for pth in ("/api/admin/user", "/api/admins"):
            try:
                r = await self._req("POST", pth, json=body)
                if r.status_code in (200, 201):
                    res = r.json()
                    if isinstance(res, dict):
                        res["password_used"] = body["password"]
                    return res
                last = PanelError(f"{pth}: {r.status_code} {(r.text or '')[:100]}")
            except PanelError as e:
                last = e
        return _raise(last)


    async def list_admins(self) -> list:
        for pth in ("/api/admins", "/api/admin/users"):
            try:
                r = await self._req("GET", pth)
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, list):
                        return j
                    if isinstance(j, dict):
                        for k in ("admins", "items", "data"):
                            if k in j:
                                return j[k]
            except PanelError:
                continue
        return []

    async def my_usage(self) -> dict:
        """Usage stats for this admin account (if panel supports)."""
        for pth in ("/api/admins/me", "/api/admin/me"):
            try:
                r = await self._req("GET", pth)
                if r.status_code == 200:
                    return r.json()
            except PanelError:
                continue
        return {}

    # ---------------- diagnostics ----------------
    async def ping(self) -> str:
        await self._auth()
        try:
            s = await self.system_stats()
            ver = s.get("version") or ""
            return f"{self.ptype} OK {ver}".strip()
        except Exception:
            return f"{self.ptype} auth-ok"


async def detect_panel(base_url: str, username: str, password: str) -> Panel:
    """Try supported panel types; return the first that logs in. Sanaei unsupported."""
    errors = []
    for ptype in ("marzban", "pasarguard"):
        p = Panel(base_url, username, password, ptype)
        try:
            await p._auth()
            return p
        except PanelError as e:
            errors.append(f"{ptype}: {e}")
    raise PanelError(" | ".join(errors))


def _raise(err):
    raise err or PanelError("create_admin failed")
