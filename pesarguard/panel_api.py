from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import hashlib
import re
import requests
from pesarguard.bootstrap import bot_log
from pesarguard.config import PANEL_RELAY_KEY, PANEL_RELAY_URL, PANEL_VERIFY_SSL
from pesarguard.constants import CHROME_UA, ROLE_LABELS
from pesarguard.crypto import panel_decrypt_pw
from pesarguard.database import get_panels, get_setting
from pesarguard.utils import strong_password


_PSESS = {"s": None}

_TOKENS: dict = {}

def _psession():
    if _PSESS["s"] is None:
        try:
            from curl_cffi import requests as creq

            _PSESS["s"] = creq.Session(impersonate="chrome")
        except Exception:
            s = requests.Session()
            s.headers.update({"User-Agent": CHROME_UA})
            _PSESS["s"] = s
    return _PSESS["s"]

def panel_clean_base_url(url: str) -> str:
    for frag in ("/dashboard/", "/dashboard"):
        if url.endswith(frag):
            url = url[: -len(frag)]
    url = url.rstrip("/")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    return url

def panel_login_url(stored_base: str) -> str:
    return stored_base.rstrip("/") + "/dashboard"

def panel_client(base_url: str | None = None, ptype: str | None = None) -> dict | None:
    panels = get_panels()
    if not panels:
        return None
    data = None
    if base_url is not None:
        for pn, d in panels.items():
            if d.get("base_url") == base_url or pn == base_url:
                data = d
                break
    else:
        sel = str(get_setting("selected_panel", "") or "")
        if sel and sel in panels:
            data = panels[sel]
    if data is None:
        for d in panels.values():
            if d.get("active"):
                data = d
                break
        if data is None:
            data = next(iter(panels.values()))
    data = dict(data)
    if ptype:
        data["ptype"] = ptype
    data["ptype"] = data.get("ptype") or "pasarguard"
    data["password"] = panel_decrypt_pw(data.get("password", ""))
    data["base_url"] = str(data.get("base_url", "")).rstrip("/")
    return data

def _preq(p: dict, method: str, path: str, token: str | None = None, **kw):
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    return _psession().request(
        method, p["base_url"].rstrip("/") + path, headers=headers, timeout=25, verify=PANEL_VERIFY_SSL, **kw
    )

def _login_paths(ptype: str) -> list[str]:
    if ptype == "sanaei":
        return ["/api/admin/token", "/api/admins/token", "/login"]
    if ptype == "pasarguard":
        return ["/api/admin/token", "/api/admins/token", "/api/admins/login"]
    return ["/api/admin/token", "/login"]

def _panel_auth(p: dict, force: bool = False) -> str | None:
    plain_pw = panel_decrypt_pw(p.get("password", "")) or p.get("password", "")
    ck = (p["base_url"], p.get("username", ""), hashlib.sha1(plain_pw.encode()).hexdigest())
    if not force and ck in _TOKENS:
        return _TOKENS[ck]
    for pth in _login_paths(p.get("ptype", "pasarguard")):
        try:
            r = _preq(p, "POST", pth, data={"username": p.get("username", ""), "password": plain_pw})
            if r.status_code == 200:
                j = r.json()
                tok = j.get("access_token") or j.get("token") or (j.get("data") or {}).get("token")
                if tok:
                    _TOKENS[ck] = tok
                    return tok
        except Exception:
            continue
    _TOKENS.pop(ck, None)
    return None

def _preq_auth(p: dict, method: str, path: str, **kw):
    tok = _panel_auth(p)
    if not tok:
        raise RuntimeError("auth failed")
    r = _preq(p, method, path, token=tok, **kw)
    if r.status_code == 401:
        tok = _panel_auth(p, force=True)
        if not tok:
            raise RuntimeError("re-login failed")
        r = _preq(p, method, path, token=tok, **kw)
    return r

def _json_or(r, default=None):
    try:
        return r.json()
    except Exception:
        return default

