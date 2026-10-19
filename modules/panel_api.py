import json
import base64
import requests
from urllib.parse import urlparse
from modules.config import PANEL_CRYPTO_KEY, PANEL_VERIFY_SSL, log_event

def panel_log(msg: str, level: str = "INFO"):
    log_event("panel_api", msg, level=level)

def panel_crypto_key() -> str:
    return PANEL_CRYPTO_KEY or "default_secret_key_32bytes_length!!"

def panel_encrypt_pw(plain: str) -> str:
    try:
        k = panel_crypto_key().encode()
        p = plain.encode()
        out = bytes([b ^ k[i % len(k)] for i, b in enumerate(p)])
        return base64.b64encode(out).decode()
    except Exception:
        return plain

def panel_decrypt_pw(enc: str) -> str:
    try:
        k = panel_crypto_key().encode()
        data = base64.b64decode(enc.encode())
        out = bytes([b ^ k[i % len(k)] for i, b in enumerate(data)])
        return out.decode()
    except Exception:
        return enc

def panel_clean_base_url(url: str) -> str:
    url = str(url or "").strip().rstrip("/")
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url

def _login_paths(ptype: str) -> list[str]:
    return ["/api/admin/token", "/api/token", "/api/v1/token"]

def _panel_auth(p: dict, force: bool = False) -> str | None:
    base = panel_clean_base_url(p.get("base_url", ""))
    uname = p.get("username", "")
    pwd = panel_decrypt_pw(p.get("password_enc", ""))
    
    sess = requests.Session()
    sess.verify = PANEL_VERIFY_SSL
    
    for path in _login_paths(p.get("type", "pasarguard")):
        try:
            res = sess.post(
                base + path,
                data={"username": uname, "password": pwd},
                timeout=10
            )
            if res.status_code == 200:
                data = res.json()
                tok = data.get("access_token") or data.get("token")
                if tok:
                    return tok
        except Exception as e:
            bot_log(f"Panel auth error ({base}{path}): {e}")
    return None

def panel_call(panel: dict, action: str, args: dict | None = None) -> dict:
    base = panel_clean_base_url(panel.get("base_url", ""))
    tok = _panel_auth(panel)
    if not tok:
        return {"ok": False, "error": "احراز هویت با پنل ناموفق بود"}
    
    headers = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    args = args or {}
    
    try:
        if action == "create_user":
            res = requests.post(f"{base}/api/user", json=args, headers=headers, timeout=15, verify=PANEL_VERIFY_SSL)
        elif action == "get_user":
            uname = args.get("username")
            res = requests.get(f"{base}/api/user/{uname}", headers=headers, timeout=15, verify=PANEL_VERIFY_SSL)
        elif action == "modify_user":
            uname = args.get("username")
            res = requests.put(f"{base}/api/user/{uname}", json=args.get("body", {}), headers=headers, timeout=15, verify=PANEL_VERIFY_SSL)
        elif action == "delete_user":
            uname = args.get("username")
            res = requests.delete(f"{base}/api/user/{uname}", headers=headers, timeout=15, verify=PANEL_VERIFY_SSL)
        else:
            return {"ok": False, "error": "عملیات نامعتبر است"}
            
        if res.status_code in (200, 201):
            return {"ok": True, "data": res.json()}
        return {"ok": False, "status_code": res.status_code, "error": res.text}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def panel_ping(panel: dict) -> dict:
    tok = _panel_auth(panel)
    return {"ok": bool(tok)}
