from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import json
import sqlite3
from pesarguard.config import ADMIN_ID, DB_PATH
from pesarguard.constants import DEFAULT_FAQ_TEXT, DEFAULT_GUIDE_TOPICS


_DB: sqlite3.Connection | None = None

def db() -> sqlite3.Connection:
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None, timeout=30)
        _DB.row_factory = sqlite3.Row
        _DB.execute("PRAGMA journal_mode=WAL")
        _DB.execute("PRAGMA busy_timeout=30000")
    return _DB

def q_all(sql: str, params=()) -> list[dict]:
    return [dict(r) for r in db().execute(sql, params).fetchall()]

def q_one(sql: str, params=()) -> dict | None:
    r = db().execute(sql, params).fetchone()
    return dict(r) if r else None

def q_val(sql: str, params=(), default=None):
    r = db().execute(sql, params).fetchone()
    return r[0] if r else default

def ex(sql: str, params=()) -> sqlite3.Cursor:
    return db().execute(sql, params)

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
