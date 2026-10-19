import os, re, json, time, requests, hashlib, base64, secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from modules.config import PANEL_CRYPTO_KEY, PANEL_RELAY_URL, PANEL_RELAY_KEY, PANEL_VERIFY_SSL, BASE_DIR, bot_log
from modules.utils import panel_decrypt_pw, panel_encrypt_pw, strong_password


def panel_crypto_key() -> str:
    k = PANEL_CRYPTO_KEY
    if k:
        return k
    kf = os.path.join(BASE_DIR, "data", "crypto.key")
    if os.path.isfile(kf):
        return open(kf).read().strip()
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    with open(kf, "w") as f:
        f.write(key)
    try:
        os.chmod(kf, 0o600)
    except Exception:
        pass
    return key

def panel_encrypt_pw(plain: str) -> str:
    if not plain:
        return ""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = base64.b64decode(panel_crypto_key())
    iv = secrets.token_bytes(12)
    ct_tag = AESGCM(key).encrypt(iv, plain.encode(), None)
    ct, tag = ct_tag[:-16], ct_tag[-16:]
    return "phpenc2:" + base64.b64encode(iv + tag + ct).decode()

def panel_decrypt_pw(enc: str) -> str:
    if not enc:
        return ""
    try:
        if enc.startswith("phpenc2:"):
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            raw = base64.b64decode(enc[8:])
            if len(raw) < 28:
                return ""
            iv, tag, ct = raw[:12], raw[12:28], raw[28:]
            return AESGCM(base64.b64decode(panel_crypto_key())).decrypt(iv, ct + tag, None).decode()
        if enc.startswith("phpenc:"):
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            raw = base64.b64decode(enc[7:])
            if len(raw) < 16:
                return ""
            c = Cipher(algorithms.AES(base64.b64decode(panel_crypto_key())), modes.CBC(raw[:16])).decryptor()
            padded = c.update(raw[16:]) + c.finalize()
            un = padding.PKCS7(128).unpadder()
            return (un.update(padded) + un.finalize()).decode()
        if enc.startswith("pyfer:"):
            return enc[6:]
        if enc.startswith("gAAAA"):
            from cryptography.fernet import Fernet

            key = panel_crypto_key()
            key = key + "=" * (-len(key) % 4)
            return Fernet(key.encode()).decrypt(enc.encode()).decode()
    except Exception as e:
        bot_log(f"decrypt failed: {e}")
        return ""
    return enc

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
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
            if args.get("telegram_id"):
                body["telegram_id"] = int(args["telegram_id"])
            paths = ["/api/admin", "/api/admins/user"]
        else:
