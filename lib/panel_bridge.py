#!/usr/bin/env python3
"""panel_bridge.py — CLI bridge: PHP -> Python panel.py (curl_cffi Cloudflare bypass).
Usage: panel_bridge.py '<json-payload>'
Payload: {base_url, username, password, ptype, action, args}
Actions: ping | list_roles | create_admin
Output: single JSON line on stdout.
"""
import asyncio
import json
import os
import sys

# portable: bundled bot/ copy first, then legacy /root/marzban-bot/bot
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNDLED = os.path.join(_BASE, "lib", "bot")
_LEGACY = "/root/marzban-bot/bot"
for _p in (_BUNDLED, _LEGACY):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)


def main() -> None:
    raw = ""
    if len(sys.argv) > 1:
        raw = sys.argv[1]
    else:
        raw = sys.stdin.read()  # پشتیبانی از payload روی stdin (PHP proc_open)
    try:
        payload = json.loads(raw)
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"bad payload: {e}"}))
        return

    from panel import Panel

    base_url = payload.get("base_url", "")
    username = payload.get("username", "")
    password = payload.get("password", "")
    ptype = payload.get("ptype", "pasarguard") or "pasarguard"
    action = payload.get("action", "")
    args = payload.get("args", {}) or {}

    async def run() -> dict:
        p = Panel(base_url, username, password, ptype)
        try:
            if action == "ping":
                ver = await p.ping()
                return {"ok": True, "msg": ver}
            if action == "list_roles":
                roles = await p.list_roles()
                return {"ok": True, "roles": roles}
            if action == "get_admin_info":
                data = await p.get_user(args.get("username", ""))
                return {"ok": True, "data": data}
            if action == "list_admins":
                data = await p.list_admins()
                return {"ok": True, "data": data}
            if action == "delete_admin":
                # کپی Panel.delete_admin (panel.py 213-220): DELETE /api/admin/{u} با فالبک /api/admins/{u}
                await p.delete_admin(args.get("username", ""))
                return {"ok": True}
            if action == "modify_admin":
                data = await p.modify_user(args.get("username", ""), **args.get("fields", {}))
                return {"ok": True, "data": data}
            if action == "modify_admin_data_limit":
                # python extra-GB (main.py 4161-4170): PUT /api/admin/{username} {"data_limit": n}
                uname3 = args.get("username", "")
                lim3 = int(args.get("data_limit", 0))
                done3 = False
                for method3 in ("PUT", "PATCH", "POST"):
                    try:
                        r3 = await p._req(method3, f"/api/admin/{uname3}", json={"data_limit": lim3})
                        if r3.status_code in (200, 204):
                            done3 = True
                            break
                    except Exception:
                        continue
                return {"ok": done3, "data": None if not done3 else {"data_limit": lim3}}
            if action == "modify_admin_status":
                # python aptoggle (main.py 992-1000): PUT /api/admin/{username} {"status": ...}
                uname2 = args.get("username", "")
                st2 = args.get("status", "active")
                done2 = False
                for method2 in ("PUT", "PATCH", "POST"):
                    try:
                        r2 = await p._req(method2, f"/api/admin/{uname2}", json={"status": st2})
                        if r2.status_code in (200, 204):
                            done2 = True
                            break
                    except Exception:
                        continue
                return {"ok": done2, "data": None if not done2 else {"status": st2}}
            if action == "modify_admin_password":
                # PasarGuard: PUT /api/admin/{username} {"password": ...} (admins are NOT users — modify_user 404s)
                uname4 = args.get("username", "")
                pw4 = args.get("password", "")
                done4 = False
                for method4 in ("PUT", "PATCH"):
                    try:
                        r4 = await p._req(method4, f"/api/admin/{uname4}", json={"password": pw4})
                        if r4.status_code in (200, 204):
                            done4 = True
                            break
                    except Exception:
                        continue
                return {"ok": done4, "data": None if not done4 else {}}

            if action == "create_admin":
                uname = args.get("username", "")
                pw = args.get("password", "")
                vol = float(args.get("volume_gb", 0))
                tid = int(args.get("telegram_id", 0))
                rid = int(args.get("role_id", 3))
                data = await p.create_admin(
                    uname, pw, data_limit_gb=vol, role_id=rid, telegram_id=tid
                )
                return {"ok": True, "data": data}
            return {"ok": False, "error": f"unknown action: {action}"}
        except Exception as e:
            return {"ok": False, "error": str(e)[:200]}

    try:
        # 15s hard timeout: a hung panel API must never freeze the single-threaded daemon
        out = asyncio.run(asyncio.wait_for(run(), timeout=15.0))
    except asyncio.TimeoutError:
        out = {"ok": False, "error": "Panel API connection timed out."}
    except Exception as e:
        out = {"ok": False, "error": str(e)[:200]}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