def _list_admins_raw(p: dict) -> list:
    for pth in ("/api/admins", "/api/admin/users"):
        try:
            r = _preq_auth(p, "GET", pth)
        except Exception:
            continue
        if r.status_code == 200:
            j = _json_or(r)
            if isinstance(j, list):
                return j
            if isinstance(j, dict):
                for k in ("admins", "items", "data"):
                    if k in j and isinstance(j[k], list):
                        return j[k]
    return []

def _try_modify(p: dict, uname: str, body: dict, methods=("PUT", "PATCH", "POST")) -> tuple[bool, str]:
    last_err = "ارتباط با پنل برقرار نشد."
    for pth in (f"/api/admin/{uname}", f"/api/admins/{uname}"):
        for m in methods:
            try:
                r = _preq_auth(p, m, pth, json=body)
                if r.status_code in (200, 204, 201):
                    return True, ""
                else:
                    j = _json_or(r, {})
                    if isinstance(j, dict):
                        last_err = str(j.get("detail") or j.get("message") or j.get("error") or r.text[:100])
                    else:
                        last_err = f"خطای {r.status_code}: {r.text[:100]}"
            except Exception as e:
                last_err = str(e)
                continue
    return False, last_err

def _panel_call_direct(p: dict, action: str, args: dict) -> dict:
    try:
        tok = _panel_auth(p)
    except Exception:
        tok = None
    if not tok:
        return {"ok": False, "error": "auth failed"}
    ptype = p.get("ptype", "pasarguard")

    if action == "ping":
        ver = ""
        try:
            r = _preq_auth(p, "GET", "/api/admin/system")
            if r.status_code == 200:
                ver = str((_json_or(r, {}) or {}).get("version", ""))
                return {"ok": True, "msg": f"{ptype} OK {ver}".strip()}
        except Exception:
            pass
        return {"ok": True, "msg": f"{ptype} auth-ok"}

    if action == "list_roles":
        for pth in ("/api/admin-roles/simple", "/api/admin-roles"):
            try:
                r = _preq_auth(p, "GET", pth)
            except Exception:
                continue
            if r.status_code == 200:
                j = _json_or(r)
                roles = j.get("roles") if isinstance(j, dict) else j
                if isinstance(roles, list) and roles:
                    out = [
                        {"id": int(x["id"]), "name": str(x.get("name") or f"role {x['id']}"), "is_owner": bool(x.get("is_owner"))}
                        for x in roles
                        if isinstance(x, dict) and "id" in x
                    ]
                    return {"ok": True, "roles": out}
        return {"ok": True, "roles": []}

    if action == "list_admins":
        return {"ok": True, "data": _list_admins_raw(p)}

    if action == "get_admin_info":
        uname = args.get("username", "")
        for a in _list_admins_raw(p):
            if a.get("username") == uname:
                return {"ok": True, "data": a}
        return {"ok": True, "data": None}

    if action == "delete_admin":
        u = args.get("username", "")
        for pth in (f"/api/admin/{u}", f"/api/admins/{u}"):
            try:
                r = _preq_auth(p, "DELETE", pth)
                if r.status_code < 400:
                    return {"ok": True}
            except Exception:
                continue
        return {"ok": False}

    if action == "modify_admin_data_limit":
        ok, err = _try_modify(p, args.get("username", ""), {"data_limit": int(args.get("data_limit", 0))})
        return {"ok": ok, "error": err if not ok else None}

    if action == "modify_admin_status":
        ok, err = _try_modify(p, args.get("username", ""), {"status": args.get("status", "active")})
        return {"ok": ok, "error": err if not ok else None}

    if action == "modify_admin_password":
        ok, err = _try_modify(p, args.get("username", ""), {"password": args.get("password", "")}, methods=("PUT", "PATCH"))
        return {"ok": ok, "error": err if not ok else None}

    if action == "create_admin":
        pw = args.get("password", "")
        body = {
            "username": args.get("username", ""),
            "password": pw,
            "data_limit": int(round(float(args.get("volume_gb", 0)) * 1024 ** 3)) or int(args.get("data_limit", 0)),
        }
        if ptype == "pasarguard":
            if len(pw) < 12 or not any(c in "!@#$%^&*" for c in pw):
                body["password"] = strong_password()
            body["role_id"] = int(args.get("role_id") or p.get("role_id") or 3)
            # Remove telegram_id from PasarGuard admin creation to avoid 409 conflicts
            # if user/admin is already present on the panel.
            paths = ["/api/admin"]
        else:
            if args.get("telegram_id"):
                body["telegram_id"] = int(args["telegram_id"])
            paths = ["/api/admin/user", "/api/admins"]
        last = "create failed"
        for pth in paths:
            try:
                r = _preq_auth(p, "POST", pth, json=body)
            except Exception as e:
                last = str(e)[:150]
                continue

            if r.status_code in (200, 201):
                res = _json_or(r, {}) or {}
                if isinstance(res, dict):
                    res["password_used"] = body["password"]
                return {"ok": True, "data": res}
            last = f"{pth}: {r.status_code} {(r.text or '')[:100]}"
        return {"ok": False, "error": last}

    if action == "stats":
        sysj = {}
        try:
            r = _preq_auth(p, "GET", "/api/admin/system")
            if r.status_code == 200:
                sysj = _json_or(r, {}) or {}
        except Exception:
            pass
        gb = 1024 ** 3
        tb = 1024 ** 4
        return {
            "ok": True,
            "admins_count": len(_list_admins_raw(p)),
            "version": sysj.get("version", "—"),
            "ram_total_gb": round(float(sysj.get("mem_total", 0)) / gb, 1) if sysj.get("mem_total") else "—",
            "ram_used_gb": round(float(sysj.get("mem_used", 0)) / gb, 1) if sysj.get("mem_used") else "—",
            "traffic_tb": round(
                (float(sysj.get("incoming_bandwidth", 0)) + float(sysj.get("outgoing_bandwidth", 0))) / tb, 2
            ) if (sysj.get("incoming_bandwidth") or sysj.get("outgoing_bandwidth")) else "—",
        }

    return {"ok": False, "error": f"unsupported action: {action}"}

