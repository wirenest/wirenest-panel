import json
import sqlite3
from modules.config import DB_PATH, STATE_FILE, ADMIN_ID, log_event

def bot_log(msg: str) -> None:
    log_event("database", msg)

def db() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def q_all(sql: str, params=()) -> list[dict]:
    with db() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

def q_one(sql: str, params=()) -> dict | None:
    with db() as conn:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None

def q_val(sql: str, params=(), default=None):
    r = q_one(sql, params)
    if not r:
        return default
    return list(r.values())[0]

def ex(sql: str, params=()) -> sqlite3.Cursor:
    with db() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur

def db_init() -> None:
    ex("""
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        ref_code TEXT UNIQUE,
        referred_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS panels (
        name TEXT PRIMARY KEY,
        type TEXT DEFAULT 'pasarguard',
        base_url TEXT,
        username TEXT,
        password_enc TEXT,
        is_active INTEGER DEFAULT 1,
        test_enabled INTEGER DEFAULT 0,
        test_volume_gb INTEGER DEFAULT 1,
        test_duration_days INTEGER DEFAULT 1,
        test_role_id INTEGER DEFAULT 0
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        panel_name TEXT,
        title TEXT,
        volume_gb REAL,
        duration_days INTEGER,
        price INTEGER,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(panel_name) REFERENCES panels(name)
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER,
        panel_name TEXT,
        panel_username TEXT,
        panel_password TEXT,
        plan_title TEXT,
        volume_gb REAL,
        duration_days INTEGER,
        price INTEGER,
        sub_url TEXT,
        status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER,
        amount INTEGER,
        ref_text TEXT,
        status TEXT DEFAULT 'pending',
        photo_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS helps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        body TEXT
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS discount_codes (
        code TEXT PRIMARY KEY,
        percent INTEGER DEFAULT 0,
        max_uses INTEGER DEFAULT 0,
        used_count INTEGER DEFAULT 0
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS gift_codes (
        code TEXT PRIMARY KEY,
        amount INTEGER DEFAULT 0,
        is_used INTEGER DEFAULT 0,
        used_by INTEGER
    )""")
    ex("""
    CREATE TABLE IF NOT EXISTS channels (
        channel_id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT
    )""")

def get_setting(key: str, default=None):
    v = q_val("SELECT value FROM settings WHERE key = ?", (key,))
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return v

def set_setting(key: str, value) -> None:
    s = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    ex("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, s))

def all_settings() -> dict:
    rows = q_all("SELECT key, value FROM settings")
    out = {}
    for r in rows:
        try:
            out[r["key"]] = json.loads(r["value"])
        except Exception:
            out[r["key"]] = r["value"]
    return out

def get_panels() -> dict:
    rows = q_all("SELECT * FROM panels")
    return {r["name"]: r for r in rows}

def bot_enabled() -> bool:
    return bool(get_setting("bot_enabled", True))

def admin_ids() -> list[int]:
    extra = get_setting("extra_admins", [])
    ids = [ADMIN_ID]
    if isinstance(extra, list):
        for e in extra:
            try:
                ids.append(int(e))
            except Exception:
                pass
    return list(set(ids))

def is_admin(tg_id: int) -> bool:
    return int(tg_id) in admin_ids()

# State Management
_STATE_CACHE = {}

def _state_save() -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(_STATE_CACHE, f, ensure_ascii=False, indent=2)
    except Exception as e:
        bot_log(f"State save error: {e}")

def st_get(uid: int, k: str, default=None):
    u = _STATE_CACHE.get(str(uid), {})
    return u.get(k, default)

def st_set(uid: int, kv: dict) -> None:
    su = str(uid)
    if su not in _STATE_CACHE:
        _STATE_CACHE[su] = {}
    _STATE_CACHE[su].update(kv)
    _state_save()

def st_pop(uid: int) -> None:
    su = str(uid)
    if su in _STATE_CACHE:
        del _STATE_CACHE[su]
        _state_save()

def st_all(uid: int) -> dict:
    return _STATE_CACHE.get(str(uid), {})
