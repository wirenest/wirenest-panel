import sqlite3, json, datetime, time, secrets, hashlib
from modules.config import DB_PATH, ADMIN_ID
from modules.utils import mask_mid, jdate, fmt_price, esc, num, bot_username, tg_send


def db_init() -> None:
    stmts = [
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        """CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, username TEXT,
            balance INTEGER NOT NULL DEFAULT 0, is_banned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS receipts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, amount INTEGER NOT NULL,
            ref_text TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, tariff_id INTEGER,
            panel_username TEXT, months INTEGER, volume_gb REAL, price INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS agent_panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL,
            panel_username TEXT NOT NULL, panel_password TEXT NOT NULL,
            panel_name TEXT, panel_type TEXT, quota_gb REAL NOT NULL, expires_at TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            is_test INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS tariffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, months INTEGER NOT NULL,
            volume_gb REAL NOT NULL, price INTEGER NOT NULL, user_limit INTEGER NOT NULL DEFAULT 1,
            is_active INTEGER NOT NULL DEFAULT 1, sort INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS panel_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, panel_name TEXT NOT NULL,
            volume_gb REAL NOT NULL, price INTEGER NOT NULL, active INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS gift_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL, amount INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0, used INTEGER DEFAULT 0, active INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS gift_redemptions (
            gift_id INTEGER NOT NULL, tg_id INTEGER NOT NULL,
            redeemed_at TEXT DEFAULT (datetime('now','localtime')), PRIMARY KEY (gift_id, tg_id))""",
        """CREATE TABLE IF NOT EXISTS discount_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL DEFAULT 'percent', value INTEGER NOT NULL,
            max_uses INTEGER DEFAULT 0, used INTEGER DEFAULT 0, active INTEGER DEFAULT 1, expires_at TEXT)""",
        "CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT NOT NULL, title TEXT)",
        """CREATE TABLE IF NOT EXISTS agent_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, message TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS help_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
        """CREATE TABLE IF NOT EXISTS guide_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '', sort INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS manual_panels (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, url TEXT DEFAULT '',
            username TEXT DEFAULT '', password TEXT DEFAULT '', status TEXT DEFAULT 'available', buyer_id INTEGER)""",
        """CREATE TABLE IF NOT EXISTS pending_buys (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'plan',
            pid INTEGER, pname TEXT, gb REAL, price INTEGER NOT NULL, discount_json TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')))""",
    ]
    for s in stmts:
        ex(s)
    if (q_val("SELECT COUNT(*) FROM guide_topics") or 0) == 0:
        for gt in DEFAULT_GUIDE_TOPICS:
            ex("INSERT INTO guide_topics(title, content) VALUES(?,?)", (gt["title"], gt["content"]))
    if get_setting("faq_text", "") == "":
        set_setting("faq_text", DEFAULT_FAQ_TEXT)

def get_setting(key: str, default=None):
    r = q_one("SELECT value FROM settings WHERE key=?", (key,))
    if r is None:
        return default
    try:
        return json.loads(r["value"])
    except Exception:
        return r["value"]

def set_setting(key: str, value) -> None:
    ex(
        "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(value, ensure_ascii=False)),
    )

def all_settings() -> dict:
    out = {}
    for r in q_all("SELECT key, value FROM settings"):
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out

def get_panels() -> dict:
    p = get_setting("panels", {})
    return p if isinstance(p, dict) else {}

def bot_enabled() -> bool:
    return bool(get_setting("bot_enabled", 1))

def admin_ids() -> list[int]:
    ids = get_setting("admin_ids", []) or []
    if ADMIN_ID and not ids:
        ids = [int(ADMIN_ID)]
        set_setting("admin_ids", ids)
    return [int(i) for i in ids]

def is_admin(tg_id: int) -> bool:
    return int(tg_id) in admin_ids()

_STATE_LOCK = threading.RLock()
try:
    with open(STATE_FILE, encoding="utf-8") as _f:
        STATE: dict = json.load(_f) or {}
except Exception:
    STATE = {}

def _state_save() -> None:
    with _STATE_LOCK:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)

def st_get(uid: int, k: str, default=None):
    v = STATE.get(str(uid), {}).get(k, default)
    return default if v is None else v

def st_set(uid: int, kv: dict) -> None:
    STATE.setdefault(str(uid), {}).update(kv)
    _state_save()

def st_pop(uid: int) -> None:
    STATE.pop(str(uid), None)
    _state_save()

def st_all(uid: int) -> dict:
    return dict(STATE.get(str(uid), {}))
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

def upsert_user(tg_id: int, username: str | None) -> None:
    ex(
        "INSERT INTO users(tg_id,username) VALUES(?,?) ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username",
        (tg_id, username),
    )

def get_balance(tg_id: int) -> int:
    return int(q_val("SELECT balance FROM users WHERE tg_id=?", (tg_id,), 0) or 0)

def spend_balance(tg_id: int, amount: int) -> bool:
    cur = ex("UPDATE users SET balance = balance - ? WHERE tg_id=? AND balance >= ?", (amount, tg_id, amount))
    return cur.rowcount == 1

def add_balance(tg_id: int, amount: int) -> None:
    ex(
        "INSERT INTO users(tg_id,balance) VALUES(?,?) ON CONFLICT(tg_id) DO UPDATE SET balance=balance+?",
        (tg_id, max(0, amount), amount),
    )

def create_receipt(tg_id: int, amount: int, ref_text: str) -> int:
    cur = ex("INSERT INTO receipts(tg_id,amount,ref_text) VALUES(?,?,?)", (tg_id, amount, ref_text))
    return int(cur.lastrowid)

def receipt_ref_exists(needle: str) -> bool:
    if q_one("SELECT 1 FROM receipts WHERE ref_text=? LIMIT 1", (needle,)):
        return True
    return bool(q_one("SELECT 1 FROM receipts WHERE ('|' || ref_text || '|') LIKE ? LIMIT 1", (f"%| {needle}|%",)))

def report_purchase(tg_id: int, uname: str, plan_title: str, amount: int, tag: str, panel_url: str = "") -> None:
    rg = str(get_setting("report_group", "") or "")
    if not rg:
        return
    h = {"تست": "#تست", "افزایش": "#افزایش_حجم"}.get(tag, "#خرید_پنل")
    txt = (
        "🛒 <b>گزارش خرید پنل</b>\n"
        f"🗓 {jdate()} — ⏰ {datetime.now().strftime('%H:%M:%S')}\n"
        f"\n👤 کاربر:  {mask_mid(str(tg_id))}\n"
        f"🆔 سرویس: {mask_mid(uname)}\n"
        f"📦 پلن: {esc(plan_title)}\n"
        f"💵 مبلغ: {fmt_price(amount)}\n"
        f"{h}\n"
    )
    bot = bot_username()
    kb = None
    if bot:
        txt += f"🤖 ربات: @{bot}\n"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 ورود به پنل‌ساز", url="https://t.me/" + bot, style="success")]])
    tg_send(rg, txt, kb)