def panel_call(panel: dict, action: str, args: dict | None = None) -> dict | None:
    args = args or {}
    res: dict | None = None
    try:
        res = _panel_call_direct(panel, action, args)
        if res and res.get("ok"):
            return res
    except Exception as e:
        bot_log(f"panel direct error {action}: {e}")
    relay_url, relay_key = PANEL_RELAY_URL, PANEL_RELAY_KEY
    if relay_url and relay_key:
        try:
            r = requests.post(
                relay_url.rstrip("/") + "/relay",
                json={
                    "key": relay_key,
                    "base_url": panel.get("base_url", ""),
                    "username": panel.get("username", ""),
                    "password": panel.get("password", ""),
                    "ptype": panel.get("ptype", "pasarguard"),
                    "action": action,
                    "args": {**args, "role_id": args.get("role_id") or panel.get("role_id") or 3},
                },
                timeout=45,
                verify=PANEL_VERIFY_SSL,
            )
            jr = r.json()
            if isinstance(jr, dict):
                return jr
        except Exception as e:
            bot_log(f"panel relay error {action}: {e}")
    return res

def panel_ping(panel: dict) -> dict:
    return panel_call(panel, "ping", {}) or {"ok": False, "msg": "Bridge error"}

def panel_create_admin(p: dict, uname: str, pwd: str, vol_gb: float, tg_id: int) -> dict:
    res = panel_call(p, "create_admin", {"username": uname, "password": pwd, "volume_gb": vol_gb, "telegram_id": tg_id})
    return res if isinstance(res, dict) else {"ok": False, "error": "bridge no response"}

def get_panel_role_label(panel: dict, role_id: int) -> str:
    try:
        tok = _panel_auth(panel)
        if tok:
            r = _preq(panel, 'GET', '/api/admin-roles/simple', token=tok)
            if r.status_code == 200:
                for role in r.json().get('roles', []):
                    if role.get('id') == role_id:
                        return f"🛡 {role.get('name')}"
    except Exception:
        pass
    return ROLE_LABELS.get(role_id, f"نقش {role_id}")
