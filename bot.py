import re
import os
import sys
import json
import time
import html
import sqlite3
import hashlib
import base64
import secrets
import logging
import asyncio
import requests
import threading
import urllib.parse
from telegram.ext import Defaults
from datetime import datetime, timedelta
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BOT_TOKEN = "8750301426:AAE3H7W3F4ye4MLDdUHCYVUizAq3nt4RDLw"
ADMIN_ID = 7254045901
SUPPORT_ID = ""
CARD_NUMBER = ""
CARD_OWNER = ""
PANEL_CRYPTO_KEY = ""
PANEL_RELAY_URL = ""
PANEL_RELAY_KEY = ""
PANEL_VERIFY_SSL = True

DB_PATH = os.path.join(BASE_DIR, "data", "bot.sqlite")
STATE_FILE = os.path.join(BASE_DIR, "data", "state.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "bot.log")

os.environ.setdefault("TZ", "Asia/Tehran")
try:
    time.tzset()
except Exception:
    pass
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)

def bot_log(msg: str) -> None:
    logging.info(msg)

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

DEFAULT_GUIDE_TOPICS: list = [
    {
        "title": "ویندوز",
        "content": "📌 راهنمای اتصال — ویندوز\n\nروی ویندوز می‌توانید از کلاینت‌های زیر استفاده کنید: v2rayN (معادل دسکتاپ v2rayNG)، Hiddify و Netch.\n\n📥 دانلود برنامه‌ها\n🔶 v2rayN — https://github.com/2dust/v2rayN/releases\n🔶 Hiddify — https://github.com/hiddify/hiddify-app/releases\n🔶 Netch — https://github.com/netchx/netch/releases\n\n🛠 مراحل اتصال (پیشنهادی: v2rayN / Hiddify)\n۱) فایل نصب یا Portable را دانلود و نصب/استخراج کنید.\n۲) در صورت نیاز، برنامه را به‌عنوان Administrator اجرا کنید و فایروال ویندوز را تأیید کنید.\n۳) لینک اشتراک یا کانفیگ را از پنل کپی کنید.\n۴) در v2rayN: افزودن اشتراک → به‌روزرسانی → انتخاب سرور → Set as active system proxy / Connect.\n۵) در Hiddify: افزودن پروفایل از لینک → اتصال.\n۶) در Netch: حالت مناسب (Process Mode / TUN) را انتخاب، کانفیگ را وارد و Start بزنید.\n\n💡 نکته: پس از اتصال، IP یا یک سایت تست را چک کنید. در صورت قطعی، سرور دیگری را امتحان کنید یا اشتراک را Update کنید.\n\n🏠 برای بازگشت از دکمه‌های زیر استفاده کنید."
    },
    {
        "title": "اندروید",
        "content": "📌 راهنمای اتصال — اندروید\n\nروی اندروید معمولاً از v2rayNG یا Hiddify استفاده می‌شود. هر دو رایگان‌اند و لینک اشتراک پنل را به‌راحتی ایمپورت می‌کنند.\n\n📥 دانلود برنامه‌ها\n🔶 v2rayNG — Google Play — https://play.google.com/store/apps/details?id=com.v2ray.ang\n🔶 v2rayNG — GitHub — https://github.com/2dust/v2rayNG/releases\n🔶 Hiddify — سایت رسمی — https://hiddify.com\n🔶 Hiddify — GitHub — https://github.com/hiddify/hiddify-app/releases\n\n🛠 مراحل اتصال\n۱) یکی از برنامه‌های بالا را نصب کنید.\n۲) برنامه را باز کنید و در صورت درخواست، اجازهٔ VPN / اتصال را بدهید.\n۳) از پنل سرویس، لینک اشتراک (Subscription) یا کانفیگ را کپی کنید.\n۴) در v2rayNG: منوی ☰ → Subscription setting → افزودن لینک → به‌روزرسانی؛ سپس سرور را انتخاب و Connect کنید.\n۵) در Hiddify: افزودن از لینک / QR → چسباندن لینک → Connect.\n\n💡 نکته: اگر کانفیگ‌ها ظاهر نشدند، اشتراک را یک‌بار Update کنید و نسخهٔ برنامه را به‌روز نگه دارید.\n\n🏠 برای بازگشت از دکمه‌های زیر استفاده کنید."
    },
    {
        "title": "مک",
        "content": "📌 راهنمای اتصال — مک\n\nبرای macOS، کلاینت پیشنهادی Clash Verge (Clash Verge Rev) است که از اشتراک و پروتکل‌های رایج پشتیبانی می‌کند.\n\n📥 دانلود برنامه\n🔶 Clash Verge — https://github.com/clash-verge-rev/clash-verge-rev/releases\n\n🛠 مراحل اتصال\n۱) نسخهٔ مناسب معماری مک (Intel یا Apple Silicon) را از Releases دانلود کنید.\n۲) نصب کنید؛ در صورت هشدار امنیتی، از System Settings → Privacy & Security اجازهٔ اجرا بدهید.\n۳) Clash Verge را باز کنید.\n۴) لینک اشتراک را در Profiles / Subscription اضافه کنید و Update بزنید.\n۵) نود (سرور) را انتخاب و System Proxy یا TUN را روشن کنید.\n\n💡 نکته: اگر سایتی باز نشد، حالت TUN یا سرور دیگری را امتحان کنید و همیشه از آخرین نسخه استفاده کنید.\n\n🏠 برای بازگشت از دکمه‌های زیر استفاده کنید."
    },
    {
        "title": "لینوکس",
        "content": "📌 راهنمای اتصال — لینوکس\n\nروی لینوکس نیز می‌توانید از Clash Verge استفاده کنید؛ مناسب کار با اشتراک و پروتکل‌هایی مثل vmess (و سایر پروتکل‌های پشتیبانی‌شده در پنل).\n\n📥 دانلود برنامه\n🔶 Clash Verge — https://github.com/clash-verge-rev/clash-verge-rev/releases\n\n🛠 مراحل اتصال\n۱) از Releases، پکیج مناسب توزیع خود را بگیرید (AppImage، deb یا rpm).\n۲) نصب یا اجرا کنید و دسترسی لازم را بدهید.\n۳) لینک اشتراک را در Profiles اضافه و به‌روزرسانی کنید.\n۴) سرور را انتخاب و System Proxy / TUN را فعال کنید.\n۵) اتصال را با باز کردن یک سایت یا بررسی IP تست کنید.\n\n💡 نکته: پس از Update اشتراک، مطمئن شوید پروفایل‌ها کامل لود شده‌اند. در صورت مشکل فایروال یا DNS، یک‌بار حالت TUN را امتحان کنید.\n\n🏠 برای بازگشت از دکمه‌های زیر استفاده کنید."
    },
    {
        "title": "iOS",
        "content": "📌 راهنمای اتصال — iOS\n\nروی آیفون و آیپد معمولاً از FairVPN یا Hiddify استفاده می‌شود. نصب فقط از App Store یا لینک رسمی انجام شود.\n\n📥 دانلود برنامه‌ها\n🔶 FairVPN — App Store\n🔶 Hiddify — https://hiddify.com\n\n🛠 مراحل اتصال\n۱) برنامه را از لینک بالا نصب کنید.\n۲) اجازهٔ افزودن VPN Configuration را تأیید کنید (رمز یا Face ID لازم است).\n۳) لینک اشتراک یا QR را از پنل بگیرید.\n۴) Import / Add Subscription را بزنید و لینک را وارد کنید (یا QR را اسکن کنید).\n۵) سرور را انتخاب و Connect را فعال کنید.\n\n💡 نکته: اگر اتصال برقرار نشد، در تنظیمات iOS مسیر VPN را چک کنید و اپ را به‌روز نگه دارید.\n\n🏠 برای بازگشت از دکمه‌های زیر استفاده کنید."
    }
]
DEFAULT_FAQ_TEXT: str = "📜 سوالات متداول — پنل ربات فروش\n\nکاربران گرامی، در این بخش به پرتکرارترین پرسش‌ها پاسخ داده‌ایم تا استفاده از سرویس‌ها ساده‌تر باشد. پیشنهاد می‌کنیم همهٔ موارد را یک‌بار مرور کنید تا با امکانات ربات فروش آشنا شوید.\n\n\n▪️ چگونه می‌توانم پنل بسازم؟\nپنل را می‌توانید در کمتر از ۱۰ ثانیه ایجاد کنید. به دکمه 🛍 تهیه سرویس بروید و پنل خود را بسازید.\n\n▪️ از چه پنلی استفاده می‌کنید؟\nسرویس‌ها روی مرزبان / PasarGuard ارائه می‌شوند.\n\n\n▪️ آیا برای استفاده از سرویس‌ها نیاز به احراز هویت دارم؟\nخیر. نیازی به احراز هویت فیزیکی یا مجازی نیست و می‌توانید با خیال راحت خرید کنید یا به همکاران بفروشید.\n\n▪️ چگونه می‌توانم ترافیک اضافه خریداری کنم؟\nپس از ساخت پنل، از پنل مدیریت سرویس روی ➕ تهیه حجم بزنید و حجم مورد نظر را خریداری کنید.\n\n▪️ آیا سرویس‌های ربات فروش برای گیمینگ مناسب هستند؟\nبستگی به کیفیت مسیر سرور دارد؛ در صورت نیاز با پشتیبانی مشورت کنید.\n\n\n▪️ آیا نیاز به خرید سرور برای استفاده از پنل‌ها دارم؟\nخیر. نیازی به خرید یا نگهداری سرور ندارید؛ پنل‌ها آماده‌اند.\n\n▪️ آیا سرویس‌ها هزینه پنهانی دارند؟\nخیر. هزینهٔ اضافه‌ای وجود ندارد و تعرفه‌ها شفاف هستند.\n\n▪️ چگونه می‌توانم پنل را به کاربر دیگر منتقل کنم؟\nاز پنل مدیریت، دکمه انتقال سرویس را بزنید و آیدی عددی کاربر مقصد را وارد کنید.\n\n▪️ چگونه از ترافیک استفاده کنم؟\nطبق راهنمای اتصال داخل ربات، اپلیکیشن مناسب را نصب و اشتراک را اضافه کنید. پنل تست اولیه ۱۵ گیگ با اعتبار ۲۴ ساعت است.\n\n▪️ آیا در صورت اتمام حجم سرویس، امکان تمدید وجود دارد؟\nدر صورت اتمام حجم، می‌توانید حجم اضافه تهیه کنید یا سرویس را تمدید کنید.\n\n▪️ آیا پنل‌ها از تمام اپراتورها پشتیبانی می‌کنند؟\nمعمولاً بله؛ در صورت مشکل اتصال با پشتیبانی در ارتباط باشید.\n\n▪️ آیا امکان دریافت بکاپ از پنل وجود دارد؟\nبکاپ‌گیری توسط مالک سرویس/پشتیبان فنی انجام می‌شود؛ در صورت نیاز با پشتیبانی هماهنگ کنید.\n\n▪️ آیا هزینه بازگشت وجه وجود دارد؟\nطبق قوانین مجموعه ربات فروش؛ جزئیات را از پشتیبانی بپرسید.\n\n▪️ آیا پنل‌ها شامل لوکیشن‌های بین‌المللی هستند؟\nبسته به تنظیمات مالک ربات متفاوت است؛ از تعرفه‌ها یا پشتیبانی بپرسید.\n\n▪️ آیا سرویس‌های ربات فروش برای فعالیت‌های تجاری مناسب هستند؟\nبله. هم برای استفاده شخصی و هم تجاری قابل استفاده‌اند، مگر اینکه مالک محدودیت جداگانه اعلام کند.\n\n\n📲 برای اطلاعات بیشتر، از دکمه «☎️ پشتیبانی» استفاده کنید."

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

def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)

def num(p) -> str:
    return f"{int(round(float(p))):,}"

def fmt_price(p) -> str:
    return num(p) + " تومان"

def fmt_gb(v) -> str:
    f = float(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.2f}".rstrip("0").rstrip(".")

def g2(v) -> str:
    return "%g" % float(v)

def mask_mid(s: str) -> str:
    s = str(s)
    if len(s) <= 6:
        return s
    return s[:4] + "****" + s[-2:]

def jdate(ts: str | None = None) -> str:
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except Exception:
        return str(ts)
    gy, gm, gd = dt.year, dt.month, dt.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy <= 1600:
        jy = 0
        gy -= 621
    else:
        jy = 979
        gy -= 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return f"{jy:04d}/{jm:02d}/{jd:02d} {dt.hour:02d}:{dt.minute:02d}"

def urldec(s: str) -> str:
    return urllib.parse.unquote(s)

def gen_username(prefix: str = "srv") -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return prefix + "".join(secrets.choice(chars) for _ in range(8))

def strong_password() -> str:
    lower, upper, digit, special = "abcdefghjkmnpqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", "!@#$%&*?"
    chars = (
        [secrets.choice(lower) for _ in range(6)]
        + [secrets.choice(upper) for _ in range(3)]
        + [secrets.choice(digit) for _ in range(3)]
        + [secrets.choice(special)]
    )
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)

def parse_int_digits(text: str) -> int:
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group(0)) if m else 0

_LOOP = asyncio.new_event_loop()
threading.Thread(target=_LOOP.run_forever, daemon=True).start()
_BOT_OBJ: Bot | None = None

def _run(coro, timeout: float = 60):
    return asyncio.run_coroutine_threadsafe(coro, _LOOP).result(timeout)

def bot_obj() -> Bot:
    global _BOT_OBJ
    if _BOT_OBJ is None:
        _BOT_OBJ = Bot(BOT_TOKEN)
        _run(_BOT_OBJ.initialize())
    return _BOT_OBJ

async def _tg_call(method: str, d: dict):
    b = bot_obj()
    if method == "sendMessage":
        extra = {k: v for k, v in d.items() if k not in ("chat_id", "text", "reply_markup", "parse_mode")}
        m = await b.send_message(
            chat_id=d["chat_id"],
            text=d["text"],
            parse_mode=ParseMode.HTML,
            reply_markup=d.get("reply_markup"),
            **extra,
        )
        return {"message_id": m.message_id}
    if method == "editMessageText":
        await b.edit_message_text(
            text=d["text"],
            chat_id=d["chat_id"],
            message_id=d["message_id"],
            parse_mode=ParseMode.HTML,
            reply_markup=d.get("reply_markup"),
        )
        return {}
    if method == "editMessageReplyMarkup":
        await b.edit_message_reply_markup(
            chat_id=d["chat_id"], message_id=d["message_id"], reply_markup=d.get("reply_markup")
        )
        return {}
    if method == "copyMessage":
        m = await b.copy_message(chat_id=d["chat_id"], from_chat_id=d["from_chat_id"], message_id=d["message_id"])
        return {"message_id": m.message_id}
    if method == "pinChatMessage":
        await b.pin_chat_message(
            chat_id=d["chat_id"],
            message_id=d["message_id"],
            disable_notification=bool(d.get("disable_notification", True)),
        )
        return {}
    if method == "answerCallbackQuery":
        await b.answer_callback_query(callback_query_id=d["callback_query_id"])
        return {}
    if method == "getChatMember":
        cm = await b.get_chat_member(chat_id=d["chat_id"], user_id=d["user_id"])
        return {"status": cm.status}
    if method == "getMe":
        me = await b.get_me()
        return {"username": me.username}
    if method == "deleteWebhook":
        await b.delete_webhook(drop_pending_updates=bool(d.get("drop_pending_updates", False)))
        return {}
    raise ValueError("unsupported method: " + method)

def _plain_html(text: str) -> str:
    return html.escape(html.unescape(re.sub(r"<[^>]+>", "", str(text))), quote=False)


def tg(method: str, data: dict | None = None, timeout: int = 35) -> dict:
    data = dict(data or {})
    fallback_used = False
    for _ in range(4):
        try:
            return {"ok": True, "result": _run(_tg_call(method, data), timeout + 25)}
        except RetryAfter as e:
            ra = e.retry_after
            time.sleep((ra.total_seconds() if isinstance(ra, timedelta) else float(ra)) + 1)
        except TelegramError as e:
            desc = str(e)
            if "parse entities" in desc.lower() and "text" in data and not fallback_used:
                fallback_used = True
                data["text"] = _plain_html(data["text"])
                bot_log(f"HTML parse fallback in {method}: {desc}")
                continue
            return {"ok": False, "description": desc}
        except Exception as e:
            bot_log(f"TG error {method}: {e}")
            return {"ok": False}
    return {"ok": False}


def theme_kb(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    bc = get_setting("btn_color", "colorful")
    if bc == "none":
        return kb
    new_rows = []
    for row in kb.inline_keyboard:
        new_row = []
        for btn in row:
            text = btn.text
            if any(text.startswith(e) for e in ["🔵", "🟢", "🔴", "🟡", "🟠", "🟣"]):
                new_row.append(btn)
                continue

            prefix = ""
            style = None
            if bc == "blue":
                style = "primary"
            elif bc == "green":
                style = "success"
            elif bc == "red":
                style = "danger"
            elif bc == "colorful":
                cbd = btn.callback_data or ""
                t = text.lower()
                if any(x in cbd for x in ["buy", "confirm", "pay", "ok", "add", "submit", "apcreds", "apgb"]) or any(x in t for x in ["تایید", "خرید", "شارژ", "افزودن", "ثبت", "پرداخت"]):
                    style = "success"
                elif any(x in cbd for x in ["cancel", "del", "remove", "no", "reject", "close", "off"]) or any(x in t for x in ["حذف", "لغو", "انصراف", "رد", "بستن", "خاموش"]):
                    style = "danger"
                elif any(x in cbd for x in ["back", "home", "return"]) or any(x in t for x in ["بازگشت", "منوی"]):
                    style = "primary"
                else:
                    style = "primary"

            kwargs = {
                "text": text,
                "style": style
            }
            for attr in ["callback_data", "url", "login_url", "web_app", "switch_inline_query", 
                         "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", 
                         "callback_game", "pay", "copy_text", "icon_custom_emoji_id"]:
                val = getattr(btn, attr, None)
                if val is not None:
                    kwargs[attr] = val
            
            btn = InlineKeyboardButton(**kwargs)
            # فقط در صورتی که پلتفرم بله باشد یا متد ارسالی فیلد استایل را بپذیرد
            # چون روی تلگرام خطای 400 می‌دهد، اینجا برای تلگرام حذفش می‌کنیم
            # if style: btn.style = style 
            new_row.append(btn)
        new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows)


def theme_reply_kb(kb: ReplyKeyboardMarkup) -> ReplyKeyboardMarkup:
    bc = get_setting("btn_color", "colorful")
    if bc == "none":
        return kb
    new_rows = []
    for row in kb.keyboard:
        new_row = []
        for btn in row:
            text = btn.text
            style = "primary"
            if bc == "blue":
                style = "primary"
            elif bc == "green":
                style = "success"
            elif bc == "red":
                style = "danger"
            elif bc == "colorful":
                t = text.lower()
                if any(x in t for x in ["خرید", "شارژ", "موجودی", "تایید", "افزودن"]):
                    style = "success"
                elif any(x in t for x in ["لغو", "خروج", "بستن"]):
                    style = "danger"
                elif any(x in t for x in ["مدیریت", "پشتیبانی", "راهنما", "سوالات"]):
                    style = "primary"
                else:
                    style = "primary"

            kwargs = {
                "text": text,
                "style": style
            }
            for attr in ["request_users", "request_chat", "request_contact", "request_location", "request_poll", "web_app"]:
                val = getattr(btn, attr, None)
                if val is not None:
                    kwargs[attr] = val
            new_row.append(KeyboardButton(**kwargs))
        new_rows.append(new_row)

    return ReplyKeyboardMarkup(
        new_rows,
        resize_keyboard=getattr(kb, "resize_keyboard", True),
        one_time_keyboard=getattr(kb, "one_time_keyboard", False),
        selective=getattr(kb, "selective", False),
        input_field_placeholder=getattr(kb, "input_field_placeholder", None)
    )


def tg_send(chat, text: str, kb=None, extra: dict | None = None) -> dict:
    if isinstance(kb, InlineKeyboardMarkup):
        kb = theme_kb(kb)
    elif isinstance(kb, ReplyKeyboardMarkup):
        kb = theme_reply_kb(kb)
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    if kb:
        data["reply_markup"] = kb
    if extra:
        data.update(extra)
    return tg("sendMessage", data)

def edit_menu(chat_id: int, msg_id: int, text: str, kb=None) -> None:
    if isinstance(kb, InlineKeyboardMarkup):
        kb = theme_kb(kb)
    if msg_id:
        params = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
        if kb:
            params["reply_markup"] = kb
        r = tg("editMessageText", params)
        if r.get("ok"):
            return
        if "message is not modified" in str(r.get("description", "")).lower():
            return
        if kb:
            r2 = tg("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": msg_id, "reply_markup": kb})
            if r2.get("ok") or "message is not modified" in str(r2.get("description", "")).lower():
                return
        r3 = tg("editMessageText", params)
        if not r3.get("ok"):
            tg("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"})
        return
    tg_send(chat_id, text, kb)

_CTX = {"mid": None}

def send_or_edit(chat_id: int, text: str, kb=None) -> None:
    mid = _CTX["mid"]
    if kb and isinstance(kb, ReplyKeyboardMarkup):
        tg_send(chat_id, text, kb)
    elif mid:
        edit_menu(chat_id, mid, text, kb)
    else:
        tg_send(chat_id, text, kb)

def notify_admins(text: str, kb=None) -> None:
    first = True
    for aid in admin_ids():
        if not first:
            time.sleep(0.3)
        tg_send(aid, text, kb)
        first = False

_BOT_USERNAME = {"v": ""}

def bot_username() -> str:
    cached = str(get_setting("bot_username", "") or "")
    if cached:
        return cached
    me = tg("getMe")
    un = str((me.get("result") or {}).get("username", ""))
    if un:
        set_setting("bot_username", un)
    return un

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

LBL = {
    "test": "🧪 سرویس تست",
    "buy": "🔐 خرید اشتراک",
    "services": "🛍 سرویس های من",
    "wallet": "🏦 کیف پول + شارژ",
    "guide": "📡 راهنمای اتصال",
    "conditions": "📋 شرایط و توضیحات",
    "support": "☎️ پشتیبانی",
    "faq": "❓ سوالات متداول",
    "admin": "👨‍💼 پنل مدیریت",
}

def features() -> dict:
    f = get_setting("features", {})
    return f if isinstance(f, dict) else {}

def feat_on(key: str, default: bool = False) -> bool:
    f = features()
    return bool(f[key]) if key in f else default

def ikb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([list(r) for r in rows])

def main_menu_kb(admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [LBL["test"], LBL["buy"]],
        [LBL["services"], LBL["wallet"]],
        [LBL["guide"], LBL["conditions"]],
        [LBL["support"], LBL["faq"]],
    ]
    if admin:
        rows.append([LBL["admin"]])
    return ReplyKeyboardMarkup([[KeyboardButton(t) for t in r] for r in rows], resize_keyboard=True)

def admin_menu_kb() -> InlineKeyboardMarkup:
    return ikb(
        [InlineKeyboardButton("📊 آمار", callback_data="adm:stats"), InlineKeyboardButton("📦 مدیریت پنل‌ها", callback_data="adm:panels")],
        [InlineKeyboardButton("👥 مدیریت کاربران", callback_data="adm:users"), InlineKeyboardButton("🧾 صف رسیدها", callback_data="adm:receipts")],
        [InlineKeyboardButton("🛠 قابلیت‌های پنل", callback_data="adm:features")],
        [InlineKeyboardButton("🏷 کد تخفیف", callback_data="adm:discounts"), InlineKeyboardButton("🎁 کد هدیه", callback_data="adm:gifts")],
        [InlineKeyboardButton("📚 مدیریت آموزش", callback_data="adm:helps"), InlineKeyboardButton("⚙️ تنظیمات", callback_data="adm:settings")],
        [InlineKeyboardButton("🔌 خاموش/روشن", callback_data="adm:power")],
    )

def support_kb() -> InlineKeyboardMarkup:
    return ikb([InlineKeyboardButton("✉️ ارسال پیام به پشتیبانی", callback_data="m:tkt", style="success")], [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="m:home")])

def buy_kb(plans: list, tariffs: list) -> InlineKeyboardMarkup:
    rows = []
    for p in plans:
        rows.append([InlineKeyboardButton(f"📦 {p['panel_name']} — \u2066{fmt_gb(p['volume_gb'])} گیگ\u2069 — \u2066{fmt_price(p['price'])}\u2069", callback_data=f"buyplan:{p['id']}")])
    for t in tariffs:
        rows.append([InlineKeyboardButton(f"🏷 {t['title']} — \u2066{fmt_gb(t['volume_gb'])} گیگ\u2069 — \u2066{fmt_price(t['price'])}\u2069", callback_data=f"buy:{t['id']}")])
    rows.append([InlineKeyboardButton("➡️ منوی اصلی", callback_data="m:home")])
    return InlineKeyboardMarkup(rows)

def wallet_kb() -> InlineKeyboardMarkup:
    return ikb(
        [InlineKeyboardButton("➕ شارژ موجودی", callback_data="wal:addcredit", style="success")],
        [InlineKeyboardButton("📜 رسیدهای من", callback_data="wal:receipts")],
        [InlineKeyboardButton("🎁 کد هدیه دارم", callback_data="wal:gift")],
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="m:home")],
    )

def cancel_kb() -> InlineKeyboardMarkup:
    return ikb([InlineKeyboardButton("❌ لغو", callback_data="setcancel", style="danger")])

def back_adm_kb() -> InlineKeyboardMarkup:
    return ikb([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])

def welcome_text(frm: dict) -> str:
    s = str(get_setting("start_text", "") or "")
    greet = s if s else "سلام {name} 👋\nبه ربات فروش سرویس خوش اومدی!"
    return greet.replace("{name}", esc(frm.get("first_name", ""))).replace("{username}", "@" + str(frm.get("username", "")))

def show_buy_screen(chat_id: int) -> None:
    plans = q_all("SELECT * FROM panel_plans WHERE active=1 ORDER BY price")
    tariffs = q_all("SELECT * FROM tariffs WHERE is_active=1 ORDER BY price")
    if not plans and not tariffs:
        tg_send(chat_id, "فعلا تعرفه‌ای تعریف نشده.", main_menu_kb(is_admin(chat_id)))
        return
    text = "💳 <b>تعرفه‌های سرویس:</b>\n\n"
    if tariffs:
        text += "\n".join("• " + esc(t["title"]) for t in tariffs) + "\n"
    if plans:
        if tariffs:
            text += "\n"
        text += "📦 <b>پلن‌های حجمی:</b>\n" + "\n".join(f"• {esc(p.get('panel_name') or 'تانل')} — {int(float(p['volume_gb'])) if float(p['volume_gb']).is_integer() else p['volume_gb']} گیگ — {num(p['price'])} تومان" for p in plans)
    tg_send(chat_id, text, buy_kb(plans, tariffs))

def show_guide(chat_id: int) -> None:
    intro = get_setting("guide_intro") or "📌 راهنمای اتصال — سیستم‌عامل خود را انتخاب کنید!"
    rows = [[InlineKeyboardButton(str(t["title"]), callback_data=f"guide:{t['id']}")] for t in q_all("SELECT id, title FROM guide_topics ORDER BY id")]
    rows.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="m:home")])
    send_or_edit(chat_id, str(intro), InlineKeyboardMarkup(rows))

def show_conditions(chat_id: int) -> None:
    c = get_setting("conditions_text") or (
        "📋 <b>شرایط و توضیحات ربات</b>\n\n"
        "✅ پنل ادمین محدود روی سرور قدرتمند تحویل می‌گیرید\n"
        "♾️ <b>بدون محدودیت زمان</b> — پنل تا تمام شدن حجم معتبر است\n"
        "📦 سهمیه مشخص در هر پلن که بین مشتریان خود تقسیم می‌کنید\n"
        "🛠 پنل مدیریت کامل: ساخت و مدیریت سرویس‌ها برای مشتریانتان\n"
        "➕ امکان خرید حجم اضافه هر زمان\n"
        "⚡ تحویل آنی بعد از تایید پرداخت\n"
        "☎️ پشتیبانی پاسخ‌گو\n\n"
        "❗ مسئولیت استفاده از پنل با خریدار است؛ فروش غیرمجاز ممنوع."
    )
    tg_send(chat_id, str(c), main_menu_kb(is_admin(chat_id)))

def start_support(chat_id: int) -> None:
    sup = str(get_setting("support_id", "") or "")
    txt = "☎️ پشتیبانی"
    if sup:
        txt += "\nآیدی پشتیبانی: @" + sup.lstrip("@")
    txt += "\n\nبرای ارسال تیکت، روی دکمه زیر بزن و پیامت را بنویس!"
    tg_send(chat_id, txt, support_kb())
    st_set(chat_id, {"await": "support_msg"})

def wallet_screen(chat_id: int) -> None:
    send_or_edit(chat_id, f"🏦 <b>کیف پول شما</b>\n\n💵 موجودی: <b>{fmt_price(get_balance(chat_id))}</b>", wallet_kb())

def start_topup(chat_id: int) -> None:
    st_set(chat_id, {"await": "topup_amount"})
    send_or_edit(chat_id, "💰 مبلغ شارژ را به تومان بفرست (مثلاً: 100000)\n\nیا «🏠 بازگشت به منوی اصلی» بزن!")

def wallet_add_credit(chat_id: int) -> None:
    st = st_all(chat_id)
    price = 0
    bp = st.get("buy_plan")
    if isinstance(bp, dict):
        price = int(bp.get("orig_price") or bp.get("price") or 0)
    elif st.get("xp_kind") == "extragb":
        price = int(st.get("xp_price") or 0)
    elif st.get("back_tariff"):
        price = int(q_val("SELECT price FROM tariffs WHERE id=?", (int(st["back_tariff"]),), 0) or 0)
    if price:
        deficit = max(price - get_balance(chat_id), 0) or price
        st_set(chat_id, {"await": "card_wait", "amount": deficit, "buy_plan": bp, "back_tariff": st.get("back_tariff")})
        wallet_card_sent(chat_id)
        return
    start_topup(chat_id)

def wallet_card_sent(chat_id: int) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    gw = str(st_get(chat_id, "gw", "card"))
    gw_label = {"tron": "💵 ترون", "zarinpal": "🟡 زرین پال", "aqayepardakht": "🔵 آقای پرداخت"}.get(gw)
    if gw_label:
        body = (
            f"برای پرداخت {fmt_price(amount)} از طریق {gw_label}:\n\n"
            f"💼 آدرس ولت:\n<code>{esc(get_setting('wallet_address', '—'))}</code>\n\n"
            "پس از واریز، دکمه «✉️ ارسال کردم (ارسال رسید)» را بزن و هش تراکنش/عکس رسید را بفرست!"
        )
    else:
        card = get_setting("card_number", "—")
        owner = get_setting("card_owner", "—")
        body = (
            f"💳 کارت به کارت:\n\n💳 شماره کارت (کپی کن):\n<code>{esc(card)}</code>\n"
            f"👤 به نام: {esc(owner)}\n\n"
            f"💰 مبلغ واریزی: <b>{fmt_price(amount)}</b>\n\n"
            "مبلغ را دقیقاً همان عدد واریز کن. پس از واریز، دکمه زیر را بزن!"
        )
    st_set(chat_id, {"await": "card_wait", "amount": amount,
                     "buy_plan": st_get(chat_id, "buy_plan"), "back_tariff": st_get(chat_id, "back_tariff")})
    send_or_edit(chat_id, body, ikb([InlineKeyboardButton("✉️ ارسال کردم (ارسال رسید)", callback_data="wal:receipt", style="success")]))

def my_receipts(chat_id: int) -> None:
    rows = q_all("SELECT id, amount, status, created_at FROM receipts WHERE tg_id=? ORDER BY id DESC LIMIT 10", (chat_id,))
    if not rows:
        send_or_edit(chat_id, "هنوز رسیدی ثبت نکردی.")
        return
    smap = {"pending": "⏳ در انتظار", "approved": "✅ تایید شده", "rejected": "❌ رد شده", "deleted": "🗑 حذف"}
    txt = "📄 آخرین رسیدها:\n\n"
    for r in rows:
        txt += f"#{r['id']} — {fmt_price(r['amount'])} — {smap.get(r['status'], r['status'])} — {jdate(r['created_at'])}\n"
    send_or_edit(chat_id, txt)

def start_gift_redeem(chat_id: int) -> None:
    st_set(chat_id, {"await": "gift_redeem"})
    send_or_edit(chat_id, "🎁 کد هدیه را بفرست (یا /cancel برای انصراف)!")

def handle_gift_redeem(chat_id: int, text: str) -> None:
    code = text.strip().upper()
    row = q_one("SELECT * FROM gift_codes WHERE UPPER(code)=? AND active=1", (code,))
    if not row:
        tg_send(chat_id, "❌ کد هدیه نامعتبر یا غیرفعال است. دوباره بفرست یا /cancel!")
        st_pop(chat_id)
        return
    
    # 1. Atomic check for duplicate usage by the same user via UNIQUE constraint (gift_id, tg_id)
    try:
        ex("INSERT INTO gift_redemptions(gift_id, tg_id) VALUES(?,?)", (row["id"], chat_id))
    except sqlite3.IntegrityError:
        tg_send(chat_id, "❌ شما قبلاً از این کد هدیه استفاده کرده‌اید.")
        st_pop(chat_id)
        return

    # 2. Atomic check for max_uses limit to prevent concurrent spam overload
    cur = ex("UPDATE gift_codes SET used = used + 1 WHERE id=? AND (max_uses=0 OR used < max_uses)", (row["id"],))
    if cur.rowcount == 0:
        # Revert the redemption entry if max uses was reached
        ex("DELETE FROM gift_redemptions WHERE gift_id=? AND tg_id=?", (row["id"], chat_id))
        tg_send(chat_id, "❌ ظرفیت استفاده از این کد هدیه به پایان رسیده است.")
        st_pop(chat_id)
        return

    add_balance(chat_id, int(row["amount"]))
    st_pop(chat_id)
    tg_send(chat_id, f"🎉 تبریک! کد هدیه «{esc(code)}» اعمال شد.\n{fmt_price(row['amount'])} به کیف پولت اضافه شد.")

def service_panel_base(panel_name: str) -> str:
    for pname, cfg in get_panels().items():
        if pname.lower() == panel_name.lower():
            return str(cfg.get("base_url", ""))
    return panel_name

def _find_admin(p: dict, uname: str) -> dict | None:
    res = panel_call(p, "list_admins", {}) or {}
    for a in res.get("data") or []:
        if a.get("username") == uname:
            return a
    return None

def services_home(chat_id: int) -> None:
    # Only show active services to the user
    rows = q_all("SELECT * FROM agent_panels WHERE tg_id=? AND status='active' ORDER BY id DESC", (chat_id,))
    if not rows:
        send_or_edit(chat_id, "🛡 فعلاً سرویسی نداری. از «🔐 خرید اشتراک» یک سرویس تهیه کن! 🛒", main_menu_kb(is_admin(chat_id)))
        return
    kb = [[InlineKeyboardButton("🛡 " + r["panel_username"], callback_data=f"svc:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("➡️ منوی اصلی", callback_data="m:home")])
    send_or_edit(
        chat_id,
        "🔖 <b>مدیریت سرویس</b>\n\n🪂 سرویسی که می‌خواهید مدیریت کنید را از لیست زیر انتخاب کنید.\n\n"
        "🪂 بعد از انتخاب: مشخصات، حجم اضافه، رمز، روشن/خاموش و ورود به پنل وب در دسترس است.",
        InlineKeyboardMarkup(kb),
    )

def _get_service(chat_id: int, svc_id: int) -> dict | None:
    return q_one("SELECT * FROM agent_panels WHERE id=? AND tg_id=? AND status='active'", (svc_id, chat_id))

def service_screen(chat_id: int, svc_id: int) -> None:
    s = _get_service(chat_id, svc_id)
    if not s:
        send_or_edit(chat_id, "یافت نشد.")
        return
    status_active, used_gb = True, None
    total_gb = float(s["quota_gb"]) if s["quota_gb"] is not None else None
    p = panel_client(s["panel_name"], s["panel_type"] or None)
    if p:
        mine = _find_admin(p, s["panel_username"])
        if mine:
            used_gb = round(float(mine.get("used_traffic") or 0) / 1024 ** 3, 2)
            lim = float(mine.get("data_limit") or 0)
            if lim:
                total_gb = round(lim / 1024 ** 3, 2)
            status_active = (mine.get("status") or "active") == "active"
    if total_gb is not None and total_gb >= 999999:
        usage = f"📊 حجم مصرفی: {used_gb} گیگ — سهمیه: نامحدود ∞" if used_gb is not None else "📊 سهمیه: نامحدود ∞"
    elif used_gb is not None and total_gb:
        usage = f"📊 حجم مصرفی: {used_gb} از {total_gb} گیگ"
    else:
        usage = f"📦 سهمیه: {g2(s['quota_gb'] or 0)} گیگ"
    url = panel_login_url(service_panel_base(str(s["panel_name"])))
    text = (
        f"🛡 <b>سرویس شما:</b> <code>{esc(s['panel_username'])}</code>\n"
        + ("🟢 وضعیت: روشن و فعال" if status_active else "🔴 وضعیت: خاموش") + "\n"
        f"{usage}\n🌐 آدرس ورود: <code>{esc(url)}</code>"
    )
    rows = []
    if not s["is_test"]:
        rows.append([InlineKeyboardButton("💳 خرید حجم اضافه", callback_data=f"apgb:{svc_id}", style="success")])
    login_row = [InlineKeyboardButton("🔑 اطلاعات ورود", callback_data=f"apcreds:{svc_id}")]
    if str(url).startswith(("http://", "https://")):
        login_row.append(InlineKeyboardButton("🌐 ورود به پنل وب ↗️", url=url, style="success"))
    rows.append(login_row)
    rows.append([InlineKeyboardButton("🔐 تغییر رمز پنل", callback_data=f"apchpw:{svc_id}")])
    rows.append([InlineKeyboardButton("🔴 خاموش کردن سرویس" if status_active else "🟢 روشن کردن سرویس", callback_data=f"aptoggle:{svc_id}")])
    rows.append([InlineKeyboardButton("➡️ بازگشت به لیست", callback_data="m:services")])
    send_or_edit(chat_id, text, InlineKeyboardMarkup(rows))

def service_toggle(chat_id: int, svc_id: int) -> None:
    s = _get_service(chat_id, svc_id)
    if not s:
        send_or_edit(chat_id, "یافت نشد.")
        return
    p = panel_client(s["panel_name"], s["panel_type"] or None)
    if not p:
        send_or_edit(chat_id, "پنل متصل نیست.")
        return
    mine = _find_admin(p, s["panel_username"])
    if not mine:
        send_or_edit(chat_id, "وضعیت سرویس از پنل دریافت نشد.")
        return
    new = "disabled" if str(mine.get("status") or "active").lower() == "active" else "active"
    res = panel_call(p, "modify_admin_status", {"username": s["panel_username"], "status": new})
    if not (res or {}).get("ok"):
        send_or_edit(chat_id, "❌ تغییر وضعیت ناموفق بود.")
        return
    service_screen(chat_id, svc_id)

def service_extra_gb_start(chat_id: int, svc_id: int) -> None:
    s = _get_service(chat_id, svc_id)
    if not s:
        send_or_edit(chat_id, "یافت نشد.")
        return
    if s["is_test"]:
        send_or_edit(chat_id, "⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.")
        return
    panels = get_panels()
    d = None
    for k, v in panels.items():
        if v.get("base_url") == s["panel_name"] or k == s["panel_name"]:
            d = v
            break
    if not d:
        d = panels.get(str(get_setting("selected_panel", "") or ""))
    if not d or not d.get("extra_gb_price"):
        send_or_edit(chat_id, "قیمت حجم اضافه هنوز توسط ادمین تنظیم نشده. ❗️")
        return
    xp, xmin = int(d["extra_gb_price"]), int(d.get("extra_gb_min") or 1)
    st_set(chat_id, {"await": "agent_gb", "pid": svc_id, "xp": xp, "xmin": xmin})
    send_or_edit(
        chat_id,
        f"📦 چند گیگ اضافه می‌خواهی؟\n\n💰 قیمت حجم اضافه: {num(xp)} تومان برای هر گیگ\n"
        f"⚖️ حداقل خرید: {xmin} گیگ\n\nعدد بفرست (مثلاً 50)!",
    )

def service_login_info(chat_id: int, svc_id: int) -> None:
    s = _get_service(chat_id, svc_id)
    if not s:
        send_or_edit(chat_id, "یافت نشد.")
        return
    url = panel_login_url(service_panel_base(str(s["panel_name"])))
    send_or_edit(
        chat_id,
        f"🔑 اطلاعات ورود پنل:\n\n🌐 آدرس: <code>{esc(url)}</code>\n"
        f"👤 نام کاربری: <code>{esc(s['panel_username'])}</code>\n"
        f"🔑 رمز عبور: <code>{esc(panel_decrypt_pw(str(s['panel_password'])))}</code>",
        main_menu_kb(is_admin(chat_id)),
    )

def service_change_password_start(chat_id: int, svc_id: int) -> None:
    st_set(chat_id, {"await": f"svcnewpass:{svc_id}"})
    send_or_edit(chat_id, "رمز جدید رو بفرست (حداقل ۱۲ کاراکتر شامل حرف بزرگ، عدد و علامت خاص)!")

def service_change_password_apply(chat_id: int, text: str) -> None:
    svc_id = int(str(st_get(chat_id, "await", ""))[11:] or 0)
    st_pop(chat_id)
    s = _get_service(chat_id, svc_id)
    if not s:
        send_or_edit(chat_id, "سرویس یافت نشد.")
        return
    p = panel_client(s["panel_name"], s["panel_type"] or None)
    if not p:
        send_or_edit(chat_id, "❌ خطا در اتصال به پنل.")
        return
    if str(p.get("ptype") or "pasarguard") == "pasarguard":
        weak = (len(text) < 12 or sum(c.isupper() for c in text) < 2
                or not any(c.isdigit() for c in text) or not any(not c.isalnum() for c in text))
        if weak:
            send_or_edit(chat_id, "❌ رمز باید حداقل ۱۲ کاراکتر و شامل دست‌کم ۲ حرف بزرگ، یک عدد و یک علامت خاص باشد. دوباره از منوی سرویس شروع کن.")
            return
    elif len(text) < 8:
        send_or_edit(chat_id, "❌ رمز باید حداقل ۸ کاراکتر باشد. دوباره از منوی سرویس شروع کن.")
        return
    res = panel_call(p, "modify_admin_password", {"username": s["panel_username"], "password": text}) or {}
    if not res.get("ok"):
        err_msg = str(res.get("error") or "modify failed")
        send_or_edit(chat_id, "❌ تغییر رمز ناموفق: " + esc(err_msg))
        notify_admins(
            f"⚠️ <b>خطای تغییر رمز توسط کاربر</b>\n"
            f"👤 کاربر: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n"
            f"🛡 یوزرنیم سرویس: <code>{esc(str(s['panel_username']))}</code>\n"
            f"❗️ خطا: <code>{esc(err_msg)}</code>"
        )
        return
    ex("UPDATE agent_panels SET panel_password=? WHERE id=?", (panel_encrypt_pw(text), svc_id))
    send_or_edit(chat_id, "✅ رمز عوض شد!", main_menu_kb(is_admin(chat_id)))

def _test_pool() -> dict:
    sel = get_setting("selected_panel")
    pool = {}
    for name, d in get_panels().items():
        if d.get("is_test_panel") and d.get("test_gb") and d.get("test_days") and d.get("active", name == sel):
            pool[name] = d
    return pool

def _test_limit_reached(chat_id: int) -> bool:
    limit = int(get_setting("test_limit", 1) or 1)
    return int(q_val("SELECT COUNT(*) FROM agent_panels WHERE tg_id=? AND is_test=1", (chat_id,), 0)) >= limit

def _create_test_service(chat_id: int, d: dict, style: str) -> None:
    tg_send(chat_id, "⏳ در حال ساخت سرویس تست شما...")
    p = panel_client(d.get("base_url", ""), d.get("ptype", "pasarguard"))
    if not p:
        tg_send(chat_id, "❌ خطا در اتصال به پنل — با پشتیبانی تماس بگیر.")
        return
    gb = float(d.get("test_gb") or 0.5)
    days = int(d.get("test_days") or 1)
    uname = "test" + str(chat_id)[-5:]
    pw = strong_password()
    res = panel_call(p, "list_admins", {})
    if res and res.get("ok") and isinstance(res.get("data"), list):
        taken = {str(a.get("username", "")).lower() for a in res["data"]}
        n, cand = 1, uname
        while cand.lower() in taken:
            n += 1
            cand = f"{uname}{n}"
        uname = cand
    cr = panel_call(p, "create_admin", {"username": uname, "password": pw, "volume_gb": gb, "telegram_id": chat_id})
    if not cr or not cr.get("ok"):
        cr = panel_call(p, "create_admin", {"username": uname, "password": pw, "volume_gb": gb})
    if not cr or not cr.get("ok"):
        err = (cr or {}).get("error") or "create failed"
        tg_send(chat_id, "❌ خطا در ساخت پنل تست — با پشتیبانی تماس بگیر.")
        notify_admins(
            f"⚠️ <b>خطای ساخت سرویس تست</b>\n"
            f"👤 کاربر: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n"
            f"❗️ خطا: <code>{esc(str(err))}</code>"
        )
        return
    if (cr.get("data") or {}).get("password_used"):
        pw = cr["data"]["password_used"]
    expires = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    ex(
        "INSERT INTO agent_panels(tg_id, panel_username, panel_password, panel_name, panel_type, quota_gb, expires_at, status, is_test, created_at)"
        " VALUES(?,?,?,?,?,?,?,'active',1,datetime('now','localtime'))",
        (chat_id, uname, panel_encrypt_pw(pw), d.get("base_url", ""), d.get("ptype", "pasarguard"), gb, expires),
    )
    url = panel_login_url(str(d.get("base_url", "")))
    report_purchase(chat_id, uname, f"سرویس تست {fmt_gb(gb)} گیگ", 0, "تست", url)
    if style == "start":
        tg_send(
            chat_id,
            "🧪 <b>سرویس تست شما آماده شد!</b>\n\n"
            f"🌐 آدرس ورود: <code>{esc(url)}</code>\n👤 نام کاربری: <code>{esc(uname)}</code>\n"
            f"🔑 رمز عبور: <code>{esc(pw)}</code>\n📦 حجم: {fmt_gb(gb)} گیگابایت\n📅 اعتبار: {days} روز\n\n"
            "✨ بعد از تست، سرویس اصلی رو از «🔐 خرید اشتراک» بگیر!",
            ikb([InlineKeyboardButton("🛍 سرویس های من", callback_data="m:services")]),
        )
    else:
        tg_send(
            chat_id,
            "🧪 <b>سرویس تست شما آماده شد!</b>\n\n"
            f"🌐 آدرس ورود: <code>{esc(url)}</code>\n👤 یوزرنیم: <code>{esc(uname)}</code>\n"
            f"🔑 رمز: <code>{esc(pw)}</code>\n\n⚠️ این سرویس بعد از {days} روز منقضی می‌شود.",
            main_menu_kb(is_admin(chat_id)),
        )

def handle_test_start(chat_id: int) -> None:
    if _test_limit_reached(chat_id):
        send_or_edit(chat_id, "🧪 شما قبلاً سرویس تست گرفته‌اید!\nاز بخش «🛍 سرویس های من» می‌تونی مدیریتش کنی.",
                     main_menu_kb(is_admin(chat_id)))
        return
    if not get_panels():
        tg_send(chat_id, "❌ فعلاً پنلی متصل نیست.")
        return
    pool = _test_pool()
    if not pool:
        tg_send(chat_id, "⛔️ فعلاً سرویس تست فعال نیست — بعداً دوباره امتحان کن.", main_menu_kb(is_admin(chat_id)))
        return
    if len(pool) > 1:
        rows = [[InlineKeyboardButton(f"🧪 {n} — {g2(d['test_gb'])} گیگ / {int(d['test_days'])} روز", callback_data="testpick:" + n)] for n, d in pool.items()]
        send_or_edit(chat_id, "🧪 از کدام پنل سرویس تست می‌خواهی؟", InlineKeyboardMarkup(rows))
        return
    _create_test_service(chat_id, next(iter(pool.values())), "start")

def handle_test_pick(chat_id: int, name: str) -> None:
    if _test_limit_reached(chat_id):
        send_or_edit(chat_id, "🧪 شما قبلاً سرویس تست گرفته‌اید!")
        return
    d = get_panels().get(name)
    if not d:
        send_or_edit(chat_id, "⛔️ این پنل دیگر در دسترس نیست.")
        return
    if not d.get("is_test_panel") or not d.get("test_gb") or not d.get("test_days") or not d.get(
            "active", name == get_setting("selected_panel")):
        send_or_edit(chat_id, "⛔️ سرویس تست این پنل غیرفعال شد.")
        return
    _create_test_service(chat_id, d, "pick")


def plan_label(pl: dict) -> str:
    return f"{int(float(pl['volume_gb'])) if float(pl['volume_gb']).is_integer() else pl['volume_gb']} گیگ — {esc(pl.get('panel_name') or 'تانل')} — {num(pl['price'])} تومان"

def _cancel_row() -> list:
    return [InlineKeyboardButton("❌ انصراف", callback_data="cancelbuy", style="danger")]

def handle_buy_callback(chat_id: int, data: str) -> None:
    if data.startswith("buyplan:"):
        pid = int(data[8:])
        pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
        if not pl or not pl["active"]:
            send_or_edit(chat_id, "پلن در دسترس نیست.")
            return
        send_or_edit(
            chat_id,
            f"📇 پیش فاکتور شما:\n\n{esc(plan_label(pl))}\n\n"
            "⚠️ توجه: خرید پنل غیرقابل استرداد است. لطفاً قبل از پرداخت از انتخاب خود مطمئن شوید.\n\nبرای ادامه، تایید کن!",
            ikb([InlineKeyboardButton("✅ متوجه شدم، خرید را نهایی کن", callback_data=f"confirmplan:{pid}", style="success")], _cancel_row()),
        )
        return

    if data.startswith("buy:"):
        tid = int(data[4:])
        t = q_one("SELECT * FROM tariffs WHERE id=?", (tid,))
        if not t or not t["is_active"]:
            send_or_edit(chat_id, "تعرفه در دسترس نیست.")
            return
        warn = str(get_setting("nonrefund_text", "") or "⚠️ توجه: خرید پنل غیرقابل استرداد است. لطفاً قبل از پرداخت از انتخاب خود مطمئن شوید.")
        send_or_edit(
            chat_id,
            f"📇 پیش فاکتور شما:\n\n{esc(t['title'])}\n\n{esc(warn)}\n\nبرای ادامه، تایید کن!",
            ikb([InlineKeyboardButton("✅ متوجه شدم، خرید را نهایی کن", callback_data=f"confirm:{tid}", style="success")], _cancel_row()),
        )
        return

    if data.startswith("confirmplan:"):
        pid = int(data[12:])
        pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
        if not pl or not pl["active"]:
            send_or_edit(chat_id, "پلن در دسترس نیست.")
            return
        bal = get_balance(chat_id)
        bp = {"pid": pid, "gb": float(pl["volume_gb"]), "price": int(pl["price"]), "orig_price": int(pl["price"])}
        if bal >= float(pl["price"]):
            st_set(chat_id, {"buy_plan": bp})
            send_or_edit(
                chat_id,
                f"📇 پیش فاکتور شما:\n\n{esc(plan_label(pl))}\n\n💵 موجودی کیف پول شما: {fmt_price(bal)}\n\n"
                "✅ موجودی کافی است. برای پرداخت و ساخت آنی روی دکمه زیر بزنید!",
                ikb(
                    [InlineKeyboardButton(f"✅ پرداخت از موجودی کیف پول ({num(pl['price'])} تومان)", callback_data=f"paybalplan:{pid}", style="success")],
                    [InlineKeyboardButton("🏷 کد تخفیف دارم", callback_data=f"apdc:{pid}")],
                    _cancel_row(),
                ),
            )
            return
        st_set(chat_id, {"await": "topup_amount", "buy_plan": bp})
        ex("INSERT INTO pending_buys(tg_id,kind,pid,pname,gb,price) VALUES(?,?,?,?,?,?)",
           (chat_id, "plan", pid, str(pl["panel_name"]), float(pl["volume_gb"]), int(pl["price"])))
        send_or_edit(
            chat_id,
            f"📇 پیش فاکتور شما:\n\n{esc(plan_label(pl))}\n\n💵 موجودی کیف پول شما: {fmt_price(bal)}\n\n"
            f"❌ <b>موجودی کیف پولت کافی نیست!</b>\nاول کیف پولت را شارژ کن (حداقل {fmt_price(float(pl['price']) - bal)}).",
            ikb([InlineKeyboardButton("💳 شارژ کیف پول", callback_data="wal:addcredit", style="success")], _cancel_row()),
        )
        return

    if data.startswith("confirm:"):
        tid = int(data[8:])
        t = q_one("SELECT * FROM tariffs WHERE id=?", (tid,))
        if not t or not t["is_active"]:
            send_or_edit(chat_id, "تعرفه در دسترس نیست.")
            return
        bal = get_balance(chat_id)
        if bal < float(t["price"]):
            st_set(chat_id, {"await": "topup_amount", "back_tariff": tid})
            ex("INSERT INTO pending_buys(tg_id,kind,pid,pname,gb,price) VALUES(?,?,?,?,?,?)",
               (chat_id, "tariff", tid, str(t["title"]), float(t["volume_gb"]), int(t["price"])))
            send_or_edit(
                chat_id,
                f"📇 پیش فاکتور شما:\n\n{esc(t['title'])}\n\n💵 موجودی کیف پول شما: {fmt_price(bal)}\n\n"
                f"❌ <b>موجودی کیف پولت کافی نیست!</b>\nاول کیف پولت را شارژ کن (حداقل {fmt_price(float(t['price']) - bal)}).",
                ikb([InlineKeyboardButton("💳 شارژ کیف پول", callback_data="wal:addcredit", style="success")], _cancel_row()),
            )
            return
        st_set(chat_id, {"buy_tariff": tid})
        send_or_edit(
            chat_id,
            f"📇 پیش فاکتور شما:\n\n{esc(t['title'])}\n\n💵 موجودی کیف پول شما: {fmt_price(bal)}\n\n"
            "✅ موجودی کافی است. برای پرداخت و ساخت آنی روی دکمه زیر بزنید!",
            ikb([InlineKeyboardButton(f"✅ پرداخت از موجودی کیف پول ({num(t['price'])} تومان)", callback_data=f"paybal:{tid}", style="success")], _cancel_row()),
        )
        return

    if data == "cancelbuy":
        st_pop(chat_id)
        tg_send(chat_id, "❌ خرید لغو شد.")
        return

    if data.startswith("apdc:"):
        pid = int(data[5:])
        bp = st_get(chat_id, "buy_plan", {}) or {}
        if bp.get("pid") != pid:
            send_or_edit(chat_id, "جلسه خرید منقضی شد.")
            return
        st_set(chat_id, {"await": "buy_discount_code"})
        send_or_edit(chat_id, "🏷 کد تخفیف را بفرست (یا /cancel برای انصراف)!")
        return

    if data.startswith("paybalplan:"):
        pid = int(data[11:])
        pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
        if not pl:
            send_or_edit(chat_id, "پلن نامعتبر.")
            return
        bal = get_balance(chat_id)
        bp = st_get(chat_id, "buy_plan", {}) or {}
        pay = int(pl["price"])
        if bp.get("pid") == pid and bp.get("discount") and 0 <= int(bp.get("price") or 0) < int(pl["price"]):
            pay = int(bp["price"])
        if bal < pay:
            send_or_edit(chat_id, "موجودی کافی نیست.")
            return
        st_set(chat_id, {"await": "buy_custom_username", "pid": pid,
                         "buy_plan": bp or {"pid": pid, "price": pay, "orig_price": int(pl["price"])}})
        send_or_edit(
            chat_id,
            f"👤 <b>انتخاب نام کاربری</b>\n\nپلن: {fmt_gb(pl['volume_gb'])} گیگ — {num(pay)} تومان\n\n"
            "لطفاً نام کاربری (Username) دلخواه خود را برای ادمین پنل بفرست\n(یا /skip برای ساخت خودکار)!",
            ikb(_cancel_row()),
        )
        return

    if data.startswith("paybal:"):
        tid = int(data[7:])
        t = q_one("SELECT * FROM tariffs WHERE id=?", (tid,))
        if not t:
            send_or_edit(chat_id, "تعرفه نامعتبر.")
            return
        if get_balance(chat_id) < float(t["price"]):
            send_or_edit(chat_id, "موجودی کافی نیست.")
            return
        st_set(chat_id, {"await": "buy_custom_username", "tid": tid})
        send_or_edit(
            chat_id,
            f"👤 <b>انتخاب نام کاربری</b>\n\nتعرفه: {esc(t['title'])}\n\n"
            "لطفاً نام کاربری (Username) دلخواه خود را برای ادمین پنل بفرست\n(یا /skip برای ساخت خودکار)!",
            ikb(_cancel_row()),
        )

def handle_buy_custom_username(chat_id: int, text: str) -> None:
    if text == "🏠 بازگشت به منوی اصلی":
        st_pop(chat_id)
        send_or_edit(chat_id, "🏠 بازگشتید!", main_menu_kb(is_admin(chat_id)))
        return
    st = st_all(chat_id)
    st_pop(chat_id)
    pid, tid = int(st.get("pid") or 0), int(st.get("tid") or 0)
    if pid:
        item = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
        pname = str(item["panel_name"]) if item else None
    else:
        item = q_one("SELECT * FROM tariffs WHERE id=?", (tid,))
        pname = None
    if not item:
        send_or_edit(chat_id, "آیتم نامعتبر.")
        return

    if text.lower() == "/skip":
        uname = gen_username("ag")
    else:
        uname = text.strip()
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{3,15}$", uname):
            st_set(chat_id, st)
            send_or_edit(chat_id, "❌ نام کاربری نامعتبر! (فقط حروف و اعداد، شروع با حرف، ۴ تا ۱۶ کاراکتر).")
            return

    panels = get_panels()
    if pname and pname in panels:
        d = panels[pname]
    else:
        d = panels.get(str(get_setting("selected_panel", "") or "")) or (next(iter(panels.values())) if panels else None)
    if not d:
        st_set(chat_id, st)
        send_or_edit(chat_id, "❌ پنل یافت نشد.")
        return
    p = panel_client(d.get("base_url"), d.get("ptype"))
    if not p:
        st_set(chat_id, st)
        send_or_edit(chat_id, "❌ خطا در اتصال به پنل.")
        return

    res = panel_call(p, "list_admins", {}) or {}
    if res.get("ok") and isinstance(res.get("data"), list):
        for a in res["data"]:
            if str(a.get("username", "")).lower() == uname.lower():
                st_set(chat_id, st)
                send_or_edit(chat_id, f"❌ نام کاربری <code>{esc(uname)}</code> قبلاً در پنل رزرو شده. یکی دیگه بفرست!")
                return

    pay = int(item["price"])
    bp2 = st.get("buy_plan") or {}
    if bp2.get("pid") == pid and bp2.get("discount") and 0 <= int(bp2.get("price") or 0) < int(item["price"]):
        pay = int(bp2["price"])
    if not spend_balance(chat_id, pay):
        st_pop(chat_id)
        send_or_edit(chat_id, "❌ موجودی کافی نیست.")
        return
    disc = bp2.get("discount") or {}
    if disc.get("did") and disc.get("code"):
        # Atomic check-and-increment to prevent spam/concurrent usage exceeding max_uses
        cur = ex("UPDATE discount_codes SET used=used+1 WHERE id=? AND (max_uses=0 OR used < max_uses) AND active=1", (int(disc["did"]),))
        if cur.rowcount == 0:
            add_balance(chat_id, pay)
            st_set(chat_id, st)
            send_or_edit(chat_id, "❌ ظرفیت استفاده از این کد تخفیف به پایان رسیده است. مبلغ به کیف پولت برگشت خورد.")
            return

    pwd = strong_password()
    res = panel_create_admin(p, uname, pwd, float(item["volume_gb"]), chat_id)
    if not res.get("ok"):
        add_balance(chat_id, pay)
        err = res.get("error") or "create failed"
        if disc.get("did"):
            ex("UPDATE discount_codes SET used = MAX(0, used - 1) WHERE id=?", (int(disc["did"]),))
        st_set(chat_id, st)
        send_or_edit(chat_id, "❌ خطا در ساخت پنل. مبلغ برگشت خورد. دوباره تلاش کن.")
        notify_admins(
            f"⚠️ <b>خطای ساخت سرویس اصلی (پرداخت شده)</b>\n"
            f"👤 کاربر: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n"
            f"📦 یوزرنیم درخواستی: <code>{esc(uname)}</code>\n"
            f"❗️ خطا: <code>{esc(str(err))}</code>"
        )
        return
    if (res.get("data") or {}).get("password_used"):
        pwd = res["data"]["password_used"]

    st_pop(chat_id)
    ex("INSERT INTO purchases(tg_id,tariff_id,panel_username,volume_gb,price,status) VALUES(?,?,?,?,?,?)",
       (chat_id, tid or -1, uname, float(item["volume_gb"]), pay, "active"))
    ex("DELETE FROM pending_buys WHERE tg_id=?", (chat_id,))
    ex("INSERT INTO agent_panels(tg_id,panel_username,panel_password,panel_name,panel_type,quota_gb) VALUES(?,?,?,?,?,?)",
       (chat_id, uname, panel_encrypt_pw(pwd), p["base_url"], p.get("ptype", "pasarguard"), float(item["volume_gb"])))
    url = panel_login_url(p["base_url"])
    report_purchase(chat_id, uname, f"{fmt_gb(item['volume_gb'])} گیگ — {num(item['price'])} تومان", pay, "خرید", url)
    send_or_edit(
        chat_id,
        "✅ <b>خرید و ساخت پنل با موفقیت انجام شد!</b>\n\n"
        f"🌐 آدرس ورود: <code>{esc(url)}</code>\n👤 نام کاربری: <code>{esc(uname)}</code>\n"
        f"🔑 رمز عبور: <code>{esc(pwd)}</code>\n\n📦 سهمیه: {fmt_gb(item['volume_gb'])} گیگ\n"
        f"💵 کسر شده از کیف پول: {fmt_price(pay)}",
        main_menu_kb(is_admin(chat_id)),
    )

def handle_buy_discount_code(chat_id: int, text: str) -> None:
    st = st_all(chat_id)
    st_pop(chat_id)
    code = text.strip()
    dc = q_one(
        "SELECT * FROM discount_codes WHERE UPPER(code)=UPPER(?) AND active=1 AND (max_uses=0 OR used < max_uses)"
        " AND (expires_at IS NULL OR expires_at = '' OR expires_at > datetime('now','localtime'))", (code,))
    if not dc:
        st_set(chat_id, st)
        send_or_edit(chat_id, "❌ کد تخفیف نامعتبر است. دوباره بفرست یا /cancel!")
        return
    bp = dict(st.get("buy_plan") or {})
    price = int(bp.get("orig_price") or bp.get("price") or 0)
    if str(dc["kind"]) == "percent":
        new_price = int(round(price * (1 - float(dc["value"]) / 100)))
    else:
        new_price = max(0, price - int(dc["value"]))
    bp["price"] = new_price
    bp["discount"] = {"did": int(dc["id"]), "code": code}
    st["buy_plan"] = bp
    st_set(chat_id, st)
    send_or_edit(chat_id, "✅ کد تخفیف اعمال شد.\n💵 مبلغ نهایی: " + fmt_price(new_price) + ".")

def _keep_xp_and_clear(chat_id: int) -> None:
    keep = {}
    if str(st_get(chat_id, "xp_kind", "")) == "extragb":
        keep = {"xp_kind": "extragb", "xp_gb": st_get(chat_id, "xp_gb"), "xp_price": st_get(chat_id, "xp_price"),
                "xp": st_get(chat_id, "xp"), "pid": st_get(chat_id, "pid"), "await": "idle"}
    st_pop(chat_id)
    if keep:
        st_set(chat_id, keep)

def receipt_review_kb(rid: int) -> InlineKeyboardMarkup:
    return ikb([InlineKeyboardButton("⚡ تایید با همان مبلغ", callback_data=f"rcok:{rid}", style="success"), InlineKeyboardButton("✏️ ویرایش مبلغ و تایید", callback_data=f"rcfix:{rid}", style="success")],
               [InlineKeyboardButton("❌ رد درخواست", callback_data=f"rcno:{rid}")])

def handle_wallet_receipt_text(chat_id: int, text: str) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    if not amount:
        st_pop(chat_id)
        st_set(chat_id, {"await": "topup_amount"})
        send_or_edit(chat_id, "❌ مبلغ شارژ مشخص نیست. اول مبلغ را بفرست (مثلاً: 100000)!")
        return
    _keep_xp_and_clear(chat_id)
    ref = text.strip()
    if len(ref) >= 20 and receipt_ref_exists(ref):
        send_or_edit(chat_id, "⛔️ این TXID قبلاً ثبت شده است — هر تراکنش فقط یک‌بار قابل استفاده است.")
        return
    rid = create_receipt(chat_id, amount, "topup | " + text[:200])
    send_or_edit(chat_id, "✅ رسید شارژ ثبت شد و در انتظار تایید ادمین است.", main_menu_kb(is_admin(chat_id)))
    notify_admins(
        f"💳 رسید شارژ کیف پول #{rid}\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n"
        f"مبلغ: {fmt_price(amount)}\nکد/پیگیری: <code>{esc(text[:200])}</code>",
        receipt_review_kb(rid),
    )

def handle_wallet_receipt_photo(chat_id: int, m: dict) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    if not amount:
        st_pop(chat_id)
        st_set(chat_id, {"await": "topup_amount"})
        send_or_edit(chat_id, "❌ مبلغ شارژ مشخص نیست. اول مبلغ را بفرست (مثلاً: 100000)!")
        return
    _keep_xp_and_clear(chat_id)
    fid = (m.get("photo") or [{}])[-1].get("file_unique_id", "photo")
    rid = create_receipt(chat_id, amount, f"topup | photo:{fid}")
    send_or_edit(chat_id, "✅ رسید شارژ ثبت شد و در انتظار تایید ادمین است.", main_menu_kb(is_admin(chat_id)))
    for aid in admin_ids():
        tg("copyMessage", {"chat_id": aid, "from_chat_id": chat_id, "message_id": m["message_id"]})
    notify_admins(
        f"💳 رسید شارژ کیف پول #{rid} (عکس)\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\nمبلغ: {fmt_price(amount)}",
        receipt_review_kb(rid),
    )

def handle_agent_gb(chat_id: int, text: str) -> None:
    st = st_all(chat_id)
    st_pop(chat_id)
    pid, xp, xmin = int(st.get("pid") or 0), int(st.get("xp") or 0), int(st.get("xmin") or 1)
    if q_val("SELECT is_test FROM agent_panels WHERE id=? AND tg_id=?", (pid, chat_id)):
        send_or_edit(chat_id, "⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.")
        return
    m = re.search(r"(\d+)", text.replace(",", ""))
    if not m:
        send_or_edit(chat_id, "عدد معتبر بفرست!")
        return
    gb = int(m.group(1))
    if gb < xmin:
        st_set(chat_id, st)
        send_or_edit(chat_id, f"⚖️ حداقل خرید حجم اضافه {xmin} گیگ است. عدد بزرگ‌تری بفرست!")
        return
    price = gb * xp
    bal = get_balance(chat_id)
    deficit = max(price - bal, 0)
    st_set(chat_id, {"await": "idle", "xp_kind": "extragb", "xp_gb": gb, "xp_price": price, "xp": xp, "pid": pid,
                     "xg_deficit": deficit})
    send_or_edit(
        chat_id,
        "🧾 <b>فاکتور حجم اضافه</b>\n\n"
        f"📦 حجم درخواستی: {gb} گیگ\n💰 مبلغ فاکتور: {num(price)} تومان\n💵 موجودی کیف پول: {fmt_price(bal)}\n"
        + (f"💳 قابل پرداخت (تفاضل): {fmt_price(deficit)}" if deficit > 0 else "✅ پوشش کامل از موجودی کیف پول."),
        ikb([InlineKeyboardButton("✅ تایید فاکتور", callback_data=f"xgpay:{pid}:{gb}:{price}", style="success")], [InlineKeyboardButton("❌ لغو فاکتور", callback_data="xgcancel", style="danger")]),
    )

def extra_gb_invoice_confirm(chat_id: int, pid: int, gb: int, price: int) -> None:
    st = st_all(chat_id)
    if st.get("xp_kind") != "extragb" or int(st.get("xp_gb") or 0) != gb or int(st.get("xp_price") or 0) != price:
        send_or_edit(chat_id, "⌛️ فاکتور منقضی شد — دوباره از صفحهٔ سرویس شروع کن.")
        return
    deficit = max(price - get_balance(chat_id), 0)
    if deficit > 0:
        st_set(chat_id, {"await": "wallet_card", "amount": deficit})
        wallet_card_sent(chat_id)
    else:
        st_pop(chat_id)
        if not spend_balance(chat_id, price):
            send_or_edit(chat_id, "❌ خطا در کسر موجودی.")
            return
        complete_extra_gb(chat_id, gb, pid, int(st.get("xp") or 0), price)

def extra_gb_invoice_cancel(chat_id: int) -> None:
    st_pop(chat_id)
    send_or_edit(chat_id, "❌ فاکتور لغو شد.", main_menu_kb(is_admin(chat_id)))

def complete_extra_gb(chat_id: int, gb: int, pid: int, xp: int, price: int) -> None:
    s = _get_service(chat_id, pid)
    if not s:
        add_balance(chat_id, price)
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    if s["is_test"]:
        add_balance(chat_id, price)
        send_or_edit(chat_id, "⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.")
        return
    p = panel_client(s["panel_name"], s["panel_type"] or None)
    cur_limit = 0
    if p:
        mine = _find_admin(p, s["panel_username"])
        if mine:
            cur_limit = int(mine.get("data_limit") or 0)
    new_limit = cur_limit + gb * 1024 ** 3
    ok = False
    if p:
        ok = bool((panel_call(p, "modify_admin_data_limit", {"username": s["panel_username"], "data_limit": new_limit}) or {}).get("ok"))
    if not ok:
        add_balance(chat_id, price)
        send_or_edit(chat_id, "❌ افزایش سهمیه روی پنل ناموفق بود. مبلغ برگشت خورد.")
        return
    ex("UPDATE agent_panels SET quota_gb = quota_gb + ? WHERE id=?", (gb, pid))
    wmap = get_setting("quota_warned", {}) or {}
    if isinstance(wmap, dict) and wmap.get(str(pid)):
        wmap.pop(str(pid), None)
        set_setting("quota_warned", wmap)
    report_purchase(chat_id, str(s["panel_username"]), f"{gb} گیگ حجم اضافه", price, "افزایش", panel_login_url(str(s["panel_name"])))
    send_or_edit(
        chat_id,
        f"✅ {gb} گیگ به سرویس اضافه شد!\n📦 سهمیه جدید: {round(new_limit / 1024 ** 3)} گیگ\n"
        f"💵 کسر شده: {num(price)} تومان — موجودی جدید: {fmt_price(get_balance(chat_id))}",
        main_menu_kb(is_admin(chat_id)),
    )

def admin_receipts_queue(chat_id: int) -> None:
    recs = q_all("SELECT id, tg_id, amount, ref_text FROM receipts WHERE status='pending' ORDER BY id")
    if not recs:
        send_or_edit(chat_id, "🧾 در انتظار تاییدی نیست.")
        return
    for r in recs:
        tg_send(chat_id, f"#{r['id']} از {r['tg_id']} — {fmt_price(r['amount'])}\n<code>{esc(r['ref_text'])}</code>",
                receipt_review_kb(r["id"]))

def handle_receipt_review(chat_id: int, data: str) -> None:
    rid = int(data.split(":")[1])
    approve = data.startswith("rcok")
    rec = q_one("SELECT * FROM receipts WHERE id=?", (rid,))
    if not rec or rec["status"] != "pending":
        send_or_edit(chat_id, "قبلا پردازش شده.")
        return
    cur = ex("UPDATE receipts SET status=? WHERE id=? AND status='pending'", ("approved" if approve else "rejected", rid))
    if cur.rowcount == 0:
        send_or_edit(chat_id, "قبلا پردازش شده.")
        return
    uid = int(rec["tg_id"])
    if not approve:
        tg_send(uid, "❌ رسید شما رد شد. برای بررسی با پشتیبانی در تماس باش.")
        send_or_edit(chat_id, f"❌ رسید #{rid} رد شد.")
        return
    add_balance(uid, int(rec["amount"]))
    send_or_edit(chat_id, f"✅ رسید #{rid} تایید شد و {fmt_price(rec['amount'])} به کیف پول کاربر اضافه شد.")
    tg_send(uid, f"✅ پرداخت {fmt_price(rec['amount'])} تایید و به موجودی‌ات اضافه شد.")
    xst = st_all(uid)
    if xst.get("xp_kind") == "extragb" and xst.get("xp_gb"):
        st_pop(uid)
        xprice = int(xst.get("xp_price") or 0)
        if xprice > 0 and not spend_balance(uid, xprice):
            tg_send(uid, "⚠️ موجودی برای تکمیل خرید حجم اضافه کافی نشد — مبلغ در کیف پولت باقی ماند. دوباره تلاش کن.")
            return
        complete_extra_gb(uid, int(xst["xp_gb"]), int(xst.get("pid") or 0), int(xst.get("xp") or 0), xprice)
        return
    if str(rec["ref_text"] or "").startswith("topup"):
        b = q_one("SELECT * FROM pending_buys WHERE tg_id=? ORDER BY id DESC LIMIT 1", (uid,))
        if b and b["pid"]:
            prow = q_one("SELECT * FROM panel_plans WHERE id=?", (int(b["pid"]),))
            if prow and get_balance(uid) >= float(prow["price"]):
                st_set(uid, {"buy_plan": {"pid": int(prow["id"]), "gb": float(prow["volume_gb"]),
                                          "price": int(prow["price"]), "orig_price": int(prow["price"])}})
                tg_send(uid, "✅ موجودی کافی شد. برای پرداخت و ساخت آنی پنل بزن!",
                        ikb([InlineKeyboardButton(f"✅ پرداخت از موجودی کیف پول ({num(prow['price'])} تومان)", callback_data=f"paybalplan:{prow['id']}", style="success")]))

def receipt_fix_start(chat_id: int, rid: int) -> None:
    st_set(chat_id, {"await": f"rcfix:{rid}"})
    send_or_edit(chat_id, "✏️ مبلغ صحیح رسید را به تومان بفرست (تایید با این مبلغ انجام می‌شود)!")

def receipt_fix_apply(chat_id: int, text: str) -> None:
    rid = int(str(st_get(chat_id, "await", ""))[6:] or 0)
    st_pop(chat_id)
    clean = int(re.sub(r"[^\d]", "", text.replace(",", "")) or 0)
    if not clean:
        send_or_edit(chat_id, "❌ فقط عدد بفرست!")
        st_set(chat_id, {"await": f"rcfix:{rid}"})
        return
    ex("UPDATE receipts SET amount=? WHERE id=?", (clean, rid))
    handle_receipt_review(chat_id, f"rcok:{rid}")

def build_full_stats() -> str:
    users = q_all("SELECT COALESCE(balance,0) b FROM users")
    total_users = len(users)
    total_bal = sum(int(u["b"]) for u in users)
    buys = q_all("SELECT tg_id, price, status, tariff_id, panel_username, created_at FROM purchases")
    recs = q_all("SELECT amount, status, ref_text FROM receipts WHERE status='approved'")
    total_sales = len(buys)
    active_sales = sum(1 for b in buys if b.get("status") == "active")
    sum_sales = sum(int(b.get("price") or 0) for b in buys)
    sum_active = sum(int(b.get("price") or 0) for b in buys if b.get("status") == "active")
    buyers = len({int(b["tg_id"]) for b in buys})
    conv = (buyers / total_users * 100) if total_users else 0.0
    avg_buy = (sum_sales / total_sales) if total_sales else 0
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    m_sales = sum(int(b.get("price") or 0) for b in buys if str(b.get("created_at") or "") >= since)
    per_user: dict = {}
    for b in buys:
        k = f"{b['tg_id']}:{b['tariff_id']}"
        per_user[k] = per_user.get(k, 0) + 1
    renews = sum(v - 1 for v in per_user.values() if v > 1)
    renew_pct = (renews / total_sales * 100) if total_sales else 0.0
    gw_stat: dict = {}
    for r in recs:
        ref = str(r.get("ref_text") or "")
        gw = "wallet" if ref.startswith("topup") else "buy" if ref.startswith("buy:") else "other"
        gw_stat.setdefault(gw, {"n": 0, "sum": 0})
        gw_stat[gw]["n"] += 1
        gw_stat[gw]["sum"] += int(r.get("amount") or 0)
    labels = {"card": "💳 کارت به کارت", "wallet": "🏦 شارژ کیف پول", "buy": "🛒 خرید مستقیم", "other": "📄 سایر"}
    L = [
        "📊 آمار کلی ربات", "━━━━━━━━━━━━━━━━━━",
        f"👥 تعداد کل کاربران: {total_users} نفر",
        f"💳 کاربران دارای خرید: {buyers} نفر",
        f"💰 موجودی کل کاربران: {num(total_bal)} تومان", "",
        f"🧾 تعداد کل فروش: {total_sales} عدد",
        f"🧾 تعداد کل فروش سرویس های فعال: {active_sales} عدد",
        f"💵 جمع کل فروش : {num(sum_sales)} تومان",
        f"💵 جمع کل فروش سرویس های فعال: {num(sum_active)} تومان",
        f"📈 نرخ تبدیل به مشتری: {conv:,.2f}٪",
        f"💳 میانگین خرید هر مشتری: {avg_buy:,.0f} تومان",
        f"📅 درآمد پیش‌بینی‌شده ماهانه: {num(m_sales)} تومان",
        f"📊 درصد تمدید از فروش: {renew_pct:,.2f}٪", "",
        f"🧩 تعداد پنل‌ها: {len(get_panels())} عدد",
    ]
    if gw_stat:
        L.append("")
        for g, s in gw_stat.items():
            L.append(f"\n📌 نام درگاه : {labels.get(g, g)}\n - تعداد پرداخت موفق : {s['n']}\n - جمع پرداختی ها : {num(s['sum'])}")
    return "\n".join(L)

def admin_stats(chat_id: int) -> None:
    t0 = time.time()
    try:
        txt = build_full_stats()
    except Exception as e:
        txt = "⚠️ خطا در آمار: " + str(e)[:150]
    txt += f"\n📡 پینگ ربات: {int((time.time() - t0) * 1000)} میلی‌ثانیه"
    send_or_edit(chat_id, txt, ikb([InlineKeyboardButton("◀️ بازگشت به پنل مدیریت", callback_data="adm:back")]))

def admin_tickets(chat_id: int) -> None:
    rows = q_all("SELECT * FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 10")
    kb = []
    for t in rows:
        kb.append([InlineKeyboardButton(f"#{t['id']} — {str(t['message'])[:28]}…", callback_data=f"um:{t['tg_id']}")])
        kb.append([InlineKeyboardButton(f"✅ بستن تیکت #{t['id']}", callback_data=f"tkclose:{t['id']}")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:users")])
    txt = (f"🎫 <b>تیکت‌های باز:</b> {len(rows)}\nروی تیکت بزن تا پروفایل کاربر باز شود!" if rows else "🎫 <b>تیکت‌های باز:</b> هیچ")
    send_or_edit(chat_id, txt, InlineKeyboardMarkup(kb))

def admin_ticket_close(chat_id: int, tid: int) -> None:
    if q_one("SELECT 1 FROM tickets WHERE id=?", (tid,)):
        ex("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        send_or_edit(chat_id, "تیکت بسته شد.")

def admin_guide_home(chat_id: int) -> None:
    kb = []
    for t in q_all("SELECT * FROM guide_topics ORDER BY id"):
        kb.append([InlineKeyboardButton(f"✏️ {t['title']}", callback_data=f"helpedit:{t['id']}"), InlineKeyboardButton(f"🗑 {t['title']}", callback_data=f"helpdel:{t['id']}")])
    kb.append([InlineKeyboardButton("➕ افزودن راهنما", callback_data="helpadd", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "📚 مدیریت راهنما:\n✏️ = ویرایش متن | 🗑 = حذف", InlineKeyboardMarkup(kb))

def admin_help_add(chat_id: int) -> None:
    st_set(chat_id, {"await": "helpadd_title"})
    send_or_edit(chat_id, "📚 عنوان آموزش را بفرست!")

def admin_help_edit(chat_id: int, tid: int) -> None:
    t = q_one("SELECT * FROM guide_topics WHERE id=?", (tid,))
    if not t:
        send_or_edit(chat_id, "آموزش یافت نشد.")
        return
    st_set(chat_id, {"await": f"helpedit_body:{tid}"})
    send_or_edit(chat_id, f"✏️ ویرایش آموزش «{esc(t['title'])}»\n\n📄 متن فعلی:\n{esc(str(t['content'])[:2500])}\n\n✍️ متن جدید را بفرست!", cancel_kb())

def admin_help_delete(chat_id: int, tid: int) -> None:
    ex("DELETE FROM guide_topics WHERE id=?", (tid,))
    admin_guide_home(chat_id)

def admin_help_title_apply(chat_id: int, text: str) -> None:
    st_set(chat_id, {"await": "helpadd_body", "htitle": text.strip()})
    send_or_edit(chat_id, "📚 توضیحات آموزش را بفرست (متن/لینک/فیلم)!")

def admin_help_body_apply(chat_id: int, text: str) -> None:
    title = str(st_get(chat_id, "htitle", "آموزش"))
    st_pop(chat_id)
    ex("INSERT INTO guide_topics(title, content) VALUES(?,?)", (title, text))
    send_or_edit(chat_id, f"✅ آموزش «{esc(title)}» اضافه شد.")

def admin_help_body_edit(chat_id: int, await_: str, text: str) -> None:
    tid = int(await_[len("helpedit_body:"):])
    st_pop(chat_id)
    ex("UPDATE guide_topics SET content=? WHERE id=?", (text, tid))
    t = q_one("SELECT title FROM guide_topics WHERE id=?", (tid,))
    send_or_edit(chat_id, f"✅ آموزش «{esc((t or {}).get('title', '?'))}» به‌روزرسانی شد.")

FEATURE_ITEMS = [("buy", "🛒 خرید"), ("topup", "💰 شارژ موجودی"), ("manage", "👤 مدیریت سرویس"),
                 ("gift", "🎁 هدیه/کد تخفیف"), ("guide", "📡 راهنمای اتصال"), ("faq", "❓ سوالات متداول")]

def admin_features_home(chat_id: int) -> None:
    feats = features()
    rows = []
    for i in range(0, len(FEATURE_ITEMS), 2):
        rows.append([InlineKeyboardButton(("✅" if feats.get(k, True) else "⛔️") + " " + label, callback_data=f"feat:{k}") for k, label in FEATURE_ITEMS[i:i + 2]])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🛠 <b>قابلیت‌های پنل</b>", InlineKeyboardMarkup(rows))

def admin_feature_toggle(chat_id: int, key: str) -> None:
    feats = features()
    feats[key] = not feats.get(key, True)
    set_setting("features", feats)
    admin_features_home(chat_id)

def admin_settings_home(chat_id: int) -> None:
    send_or_edit(chat_id, "🏬 <b>تنظیمات فروشگاه</b>", ikb(
        [InlineKeyboardButton("⚙️ تنظیمات پنل", callback_data="adm:general")], [InlineKeyboardButton("⚙️ تنظیمات عمومی", callback_data="adm:shopgeneral")],
        [InlineKeyboardButton("⚙️ تنظیمات پرداخت", callback_data="adm:payments")],
        [InlineKeyboardButton("🎨 تنظیمات ظاهر", callback_data="adm:appearance")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")]))

def admin_general_home(chat_id: int) -> None:
    s = all_settings()
    tl = int(s.get("test_limit", 1) or 1)
    wpct, wd = s.get("quota_warn_pct", 80), s.get("quota_warn_discount_pct", 10)
    usd = int(s.get("usd_rate", 220000) or 220000)
    mn = int(get_setting("min_charge", 0) or 0) or "خاموش"
    mx = int(get_setting("max_charge", 0) or 0) or "خاموش"
    send_or_edit(chat_id, "⚙️ <b>تنظیمات پنل</b>", ikb(
        [InlineKeyboardButton(f"🧪 تعداد تست هر کاربر: {tl}", callback_data="set:testlimit")],
        [InlineKeyboardButton(f"💳 حداقل واریز: {mn} تومان", callback_data="set:min_charge"), InlineKeyboardButton(f"💳 حداکثر واریز: {mx} تومان", callback_data="set:max_charge")],
        [InlineKeyboardButton(f"⚠️ درصد هشدار حجم: {wpct}٪", callback_data="set:quota_warn_pct"), InlineKeyboardButton(f"🎁 تخفیف هشدار: {wd}٪", callback_data="set:quota_warn_discount_pct")],
        [InlineKeyboardButton(f"💲 نرخ دلار: {usd:,} تومان (دستی)", callback_data="set:usd_rate")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:settings")]))

def admin_shopgeneral_home(chat_id: int) -> None:
    s = all_settings()
    fj = "✅ فعال" if s.get("force_join") else "⛔️ خاموش"
    rg = "ثبت شده ✅" if s.get("report_group") else "ثبت نشده ❌"
    send_or_edit(chat_id, "⚙️ <b>تنظیمات عمومی</b>", ikb(
        [InlineKeyboardButton(f"🔒 عضویت اجباری: {fj}", callback_data="set:force_join", style="success"), InlineKeyboardButton("📢 کانال‌های اجباری", callback_data="set:channels")],
        [InlineKeyboardButton("📝 متن شروع", callback_data="set:start_text")],
        [InlineKeyboardButton("📝 متن رد رسید", callback_data="set:reject_text"), InlineKeyboardButton("⚠️ هشدار اتمام حجم", callback_data="set:quota_warn_text")],
        [InlineKeyboardButton("🗑 اطلاع‌رسانی حذف", callback_data="set:autoremove_text", style="danger"), InlineKeyboardButton("❓ متن سوالات متداول", callback_data="set:faq_text")],
        [InlineKeyboardButton("📝 متن ضوابط و مقررات خرید", callback_data="set:nonrefund_text"), InlineKeyboardButton("✅ متن شرایط و توضیحات", callback_data="set:conditions_text")],
        [InlineKeyboardButton("📡 راهنمای اتصال", callback_data="adm:guides")],
        [InlineKeyboardButton(f"📣 کانال گزارشات: {rg}", callback_data="set:report_group")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:settings")]))

def admin_power_home(chat_id: int) -> None:
    send_or_edit(chat_id, "🔌 <b>خاموش/روشن</b>\nبخش‌ها را باز/بسته کن!", ikb(
        [InlineKeyboardButton("🛒 فروش: " + ("🟢 باز" if feat_on("buy", True) else "🔴 بسته"), callback_data="pw:buy"),
         InlineKeyboardButton("🧪 تست: " + ("🟢 باز" if feat_on("test", True) else "🔴 بسته"), callback_data="pw:test")],
        [InlineKeyboardButton("🤖 ربات: " + ("🟢 روشن" if bot_enabled() else "🔴 خاموش"), callback_data="pw:bot")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")]))

def admin_power_toggle(chat_id: int, key: str) -> None:
    if key == "bot":
        set_setting("bot_enabled", 0 if bot_enabled() else 1)
    else:
        f = features()
        f[key] = not feat_on(key, True)
        set_setting("features", f)
    admin_power_home(chat_id)

SET_PROMPTS = {
    "start_text": "📝 متن پیام /start را بفرست (متغیرهای {name} و {username} مجازند):",
    "reject_text": "📝 متن رد رسید را بفرست:", "quota_warn_text": "⚠️ متن هشدار اتمام حجم را بفرست:",
    "autoremove_text": "🗑 متن اطلاع‌رسانی حذف را بفرست:", "faq_text": "❓ متن سوالات متداول را بفرست:",
    "nonrefund_text": "📝 متن ضوابط و مقررات خرید را بفرست:", "conditions_text": "✅ متن شرایط و توضیحات را بفرست:",
    "report_group": "📣 آیدی کانال گزارشات را بفرست (مثل @mychannel یا -100...):",
    "testlimit": "🧪 تعداد تست هر کاربر را بفرست:", "quota_warn_pct": "⚠️ درصد هشدار حجم را بفرست (مثلاً 90):",
    "quota_warn_discount_pct": "🎁 درصد تخفیف هشدار را بفرست (مثلاً 10)!", "card_number": "💳 شماره کارت را بفرست:",
    "card_owner": "👤 نام صاحب کارت را بفرست:", "usd_rate": "💲 نرخ دلار (تومان) را بفرست:",
    "tron_wallet": "💼 آدرس ولت ترون را بفرست:", "min_charge": "💳 حداقل واریز را بفرست (تومان):",
    "max_charge": "💳 حداکثر واریز را بفرست (تومان):",
}
TXT_KEYS = {"start_text", "reject_text", "quota_warn_text", "autoremove_text", "faq_text", "nonrefund_text",
            "conditions_text", "report_group", "card_number", "card_owner", "tron_wallet"}
NUMERIC_KEYS = {"usd_rate", "min_charge", "max_charge", "quota_warn_pct", "quota_warn_discount_pct", "testlimit"}

def admin_set_prompt(chat_id: int, key: str) -> None:
    st_set(chat_id, {"await": f"set:{key}"})
    prompt = SET_PROMPTS.get(key, f"مقدار جدید برای {key} را بفرست:")
    preview = ""
    if key in TXT_KEYS:
        cur = str(get_setting(key, "") or "")
        preview = ("\n\n📌 مقدار فعلی:\n" + cur[:400]) if cur else "\n\n📌 متنی تنظیم نشده — پیش‌فرض ربات استفاده می‌شود."
    send_or_edit(chat_id, prompt + preview, cancel_kb())

def admin_set_cancel(chat_id: int) -> None:
    st_pop(chat_id)
    send_or_edit(chat_id, "↩️ ویرایش لغو شد.")
    admin_shopgeneral_home(chat_id)

def admin_set_apply(chat_id: int, key: str, text: str) -> bool:
    if key in NUMERIC_KEYS:
        clean = text.strip().replace(",", "")
        if not re.match(r"^-?\d+(\.\d+)?$", clean) or float(clean) < 0:
            send_or_edit(chat_id, "❌ فقط عدد مثبت بفرست (مثلاً 220000 یا 220,000)!")
            return False
        set_setting("test_limit" if key == "testlimit" else key, float(clean) if "." in clean else int(clean))
        send_or_edit(chat_id, "✅ ذخیره شد.")
        return True
    set_setting(key, text)
    send_or_edit(chat_id, "✅ ذخیره شد.")
    return True

def admin_channels_home(chat_id: int) -> None:
    kb = [[InlineKeyboardButton(f"❌ {c['channel_id']}", callback_data="delchan:" + urllib.parse.quote_plus(str(c["channel_id"])))] for c in
          q_all("SELECT * FROM channels ORDER BY id")]
    kb.append([InlineKeyboardButton("➕ افزودن @کانال", callback_data="addchan", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:shopgeneral")])
    send_or_edit(chat_id, "📢 کانال‌های اجباری:", InlineKeyboardMarkup(kb))

def admin_channel_delete(chat_id: int, cid: str) -> None:
    ex("DELETE FROM channels WHERE channel_id=?", (cid,))
    admin_channels_home(chat_id)

def admin_channel_add_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "addchan"})
    send_or_edit(chat_id, "📢 آیدی کانال را بفرست (@id یا -100...)!")

def admin_channel_add_apply(chat_id: int, text: str) -> None:
    st_pop(chat_id)
    ch = text.strip()
    if not ch:
        send_or_edit(chat_id, "❌ آیدی معتبر بفرست!")
        return
    if ch[0] not in "@-":
        ch = "@" + ch
    ex("INSERT INTO channels(channel_id, title) VALUES(?,?)", (ch, ""))
    send_or_edit(chat_id, "✅ کانال اضافه شد.")

PAY_METHODS = {
    "card": {"label": "💳 کارت به کارت", "api_key": None},
    "tron": {"label": "💵 ترون (ارزی)", "api_key": "wallet_address", "api_prompt": "💼 آدرس ولت ترون (TRC20) را بفرست:"},
    "zarinpal": {"label": "🟡 زرین‌پال", "api_key": "zarinpal_api", "api_prompt": "🔑 API مرچنت زرین‌پال را بفرست:"},
    "aqayepardakht": {"label": "🔵 آقای پرداخت", "api_key": "aqayepardakht_api", "api_prompt": "🔑 کد API آقای پرداخت را بفرست:"},
}

def pay_onoff(key: str) -> str:
    return "✅ روشن" if get_setting(f"pay_{key}", 1 if key == "card" else 0) else "⛔️ خاموش"

def admin_payments_home(chat_id: int) -> None:
    rows = [[InlineKeyboardButton(f"{m['label']}: {pay_onoff(k)}", callback_data=f"paytoggle:{k}"), InlineKeyboardButton("⚙️", callback_data=f"paycfg:{k}")] for k, m in PAY_METHODS.items()]
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:settings")])
    send_or_edit(chat_id, "⚙️ <b>تنظیمات پرداخت</b>\n\nروشن/خاموش هر روش را با کلیک عوض کن؛ با ⚙️ تنظیمات هر روش (API/ولت) باز می‌شود.",
                 InlineKeyboardMarkup(rows))

def admin_pay_toggle(chat_id: int, key: str, from_cfg: bool = False) -> None:
    if key not in PAY_METHODS:
        send_or_edit(chat_id, "روش نامعتبر.")
        return
    cur = bool(get_setting(f"pay_{key}", 1 if key == "card" else 0))
    set_setting(f"pay_{key}", 0 if cur else 1)
    admin_pay_cfg(chat_id, key) if from_cfg else admin_payments_home(chat_id)

def admin_pay_cfg(chat_id: int, key: str) -> None:
    m = PAY_METHODS.get(key)
    if not m:
        send_or_edit(chat_id, "روش نامعتبر.")
        return
    on = pay_onoff(key)
    rows = [[InlineKeyboardButton("🔌 " + ("خاموش کردن" if on == "✅ روشن" else "روشن کردن"), callback_data=f"paytoggle:{key}:cfg")]]
    if m["api_key"]:
        curv = str(get_setting(m["api_key"], "") or "")
        rows.append([InlineKeyboardButton("🔑 تنظیم API/ولت" + (" (ثبت شده ✅)" if curv else " (ثبت نشده ❌)"), callback_data=f"payapi:{key}")])
        body = f"{m['label']} — وضعیت: {on}\n🔑 API: " + ("ثبت شده ✅" if curv else "ثبت نشده ❌")
    else:
        body = f"{m['label']} — وضعیت: {on}\nبرای این روش تنظیم API لازم نیست."
        if key == "card":
            card, owner = str(get_setting("card_number", "") or ""), str(get_setting("card_owner", "") or "")
            rows.append([InlineKeyboardButton("💳 شماره کارت" + (": " + card[:19] if card else " (ثبت نشده ❌)"), callback_data="set:card_number")])
            rows.append([InlineKeyboardButton("👤 صاحب کارت" + (": " + owner[:20] if owner else " (ثبت نشده ❌)"), callback_data="set:card_owner")])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:payments")])
    send_or_edit(chat_id, body, InlineKeyboardMarkup(rows))

def admin_appearance_home(chat_id: int) -> None:
    s = all_settings()
    bc = s.get("btn_color", "colorful")
    pe = bool(s.get("premium_emoji", 1))

    text = (
        "🎨 <b>تنظیمات ظاهر ربات</b>\n\n"
        "در این بخش می‌توانید ظاهر دکمه‌ها و ایموجی‌های ربات را شخصی‌سازی کنید:\n\n"
        "• <b>رنگ دکمه‌ها:</b> رنگ پیش‌فرض یا رنگارنگ خودکار را انتخاب کنید.\n"
        "• <b>ایموجی پریمیوم:</b> استفاده از ایموجی‌های اختصاصی در منوها."
    )

    kb_rows = [
        [
            InlineKeyboardButton(f"{'✅ ' if bc == 'blue' else ''}آبی 🔵", callback_data="setcol:blue"),
            InlineKeyboardButton(f"{'✅ ' if bc == 'green' else ''}سبز 🟢", callback_data="setcol:green"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if bc == 'red' else ''}قرمز 🔴", callback_data="setcol:red"),
            InlineKeyboardButton(f"{'✅ ' if bc == 'colorful' else ''}رنگارنگ 🎨", callback_data="setcol:colorful"),
        ],
        [
            InlineKeyboardButton(f"استفاده از ایموجی پریمیوم: {'روشن ✅' if pe else 'خاموش ❌'}", callback_data="toggleemoji")
        ],
        [
            InlineKeyboardButton("◀️ بازگشت", callback_data="adm:settings")
        ]
    ]
    send_or_edit(chat_id, text, InlineKeyboardMarkup(kb_rows))

def admin_appearance_setcol(chat_id: int, color: str) -> None:
    if color in ("blue", "green", "red", "colorful"):
        set_setting("btn_color", color)
    admin_appearance_home(chat_id)

def admin_appearance_toggle_emoji(chat_id: int) -> None:
    cur = bool(get_setting("premium_emoji", 1))
    set_setting("premium_emoji", 0 if cur else 1)
    admin_appearance_home(chat_id)

def admin_pay_api_start(chat_id: int, key: str) -> None:
    m = PAY_METHODS.get(key)
    if not m or not m["api_key"]:
        send_or_edit(chat_id, "روش نامعتبر.")
        return
    st_set(chat_id, {"await": f"payapi:{key}"})
    send_or_edit(chat_id, m["api_prompt"])

def admin_pay_api_apply(chat_id: int, text: str) -> None:
    key = str(st_get(chat_id, "await", ""))[7:]
    m = PAY_METHODS.get(key)
    st_pop(chat_id)
    if not m or not m["api_key"]:
        send_or_edit(chat_id, "روش نامعتبر.")
        return
    val = text.strip()
    if len(val) < 8:
        send_or_edit(chat_id, "❌ مقدار خیلی کوتاه است. دوباره بفرست!")
        st_set(chat_id, {"await": f"payapi:{key}"})
        return
    set_setting(m["api_key"], val)
    send_or_edit(chat_id, "✅ ذخیره شد.")

def admin_discounts_home(chat_id: int) -> None:
    rows = []
    for c in q_all("SELECT * FROM discount_codes ORDER BY id DESC"):
        kind = "٪" if c["kind"] == "percent" else "ت"
        rows.append([InlineKeyboardButton(f"🗑 {c['code']} ({c['value']}{kind} — {c['used']}/{c['max_uses'] or '∞'})", callback_data=f"okdel:discount:{c['id']}", style="danger")])
    rows.append([InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="dsc:add", style="success")])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🏷️ <b>کدهای تخفیف</b>\n🗑 = حذف", InlineKeyboardMarkup(rows))

def admin_gifts_home(chat_id: int) -> None:
    rows = []
    for c in q_all("SELECT * FROM gift_codes ORDER BY id DESC"):
        rows.append([InlineKeyboardButton(f"🗑 {c['code']} ({fmt_price(c['amount'])} — {c['used']}/{c['max_uses'] or '∞'})", callback_data=f"okdel:gift:{c['id']}", style="danger")])
    rows.append([InlineKeyboardButton("➕ افزودن کد هدیه", callback_data="gift:add", style="success")])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🎁 <b>کدهای هدیه</b>\n🗑 = حذف", InlineKeyboardMarkup(rows))

def admin_code_add_start(chat_id: int, typ: str) -> None:
    st_set(chat_id, {"await": "dsc_code" if typ == "dsc" else "gift_code"})
    send_or_edit(chat_id, "🏷 کد تخفیف (لاتین، بدون فاصله)!" if typ == "dsc" else "🎁 کد هدیه (لاتین، بدون فاصله)!")

def admin_code_delete(chat_id: int, data: str) -> None:
    parts = data.split(":")
    if parts[1] == "discount":
        ex("DELETE FROM discount_codes WHERE id=?", (int(parts[2]),))
        send_or_edit(chat_id, "کد تخفیف حذف شد.")
    else:
        ex("DELETE FROM gift_codes WHERE id=?", (int(parts[2]),))
        send_or_edit(chat_id, "کد هدیه حذف شد.")

CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{3,32}$")

def admin_dsc_code_apply(chat_id: int, text: str) -> None:
    code = text.strip().replace(" ", "")
    if not CODE_RE.match(code):
        send_or_edit(chat_id, "کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر!")
        return
    st_set(chat_id, {"await": "dsc_value", "dcode": code})
    send_or_edit(chat_id, "💰 مقدار تخفیف را بفرست:\nدرصد: مثلا 20\nمبلغ ثابت تومان: مثلا 50000\n(برای تعیین نوع، پسوند بزن: 20% یا 50000t)!")

def admin_dsc_value_apply(chat_id: int, text: str) -> None:
    v = text.strip()
    if m := re.match(r"^(\d+)\s*%$", v):
        kind, val = "percent", int(m.group(1))
    elif m := re.match(r"^(\d+)\s*t$", v, re.I):
        kind, val = "fixed", int(m.group(1))
    elif re.match(r"^\d+$", v):
        kind, val = "fixed", int(v)
    else:
        send_or_edit(chat_id, "فرمت: 20% یا 50000t یا 50000.")
        return
    code = str(st_get(chat_id, "dcode", ""))
    st_pop(chat_id)
    ex("INSERT OR REPLACE INTO discount_codes(code, kind, value, used) VALUES(?,?,?,0)", (code, kind, val))
    send_or_edit(chat_id, f"✅ کد تخفیف «{code}» ساخته شد ({val}{'%' if kind == 'percent' else ' تومان'}).")

def admin_gift_code_apply(chat_id: int, text: str) -> None:
    code = text.strip().replace(" ", "")
    if not CODE_RE.match(code):
        send_or_edit(chat_id, "کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر!")
        return
    st_set(chat_id, {"await": "gift_amount", "gcode": code})
    send_or_edit(chat_id, "💰 مبلغ هدیه (تومان) را بفرست!")

def admin_gift_amount_apply(chat_id: int, text: str) -> None:
    m = re.search(r"\d+", text.replace(",", ""))
    if not m:
        send_or_edit(chat_id, "عدد بفرست!")
        return
    code = str(st_get(chat_id, "gcode", ""))
    st_pop(chat_id)
    ex("INSERT OR REPLACE INTO gift_codes(code, amount, used) VALUES(?,?,0)", (code, int(m.group(0))))
    send_or_edit(chat_id, f"✅ کد هدیه «{code}» ساخته شد.")

def bcast_home(chat_id: int) -> None:
    send_or_edit(chat_id, "📣 <b>پیام همگانی</b>\nبه کدام گروه ارسال شود؟", ikb(
        [InlineKeyboardButton("👥 همه کاربران", callback_data="bcast2:all", style="primary"), InlineKeyboardButton("🛒 خریدارها", callback_data="bcast2:buyers")],
        [InlineKeyboardButton("🚫 خرید نداشته‌ها", callback_data="bcast2:nonbuyers", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:users")]))

AUD_LABELS = {"all": "همه کاربران", "buyers": "خریدارها", "nonbuyers": "خرید نداشته‌ها"}

def bcast_audience_pick(chat_id: int, aud: str) -> None:
    st_set(chat_id, {"await": "bcast2_text", "bcast_aud": aud})
    send_or_edit(chat_id, f"📣 متن پیام همگانی برای «{AUD_LABELS.get(aud, aud)}» را بفرست!")

def bcast_text_received(chat_id: int, text: str) -> None:
    st_set(chat_id, {"await": "bcast2_btn", "bcast_text": text})
    send_or_edit(chat_id, "📣 زیر پیام همگانی چه دکمه‌ای بگذارم؟", ikb(
        [InlineKeyboardButton("🔐 خرید اشتراک", callback_data="bcastbtn:buy", style="success"), InlineKeyboardButton("🧪 دریافت تست", callback_data="bcastbtn:test", style="primary")],
        [InlineKeyboardButton("☎️ پیام به پشتیبانی", callback_data="bcastbtn:support"), InlineKeyboardButton("📚 آموزش", callback_data="bcastbtn:help")],
        [InlineKeyboardButton("📤 ارسال بدون دکمه", callback_data="bcastbtn:none", style="danger")]))

def bcast_btn_pick(chat_id: int, b: str) -> None:
    if st_all(chat_id).get("await") != "bcast2_btn":
        send_or_edit(chat_id, "پیام یافت نشد — دوباره شروع کن!")
        return
    st_set(chat_id, {"bcast_btn": b})
    send_or_edit(chat_id, "📌 این پیام برای کاربر پین شود؟", ikb([InlineKeyboardButton("📌 بله، پین شود", callback_data="bcastgo:yes", style="success"), InlineKeyboardButton("🚫 خیر", callback_data="bcastgo:no", style="danger")]))

def bcast_run(chat_id: int, pin: bool) -> None:
    st = st_all(chat_id)
    if "bcast_text" not in st:
        send_or_edit(chat_id, "پیام یافت نشد.")
        return
    text, aud, b = str(st["bcast_text"]), str(st.get("bcast_aud", "all")), str(st.get("bcast_btn", "none"))
    st_pop(chat_id)
    if aud == "buyers":
        ids = [r["tg_id"] for r in q_all("SELECT DISTINCT tg_id FROM purchases")]
    elif aud == "nonbuyers":
        ids = [r["tg_id"] for r in q_all("SELECT tg_id FROM users WHERE is_banned=0 AND tg_id NOT IN (SELECT DISTINCT tg_id FROM purchases)")]
    else:
        ids = [r["tg_id"] for r in q_all("SELECT tg_id FROM users")]
    lbl = AUD_LABELS.get(aud, aud)
    btn_map = {"buy": ("🔐 خرید اشتراک", "m:buy"), "test": ("🧪 دریافت تست", "m:test"),
               "support": ("☎️ پیام به پشتیبانی", "m:support"), "help": ("📚 آموزش", "m:help")}
    kb = ikb([InlineKeyboardButton(btn_map[b][0], callback_data=btn_map[b][1], style="success")]) if b in btn_map else None
    total = len(ids)
    if not total:
        send_or_edit(chat_id, f"✅ ارسال تمام شد: 0 نفر ({lbl}).")
        return
    prog = tg_send(chat_id, f"📣 در حال ارسال به {total} نفر ({lbl})…\nارسال: 0.")
    prog_id = int((prog.get("result") or {}).get("message_id") or 0)

    def upd(t: str) -> None:
        if prog_id:
            tg("editMessageText", {"chat_id": chat_id, "message_id": prog_id, "text": t})
        else:
            tg_send(chat_id, t)

    sent = failed = 0
    BATCH = 15
    for i, uid in enumerate(ids, 1):
        time.sleep(0.25)
        resp = tg_send(uid, text, kb)
        ok = bool(resp.get("ok"))
        if not ok:
            time.sleep(0.3)
            resp = tg_send(uid, text, kb)
            ok = bool(resp.get("ok"))
        sent, failed = (sent + 1, failed) if ok else (sent, failed + 1)
        mid = int((resp.get("result") or {}).get("message_id") or 0)
        if pin and ok and mid:
            tg("pinChatMessage", {"chat_id": uid, "message_id": mid, "disable_notification": True})
        if i % BATCH == 0:
            upd(f"📣 در حال ارسال به {total} نفر ({lbl})…\nارسال: {sent} | خطا: {failed}")
            time.sleep(2)
    upd(f"✅ ارسال تمام شد: {sent} نفر ({lbl})" + (f" | ناموفق: {failed}" if failed else "") + (" — پیام پین شد. 📌" if pin else ""))

def admin_users_home(chat_id: int) -> None:
    n = int(q_val("SELECT COUNT(*) FROM users", (), 0))
    send_or_edit(chat_id, f"👥 <b>مدیریت کاربران</b>\n\nتعداد کاربران: {n}\n\nیکی از گزینه‌های زیر را انتخاب کن!", ikb(
        [InlineKeyboardButton("👤 جستجو کاربر", callback_data="adm:finduser"), InlineKeyboardButton("🛍 جستجو سفارش", callback_data="adm:search")],
        [InlineKeyboardButton("💰 شارژ همگانی", callback_data="adm:massbal"), InlineKeyboardButton("📉 کسر همگانی", callback_data="adm:masssub")],
        [InlineKeyboardButton("📣 پیام همگانی", callback_data="adm:bcast")], [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")]))


def admin_finduser_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "finduser"})
    send_or_edit(chat_id, "🔍 آیدی عددی کاربر را بفرست!")

def admin_findorder_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "search_order"})
    send_or_edit(chat_id, "👁‍🗨 برای مشاهده سفارشات کاربر، آیدی عددی یا نام کاربری کانفیگ را ارسال کنید!")

def _svc_pick_kb(rows: list) -> InlineKeyboardMarkup:
    kb = []
    for r in rows:
        stat = "active" if r.get("status") == "active" else "Unsuccessful"
        kb.append([InlineKeyboardButton(f"👤 {r['panel_username']}", callback_data="svcnoop"), InlineKeyboardButton(f"📊 {stat}", callback_data="svcnoop"),
                   InlineKeyboardButton("🔍 مشاهده اطلاعات", callback_data=f"svcview:{r['id']}")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:users")])
    return InlineKeyboardMarkup(kb)

def admin_search_order_apply(chat_id: int, text: str) -> None:
    st_pop(chat_id)
    q = text.strip()
    if not q:
        send_or_edit(chat_id, "❌ آیدی یا نام کاربری را بفرست!")
        return
    rows = q_all("SELECT * FROM agent_panels WHERE tg_id = ? OR panel_username LIKE ? ORDER BY id DESC LIMIT 20",
                 (int(q) if q.isdigit() else -1, f"%{q}%"))
    if not rows:
        send_or_edit(chat_id, "سفارشی یافت نشد.", back_adm_kb())
        return
    if len(rows) == 1:
        admin_svc_view(chat_id, int(rows[0]["id"]))
        return
    send_or_edit(chat_id, "⚠️ بیشتر از یک سرویس یافت شد — از لیست زیر سرویس صحیح را انتخاب کنید:\n\n👤 نام کاربری | 📊 وضعیت سرویس | ⚙️ عملیات",
                 _svc_pick_kb(rows))

def admin_svc_view(chat_id: int, svc_id: int) -> None:
    s = q_one("SELECT * FROM agent_panels WHERE id=?", (svc_id,))
    if not s:
        send_or_edit(chat_id, "سرویس یافت نشد.")
        return
    pur = q_one("SELECT * FROM purchases WHERE panel_username=? ORDER BY id DESC LIMIT 1", (str(s["panel_username"]),))
    order_no = hashlib.md5(str(s["panel_username"]).encode()).hexdigest()[:8]
    loc = str(s["panel_name"])
    for pn, pd in get_panels().items():
        if pd.get("base_url") == loc:
            loc = pn
            break
    price = int(pur["price"]) if pur else 0
    dur = f"{int(pur['months']) * 30} روزه" if pur and pur.get("months") else "—"
    prod = "🧪 سرویس تست" if s["is_test"] else "—"
    if pur:
        prod = f"🇩🇪 نگهداری حساب | یک‌ماهه | {num(price)} تومان ⚡"
    send_or_edit(
        chat_id,
        f"🛒 شماره سفارش : <code>{order_no}</code>\n🛒 وضعیت سفارش در ربات : {s['status']}\n"
        f"🧑 شناسه کاربر : <code>{s['tg_id']}</code>\n👤 نام کاربری اشتراک : <code>{esc(s['panel_username'])}</code>\n"
        f"📍 موقعیت سرویس : {esc(loc)}\n🛍 نام محصول : {prod}\n💰 قیمت پرداختی سرویس : {num(price)} تومان\n"
        f"⚜️ حجم سرویس خریداری شده : {fmt_gb(s['quota_gb'])} گیگابایت\n⏳ زمان سرویس خریداری شده : {dur}\n"
        f"📅 تاریخ خرید : {jdate(s['created_at'])}",
        ikb([InlineKeyboardButton("♻️ بروزرسانی", callback_data=f"svcview:{s['id']}")],
            [InlineKeyboardButton("❌ حذف سفارش", callback_data=f"svcordel:{s['id']}", style="danger"), InlineKeyboardButton("❌ حذف سفارش و بازگشت مبلغ", callback_data=f"svcrefund:{s['id']}")],
            [InlineKeyboardButton("🗑 حذف کامل سرویس", callback_data=f"svcfulldel:{s['id']}", style="danger")],
            [InlineKeyboardButton("◀️ بازگشت به کاربر", callback_data=f"um:{s['tg_id']}"), InlineKeyboardButton("◀️ بازگشت به مدیریت کاربران", callback_data="adm:users")]))

def admin_svc_orderdel(chat_id: int, svc_id: int) -> None:
    s = q_one("SELECT * FROM agent_panels WHERE id=?", (svc_id,))
    if not s:
        send_or_edit(chat_id, "سرویس یافت نشد.")
        return
    ex("DELETE FROM purchases WHERE panel_username=?", (str(s["panel_username"]),))
    send_or_edit(chat_id, "✅ سفارش حذف شد (سرویس پنل دست‌نخورده ماند).", back_adm_kb())

def admin_svc_refund(chat_id: int, svc_id: int) -> None:
    s = q_one("SELECT * FROM agent_panels WHERE id=?", (svc_id,))
    if not s:
        send_or_edit(chat_id, "سرویس یافت نشد.")
        return
    pur = q_one("SELECT * FROM purchases WHERE panel_username=? AND status='active' ORDER BY id DESC LIMIT 1", (str(s["panel_username"]),))
    if pur:
        ex("UPDATE users SET balance = balance + ? WHERE tg_id=?", (int(pur["price"]), int(s["tg_id"])))
        ex("DELETE FROM purchases WHERE id=?", (int(pur["id"]),))
        tg_send(int(s["tg_id"]), f"💳 مبلغ {num(pur['price'])} تومان به کیف پولت برگشت داده شد.")
    ex("DELETE FROM agent_panels WHERE id=?", (svc_id,))
    send_or_edit(chat_id, "✅ سفارش حذف و مبلغ به کیف کاربر برگشت داده شد.", back_adm_kb())

def admin_svc_fulldel(chat_id: int, svc_id: int) -> None:
    s = q_one("SELECT * FROM agent_panels WHERE id=?", (svc_id,))
    if not s:
        send_or_edit(chat_id, "سرویس یافت نشد.")
        return
    p = panel_client(str(s["panel_name"]), str(s["panel_type"] or "pasarguard"))
    if p:
        panel_call(p, "delete_admin", {"username": str(s["panel_username"])})
    ex("DELETE FROM agent_panels WHERE id=?", (svc_id,))
    ex("DELETE FROM purchases WHERE panel_username=?", (str(s["panel_username"]),))
    send_or_edit(chat_id, "✅ سرویس کامل حذف شد (پنل + ربات).")

def admin_finduser_apply(chat_id: int, text: str) -> None:
    st_pop(chat_id)
    t = text.strip()
    if not t.isdigit() or not int(t):
        st_set(chat_id, {"await": "finduser"})
        send_or_edit(chat_id, "❌ آیدی عددی معتبر بفرست!")
        return
    admin_user_card(chat_id, int(t))

def user_ref_code(tg_id: int) -> str:
    return str(tg_id % (36 ** 12))[:12].ljust(12, "0")

def user_manage_kb(u: dict) -> InlineKeyboardMarkup:
    tg_id = int(u["tg_id"])
    return ikb(
        [InlineKeyboardButton("👆 افزایش موجودی", callback_data=f"um:addbal:{tg_id}", style="success"), InlineKeyboardButton("👇 کاهش موجودی", callback_data=f"um:subbal:{tg_id}")],
        [InlineKeyboardButton("💡 خاموش کردن اکانت", callback_data=f"um:off:{tg_id}", style="danger"), InlineKeyboardButton("💡 روشن کردن اکانت", callback_data=f"um:on:{tg_id}", style="success")],
        [InlineKeyboardButton("🛍 سفارشات کاربر", callback_data=f"um:orders:{tg_id}"), InlineKeyboardButton("💰 پرداختی‌های کاربر", callback_data=f"um:pays:{tg_id}")],
        [InlineKeyboardButton("🔓 رفع مسدودی" if u["is_banned"] else "🔒 مسدود کردن", callback_data=f"um:ban:{tg_id}", style="danger")],
        [InlineKeyboardButton("✉️ ارسال پیام به کاربر", callback_data=f"um:msg:{tg_id}")],
        [InlineKeyboardButton("♻️ بروزرسانی", callback_data=f"um:info:{tg_id}")],
        [InlineKeyboardButton("◀️ بازگشت به مدیریت کاربران", callback_data="adm:users")])

def admin_user_card(chat_id: int, tg_id: int) -> None:
    u = q_one("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    if not u:
        send_or_edit(chat_id, "کاربر یافت نشد.")
        return
    buys = q_all("SELECT price, created_at FROM purchases WHERE tg_id=?", (tg_id,))
    recs = q_all("SELECT amount, status FROM receipts WHERE tg_id=?", (tg_id,))
    panels_n = int(q_val("SELECT COUNT(*) FROM agent_panels WHERE tg_id=?", (tg_id,), 0))
    now = time.time()
    h_buys, m_buys = [], []
    for b in buys:
        try:
            age = now - datetime.fromisoformat(str(b["created_at"])).timestamp()
        except Exception:
            continue
        if age <= 3600:
            h_buys.append(b)
        if age <= 30 * 86400:
            m_buys.append(b)
    sum_paid = sum(int(r["amount"] or 0) for r in recs if r["status"] == "approved")
    sum_buys = sum(int(b["price"] or 0) for b in buys)
    sum_h = sum(int(b["price"] or 0) for b in h_buys)
    sum_m = sum(int(b["price"] or 0) for b in m_buys)
    txt = (
        "👀 <b>اطلاعات کاربر:</b>\n\n🔗 <b>اطلاعات کاربری کاربر</b>\n"
        f"⭕️ وضعیت کاربر : {'Banned' if u['is_banned'] else 'Active'}\n"
        f"⭕️ نام کاربری کاربر : @{u['username'] or 'NOT_USERNAME'}\n"
        f"⭕️ آیدی عددی کاربر : <code>{u['tg_id']}</code>\n"
        f"⭕️ کد معرف کاربر : <code>{user_ref_code(tg_id)}</code>\n"
        f"⭕️ زمان عضویت کاربر : {jdate(u['created_at'])}\n\n⭕️ تعداد زیرمجموعه کاربر : 0\n\n"
        "💎 <b>گزارشات مالی</b>\n"
        f"🔰 موجودی کاربر : {u['balance'] or 0}\n🔰 تعداد خرید کل کاربر : {len(buys)}\n"
        f"🔰 مبلغ کل پرداختی  : {sum_paid}\n🔰 جمع کل خرید : {sum_buys}\n"
        f"🔰 تعداد فروش یک ساعت گذشته : {len(h_buys)} عدد\n🔰 مجموع فروش یک ساعت گذشته : {sum_h} تومان\n"
        f"🔰 تعداد فروش یک ماه گذشته : {len(m_buys)} عدد\n🔰 مجموع فروش یک ماه گذشته : {sum_m} تومان\n\n"
        f"🛡 تعداد پنل‌های فعال کاربر : {panels_n}"
    )
    send_or_edit(chat_id, txt, user_manage_kb(u))

def admin_user_action(chat_id: int, data: str) -> None:
    parts = data.split(":")
    if len(parts) == 2:
        act, tg_id = "info", int(parts[1])
    else:
        act, tg_id = parts[1], int(parts[2])
    u = q_one("SELECT * FROM users WHERE tg_id=?", (tg_id,))
    if not u:
        send_or_edit(chat_id, "کاربر یافت نشد.")
        return
    if act == "info":
        admin_user_card(chat_id, tg_id)
    elif act in ("addbal", "subbal"):
        st_set(chat_id, {"await": f"um:{act}", "target": tg_id})
        send_or_edit(chat_id, "مبلغ را به تومان بفرست!")
    elif act in ("off", "on", "ban"):
        if act == "off":
            ex("UPDATE users SET is_banned=1 WHERE tg_id=?", (tg_id,))
        elif act == "on":
            ex("UPDATE users SET is_banned=0 WHERE tg_id=?", (tg_id,))
        else:
            ex("UPDATE users SET is_banned=? WHERE tg_id=?", (0 if u["is_banned"] else 1, tg_id))
        admin_user_card(chat_id, tg_id)
    elif act == "msg":
        st_set(chat_id, {"await": "um:msg_pending", "target": tg_id})
        send_or_edit(chat_id, "❓ آیا کاربر بتواند به این پیام جواب بدهد؟",
                     ikb([InlineKeyboardButton("✅ بله", callback_data=f"umrepl:yes:{tg_id}", style="success"), InlineKeyboardButton("❌ خیر", callback_data=f"umrepl:no:{tg_id}", style="danger")]))
    elif act == "orders":
        rows = q_all("SELECT id, panel_username, status FROM agent_panels WHERE tg_id=? ORDER BY id DESC LIMIT 20", (tg_id,))
        if not rows:
            send_or_edit(chat_id, "سفارشی یافت نشد.", back_adm_kb())
        elif len(rows) == 1:
            admin_svc_view(chat_id, int(rows[0]["id"]))
        else:
            send_or_edit(chat_id, "⚠️ سفارشات کاربر — از لیست زیر سرویس موردنظر را انتخاب کنید:\n\n👤 نام کاربری | 📊 وضعیت سرویس | ⚙️ عملیات",
                         _svc_pick_kb(rows))
    elif act == "pays":
        rows = q_all("SELECT id, amount, status FROM receipts WHERE tg_id=? ORDER BY id DESC LIMIT 15", (tg_id,))
        txt = "\n".join(f"💳 #{r['id']} — {fmt_price(r['amount'])} — {r['status']}" for r in rows)
        total = int(q_val("SELECT COALESCE(SUM(amount),0) FROM receipts WHERE tg_id=? AND status='approved'", (tg_id,), 0))
        send_or_edit(chat_id, (txt or "پرداختی نیست.") + f"\n\n💰 جمع پرداخت‌های تاییدشده: {fmt_price(total)}")

def admin_umrepl(chat_id: int, data: str) -> None:
    parts = data.split(":")
    if st_all(chat_id).get("await") != "um:msg_pending":
        send_or_edit(chat_id, "جلسه منقضی شد.")
        return
    st_set(chat_id, {"allow_reply": 1 if parts[1] == "yes" else 0, "await": "um:msg"})
    send_or_edit(chat_id, "✉️ متن پیام برای کاربر را بفرست!")

def admin_um_msg_apply(chat_id: int, text: str) -> None:
    st = st_all(chat_id)
    st_pop(chat_id)
    target = int(st.get("target") or 0)
    if not target:
        send_or_edit(chat_id, "هدف نامعتبر.")
        return
    allow = bool(st.get("allow_reply"))
    kb = ikb([InlineKeyboardButton("✉️ پاسخ", callback_data=f"um:msg:{target}")]) if allow else None
    ok = tg_send(target, "📨 پیام از پشتیبانی:\n\n" + text, kb)
    send_or_edit(chat_id, ("✅ پیام ارسال شد." + (" (کاربر می‌تواند پاسخ دهد)." if allow else "")) if ok.get("ok")
                 else "❌ ارسال نشد (احتمالا کاربر ربات را استارت نکرده).")

def admin_um_bal_apply(chat_id: int, text: str) -> None:
    await_ = str(st_get(chat_id, "await", ""))
    target = int(st_get(chat_id, "target", 0) or 0)
    st_pop(chat_id)
    m = re.search(r"(\d+)", text.replace(",", ""))
    if not m:
        send_or_edit(chat_id, "عدد معتبر بفرست!")
        return
    val = int(m.group(1))
    if not target:
        send_or_edit(chat_id, "❌ عدد معتبر بفرست!")
        return
    if await_ == "um:addbal":
        add_balance(target, val)
    else:
        ex("UPDATE users SET balance = MAX(0, balance - ?) WHERE tg_id=?", (val, target))
    send_or_edit(chat_id, f"✅ انجام شد — موجودی جدید کاربر {target}: {fmt_price(get_balance(target))}")


def admin_massbal_start(chat_id: int, kind: str) -> None:
    st_set(chat_id, {"await": "massbal" if kind == "add" else "mass_sub"})
    send_or_edit(chat_id, "👥 مبلغ شارژ همگانی را به تومان بفرست (به همه کاربران اضافه می‌شود)!" if kind == "add"
                 else "📉 مبلغ کسر همگانی را به تومان بفرست (از موجودی همه کاربران کم می‌شود)!")

def admin_massbal_apply(chat_id: int, text: str) -> None:
    await_ = str(st_get(chat_id, "await", ""))
    st_pop(chat_id)
    val = int(re.sub(r"[^\d]", "", text) or 0)
    if not val:
        send_or_edit(chat_id, "❌ عدد معتبر بفرست!")
        return
    if await_ == "massbal":
        ex("UPDATE users SET balance = balance + ?", (val,))
        send_or_edit(chat_id, "✅ شارژ همگانی انجام شد.")
    else:
        ex("UPDATE users SET balance = MAX(0, balance - ?)", (val,))
        send_or_edit(chat_id, "✅ کسر همگانی انجام شد.")

ROLE_LABELS = {2: "👑 مدیر کل", 3: "👤 اپراتور", 5: "🌐 CDN"}

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


def admin_panels_home(chat_id: int) -> None:
    kb = [[InlineKeyboardButton(f"🌐 {n}", callback_data="pnl:view:" + n), InlineKeyboardButton("🔍 تست", callback_data="pnl:ping:" + n)] for n in get_panels()]
    kb.append([InlineKeyboardButton("➕ افزودن پنل", callback_data="pnl:add", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🌐 پنل‌های متصل:", InlineKeyboardMarkup(kb))

def admin_panel_view(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    active = d.get("active", name == str(get_setting("selected_panel", "") or ""))
    plans = q_all("SELECT * FROM panel_plans WHERE panel_name=? ORDER BY volume_gb", (name,))
    kb = []
    for pl in plans:
        mark = "" if pl["active"] else "❌ "
        kb.append([InlineKeyboardButton(f"{mark}{g2(pl['volume_gb'])} گیگ — {num(pl['price'])} ت", callback_data=f"pl:{name}:{pl['id']}")])
    kb.append([InlineKeyboardButton("➕ افزودن پلن حجمی +", callback_data=f"pladd:{name}", style="success")])
    xprice, xmin = int(d.get("extra_gb_price") or 0), int(d.get("extra_gb_min") or 0)
    role_lbl = get_panel_role_label(d, int(d.get("role_id") or 3))
    kb.append([InlineKeyboardButton(f"🛡 نقش مدیران: {role_lbl}", callback_data=f"pnlrolepick:{name}")])
    kb.append([InlineKeyboardButton("💰 قیمت حجم: " + (f"{num(xprice)} ت" if xprice else "— تنظیم نشده"), callback_data=f"pnledit:extra_price:{name}"),
               InlineKeyboardButton("⚖️ حداقل حجم: " + (f"{xmin} گیگ" if xmin else "— تنظیم نشده"), callback_data=f"pnledit:extra_min:{name}")])
    kb.append([InlineKeyboardButton("📊 آمار پنل", callback_data=f"pnl:stats:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش نام پنل", callback_data=f"pnledit:name:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش آدرس پنل", callback_data=f"pnledit:url:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("✏️ ویرایش پسورد ادمین", callback_data=f"pnledit:pass:{name}")])
    kb.append([InlineKeyboardButton("🧪 سرویس تست: ✅ روشن" if d.get("is_test_panel") else "🧪 سرویس تست: ⛔️ خاموش", callback_data=f"pnl:testtoggle:{name}"),
               InlineKeyboardButton("⚙️ حجم/مدت تست", callback_data=f"pnl:test:{name}")])
    kb.append([InlineKeyboardButton("🔴 غیرفعال کن" if active else "🟢 فعال کن", callback_data=f"pnl:toggle:{name}")])
    kb.append([InlineKeyboardButton("🗑 حذف این پنل", callback_data=f"askdel:pnl:{name}", style="danger")])
    kb.append([InlineKeyboardButton("◀️ پنل‌ها", callback_data="adm:panels")])
    send_or_edit(chat_id, f"🛠 مدیریت پنل «{esc(name)}» ({d.get('ptype', 'pasarguard')})\n"
                          f"{'🟢 فعال (قابل خرید)' if active else '🔴 غیرفعال'}\n🔗 {esc(d.get('base_url'))}\n\n📦 پلن‌های حجمی این پنل:",
                 InlineKeyboardMarkup(kb))

def admin_panel_ping(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    tg_send(chat_id, f"🔍 در حال تست {esc(name)} ...")
    r = panel_ping(d)
    send_or_edit(chat_id, f"🟢 وصله — {esc(name)}" if r.get("ok") else f"🔴 قطعه — {esc(name)}")

def admin_panel_add_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "pnladd_name"})
    send_or_edit(chat_id, "🏷 اسم پنل رو بفرست (همین اسم به کاربر نشون داده می‌شه، مثلاً: سرور1)!")

def admin_panel_delete_confirm(chat_id: int, name: str) -> None:
    send_or_edit(chat_id, f"⚠️ «{esc(name)}» برای همیشه حذف بشه؟ این عملیات غیرقابل‌بازگشته!",
                 ikb([InlineKeyboardButton("🔥 بله، حذف کن", callback_data="okdel:pnl:" + name, style="danger")], [InlineKeyboardButton("🚫 نه", callback_data="adm:panels")]))

def admin_panel_delete_apply(chat_id: int, name: str) -> None:
    st_pop(chat_id)
    panels = get_panels()
    panels.pop(name, None)
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🗑 پنل «{esc(name)}» حذف شد.", admin_menu_kb())

def admin_panel_add_step(chat_id: int, await_: str, text: str) -> None:
    if await_ == "pnladd_name":
        name = text.strip()
        if not name:
            send_or_edit(chat_id, "❌ اسم پنل نمی‌تونه خالی باشه، دوباره بفرست!")
            return
        if not valid_panel_name(name):
            send_or_edit(chat_id, "❌ اسم پنل باید حداکثر ۱۴ حرف باشد و شامل «:» یا «%» نباشد. دوباره بفرست!")
            return
        if name in get_panels():
            send_or_edit(chat_id, f"❌ پنلی با اسم «{esc(name)}» از قبل ثبت شده. اسم دیگه‌ای بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_url", "pnl_name": name})
        send_or_edit(chat_id, "🔗 آدرس پنل رو بفرست ( https://example.ir/dashboard)!")
    elif await_ == "pnladd_url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_user", "pnl_url": panel_clean_base_url(text.strip())})
        send_or_edit(chat_id, "👤 یوزرنیم ادمین پنل را بفرست!")
    elif await_ == "pnladd_user":
        st_set(chat_id, {"await": "pnladd_pass", "pnl_user": text.strip()})
        send_or_edit(chat_id, "🔑 پسورد ادمین پنل را بفرست!")
    elif await_ == "pnladd_pass":
        name, url, user = str(st_get(chat_id, "pnl_name", "")), str(st_get(chat_id, "pnl_url", "")), str(st_get(chat_id, "pnl_user", ""))
        pw = text.strip()
        st_pop(chat_id)
        send_or_edit(chat_id, "🔍 در حال تست اتصال...")
        r = panel_ping({"base_url": url, "username": user, "password": pw, "ptype": "pasarguard"})
        if not r.get("ok"):
            send_or_edit(chat_id, "❌ لاگین ناموفق\nدوباره از «➕ افزودن پنل» شروع کن.")
            return
        panels = get_panels()
        final = name or f"پنل {len(panels) + 1}"
        i = 2
        while final in panels:
            final = f"{name} {i}"
            i += 1
        panels[final] = {"base_url": url, "username": user, "password": panel_encrypt_pw(pw), "ptype": "pasarguard", "active": True}
        set_setting("panels", panels)
        send_or_edit(chat_id, f"✅ پنل «{esc(final)}» اضافه و وصل شد.", admin_menu_kb())

def admin_panel_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    panels[name]["active"] = not panels[name].get("active")
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🟢 پنل «{esc(name)}» فعال شد." if panels[name]["active"] else f"🔴 پنل «{esc(name)}» غیرفعال شد.")
    admin_panel_view(chat_id, name)

def admin_panel_edit_start(chat_id: int, name: str) -> None:
    if name not in get_panels():
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    send_or_edit(chat_id, f"✏️ چه چیزی از پنل «{esc(name)}» ویرایش بشه؟", ikb(
        [InlineKeyboardButton("📛 نام پنل", callback_data=f"pnledit:name:{name}")], [InlineKeyboardButton("🔗 آدرس پنل", callback_data=f"pnledit:url:{name}")],
        [InlineKeyboardButton("👤 یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("🔑 پسورد ادمین", callback_data=f"pnledit:pass:{name}")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_panel_test_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    d["is_test_panel"] = not d.get("is_test_panel")
    note = ""
    if d["is_test_panel"] and (not d.get("test_gb") or not d.get("test_days")):
        d["test_gb"] = d.get("test_gb") or 1
        d["test_days"] = d.get("test_days") or 1
        note = "\n⚙️ حجم/مدت ست نبود — دیفالت 1 گیگ / 1 روز اعمال شد (از «⚙️ حجم/مدت تست» قابل تغییر است)."
    set_setting("panels", panels)
    send_or_edit(chat_id, ("🧪 سرویس تست روشن شد." if d["is_test_panel"] else "🧪 سرویس تست خاموش شد.") + note)
    admin_panel_view(chat_id, name)

def admin_panel_test_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pnltest", "pnltest_name": name})
    send_or_edit(chat_id, "🖊 مشخصات سرویس تست را بفرست (دو خط):\n\nحجم به گیگ: مثلا 1\nمدت به روز: مثلا 1\n\n"
                          "(این پنل برای سرویس‌های تست کاربران استفاده خواهد شد).", cancel_kb())

def valid_panel_name(name: str) -> bool:
    return bool(name) and ":" not in name and "%" not in name and len(name.encode("utf-8")) <= 28

def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False

def admin_panel_test_apply(chat_id: int, text: str) -> None:
    name = str(st_get(chat_id, "pnltest_name", ""))
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2 or not _is_num(lines[0]) or not _is_num(lines[1]):
        send_or_edit(chat_id, "❌ فرمت درست نیست. دو خط بفرست:\nحجم (گیگ)\nمدت (روز) — مثلا:\n1\n1.")
        return
    panels = get_panels()
    if name in panels:
        panels[name]["test_gb"] = float(lines[0])
        panels[name]["test_days"] = int(float(lines[1]))
        set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, f"✅ سرویس تست ثبت شد: {lines[0]} گیگ / {lines[1]} روز.")
    admin_panel_view(chat_id, name)

def admin_panel_rolepick(chat_id: int, name: str) -> None:
    panels = get_panels()
    p = panels.get(name)
    if not p:
        send_or_edit(chat_id, "❌ پنل یافت نشد.")
        return
    rows = []
    tok = _panel_auth(p)
    if tok:
        try:
            r = _preq(p, "GET", "/api/admin-roles/simple", token=tok)
            if r.status_code == 200:
                roles = r.json().get("roles") or []
                for role in roles:
                    rname = str(role.get("name", "")).strip().lower()
                    if role.get("is_owner") or rname in ("owner", "administrator", "مدیر کل", "مدیرکل"):
                        continue
                    r_id = role["id"]
                    r_name = role.get("name") or f"نقش {r_id}"
                    rows.append([InlineKeyboardButton(f"🛡 {r_name}", callback_data=f"pnlrole:{r_id}:{name}")])
        except Exception:
            pass
    if not rows:
        rows = [
            [InlineKeyboardButton("👑 مدیر کل (همه‌چیز)", callback_data=f"pnlrole:2:{name}")],
            [InlineKeyboardButton("👤 اپراتور (ساخت سرویس)", callback_data=f"pnlrole:3:{name}")],
            [InlineKeyboardButton("🌐 CDN (فقط سرویس)", callback_data=f"pnlrole:5:{name}")],
        ]
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")])
    send_or_edit(chat_id, f"🛡 نقش مدیران ساخته‌شده توسط ربات در «{esc(name)}»:", InlineKeyboardMarkup(rows))

def admin_panel_role_set(chat_id: int, rid: int, name: str) -> None:
    panels = get_panels()
    if name in panels:
        panels[name]["role_id"] = rid
        set_setting("panels", panels)
        lbl = get_panel_role_label(panels[name], rid)
    else:
        lbl = f"نقش {rid}"
    send_or_edit(chat_id, f"✅ نقش مدیران: {lbl}")
    admin_panel_view(chat_id, name)

def admin_panel_stats(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    send_or_edit(chat_id, "📊 در حال دریافت آمار...")
    r = panel_call(d, "stats", {}) or {}
    if r.get("ok"):
        nadmins, ver = int(r.get("admins_count") or 0), r.get("version", "—")
        ram_t, ram_u, traffic, status = r.get("ram_total_gb", "—"), r.get("ram_used_gb", "—"), r.get("traffic_tb", "—"), "✅ پنل متصل است."
    else:
        nadmins, ver, ram_t, ram_u, traffic, status = 0, "—", "—", "—", "—", "🔴 قطع"
    row = q_one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM purchases WHERE status='active'") or {"c": 0, "s": 0}
    send_or_edit(
        chat_id,
        f"📊 آمار پنل شما 👇\n\n🖥 وضعیت اتصال: {status}\n👥 تعداد مدیران ساخته شده در پنل: {nadmins}\n"
        f"📡 نسخه پنل: {ver}\n💻 رم کل سرور: {ram_t} گیگابایت\n💻 مصرف رم پنل: {ram_u} گیگابایت\n"
        f"🌐 ترافیک کل مصرف شده: {traffic} ترابایت\n🛍 تعداد فروش کل در این پنل: {row['c']}\n"
        f"🛍 جمع فروش کل: {num(row['s'])} تومان",
    )

def admin_plan_add_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pladd_gb", "plan_panel": name})
    send_or_edit(chat_id, "➕ حجم پلن را بفرست (گیگ): مثلا 100!", cancel_kb())

def admin_plan_gb_apply(chat_id: int, text: str) -> None:
    gb = text.strip()
    if not _is_num(gb) or float(gb) <= 0:
        send_or_edit(chat_id, "❌ عدد گیگ نامعتبر. دوباره بفرست (مثلا 100)!")
        return
    st_set(chat_id, {"await": "pladd_price", "plan_gb": float(gb)})
    send_or_edit(chat_id, "💰 قیمت این پلن را بفرست (تومان): مثلا 300000!")

def admin_plan_price_apply(chat_id: int, text: str) -> None:
    price = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(price) or int(float(price)) <= 0:
        send_or_edit(chat_id, "❌ قیمت نامعتبر. دوباره بفرست (تومان)!")
        return
    name, gb = str(st_get(chat_id, "plan_panel", "")), float(st_get(chat_id, "plan_gb", 0))
    st_pop(chat_id)
    ex("INSERT INTO panel_plans(panel_name, volume_gb, price, active) VALUES(?,?,?,1)", (name, gb, int(float(price))))
    send_or_edit(chat_id, f"✅ پلن افزوده شد: {g2(gb)} گیگ — {num(float(price))} ت.")
    admin_panel_view(chat_id, name)

def admin_plan_view(chat_id: int, name: str, pid: int) -> None:
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    if not pl:
        send_or_edit(chat_id, "پلن یافت نشد.")
        return
    send_or_edit(chat_id, f"📦 پلن {g2(pl['volume_gb'])} گیگ\n💰 قیمت: {num(pl['price'])} تومان\n" + ("🟢 فعال" if pl["active"] else "🔴 غیرفعال"),
                 ikb([InlineKeyboardButton("✏️ ویرایش قیمت", callback_data=f"pled:{pid}:price:{name}"), InlineKeyboardButton("✏️ ویرایش حجم", callback_data=f"pled:{pid}:gb:{name}")],
                     [InlineKeyboardButton("🔴 غیرفعال کن" if pl["active"] else "🟢 فعال کن", callback_data=f"pltog:{pid}:{name}")],
                     [InlineKeyboardButton("🗑 حذف پلن", callback_data=f"okdel:plan:{pid}:{name}", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_plan_edit_prompt(chat_id: int, pid: int, field: str, name: str) -> None:
    st_set(chat_id, {"await": f"pled:{field}", "pled_pid": pid, "pled_panel": name})
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    cur = (f"{num(pl['price'])} تومان" if field == "price" else f"{g2(pl['volume_gb'])} گیگ") if pl else "—"
    send_or_edit(chat_id, f"✏️ مقدار فعلی: {cur}\n\nمقدار جدید {'قیمت (تومان)' if field == 'price' else 'حجم (گیگ)'} را بفرست!", cancel_kb())

def admin_plan_edit_apply(chat_id: int, field: str, text: str) -> None:
    pid, name = int(st_get(chat_id, "pled_pid", 0) or 0), str(st_get(chat_id, "pled_panel", ""))
    v = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(v) or float(v) <= 0:
        send_or_edit(chat_id, "❌ مقدار نامعتبر. دوباره بفرست!")
        return
    if field == "price":
        ex("UPDATE panel_plans SET price=? WHERE id=?", (int(float(v)), pid))
    else:
        ex("UPDATE panel_plans SET volume_gb=? WHERE id=?", (float(v), pid))
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ پلن ویرایش شد.")
    admin_plan_view(chat_id, name, pid)

def admin_plan_toggle(chat_id: int, pid: int, name: str) -> None:
    ex("UPDATE panel_plans SET active = 1 - active WHERE id=?", (pid,))
    admin_plan_view(chat_id, name, pid)

def admin_plan_delete(chat_id: int, pid: int, name: str) -> None:
    ex("DELETE FROM panel_plans WHERE id=?", (pid,))
    send_or_edit(chat_id, "🗑 پلن حذف شد.")
    admin_panel_view(chat_id, name)

def admin_panel_field_edit(chat_id: int, field: str, name: str) -> None:
    cur = get_panels().get(name, {})
    curval = {"user": cur.get("username", ""), "pass": "••••••", "url": cur.get("base_url", ""), "name": name,
              "extra_price": cur.get("extra_gb_price", ""), "extra_min": cur.get("extra_gb_min", "")}.get(field, "")
    st_set(chat_id, {"await": f"pnledit_{field}", "edit_pnl": name})
    hints = {"extra_price": "قیمت حجم اضافه به تومان برای هر گیگ (مثلاً 6000)!", "extra_min": "حداقل گیگ قابل خرید حجم اضافه (مثلاً 10)!",
             "name": "نام جدید پنل را بفرست!", "url": "آدرس جدید پنل را بفرست!", "user": "یوزر ادمین جدید را بفرست!",
             "pass": "پسورد ادمین جدید را بفرست!"}
    send_or_edit(chat_id, "✏️ مقدار فعلی: " + (str(curval) if curval not in ("", None) else "— تنظیم نشده") + "\n\n" + hints.get(field, "مقدار جدید را بفرست:"), cancel_kb())

def admin_panel_field_apply(chat_id: int, field: str, text: str) -> None:
    name = str(st_get(chat_id, "edit_pnl", ""))
    text = text.strip()
    panels = get_panels()
    if name not in panels:
        st_pop(chat_id)
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    if field == "name":
        if not valid_panel_name(text) or (text in panels and text != name):
            send_or_edit(chat_id, "❌ نام نامعتبر یا تکراری است (حداکثر ۱۴ حرف، بدون «:» و «%»). دوباره بفرست!")
            return
        panels = {(text if k == name else k): v for k, v in panels.items()}
        ex("UPDATE panel_plans SET panel_name=? WHERE panel_name=?", (text, name))
        set_setting("panels", panels)
        st_pop(chat_id)
        send_or_edit(chat_id, "✅ نام پنل شد: " + text)
        admin_panel_view(chat_id, text)
        return
    if field == "url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        panels[name]["base_url"] = panel_clean_base_url(text)
    elif field == "user":
        panels[name]["username"] = text
    elif field == "pass":
        panels[name]["password"] = panel_encrypt_pw(text)
    elif field == "extra_price":
        if not _is_num(text) or int(float(text)) < 0:
            send_or_edit(chat_id, "❌ قیمت نامعتبر (عدد تومان بفرست، 0 = حذف)!")
            return
        panels[name]["extra_gb_price"] = int(float(text))
    elif field == "extra_min":
        if not _is_num(text) or int(float(text)) < 1:
            send_or_edit(chat_id, "❌ حداقل نامعتبر (عدد گیگ بفرست)!")
            return
        panels[name]["extra_gb_min"] = int(float(text))
    else:
        st_pop(chat_id)
        return
    set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ ذخیره شد.")
    admin_panel_view(chat_id, name)

def handle_callback(cq: dict) -> None:
    chat_id = int(cq["from"]["id"])
    data = str(cq.get("data") or "")
    _CTX["mid"] = int((cq.get("message") or {}).get("message_id") or 0) or None
    tg("answerCallbackQuery", {"callback_query_id": cq["id"]})
    admin = is_admin(chat_id)

    if not admin and q_val("SELECT is_banned FROM users WHERE tg_id=?", (chat_id,), 0):
        tg_send(chat_id, "🚫 دسترسی شما به ربات مسدود شده است.")
        return

    if data.startswith(("buyplan:", "confirmplan:", "paybalplan:", "apdc:", "confirm:", "paybal:", "buy:")) or data == "cancelbuy":
        handle_buy_callback(chat_id, data)
        return
    if data == "m:home":
        st_pop(chat_id)
        send_or_edit(chat_id, "🏠 منوی اصلی:", main_menu_kb(admin))
        return
    if data == "m:buy":
        show_buy_screen(chat_id)
        return
    if data == "m:test":
        handle_test_start(chat_id)
        return
    if data == "m:support":
        start_support(chat_id)
        return
    if data == "m:help":
        show_guide(chat_id)
        return
    if data == "m:services":
        services_home(chat_id)
        return
    if data == "topup":
        start_topup(chat_id)
        return
    if data == "myreceipts" or data == "wal:receipts":
        my_receipts(chat_id)
        return
    if data == "m:tkt":
        st_set(chat_id, {"await": "support_msg"})
        tg_send(chat_id, "✍️ پیامت را بنویس (ارسال به پشتیبانی)!")
        return
    if data == "wal:addcredit":
        wallet_add_credit(chat_id)
        return
    if data == "wal:gift":
        start_gift_redeem(chat_id)
        return
    if data == "wal:receipt":
        st_set(chat_id, {"await": "wallet_receipt"})
        send_or_edit(chat_id, "✉️ کد پیگیری واریز را بفرست (یا عکس رسید)!")
        return
    if data.startswith("xgpay:"):
        parts = (data.split(":") + ["0", "0", "0"])[:4]
        extra_gb_invoice_confirm(chat_id, int(parts[1]), int(parts[2]), int(parts[3]))
        return
    if data == "xgcancel":
        extra_gb_invoice_cancel(chat_id)
        return
    if data.startswith("guide:"):
        t = q_one("SELECT content FROM guide_topics WHERE id=? LIMIT 1", (int(data[6:]),))
        send_or_edit(chat_id, str(t["content"]) if t else "راهنمایی ثبت نشده.",
                     ikb([InlineKeyboardButton("◀️ بازگشت به لیست پلتفرم‌ها", callback_data="m:help")], [InlineKeyboardButton("🏠 منوی اصلی", callback_data="m:home")]))
        return
    if data.startswith("apchpw:"):
        service_change_password_start(chat_id, int(data[7:]))
        return
    if data.startswith("apcreds:"):
        service_login_info(chat_id, int(data[8:]))
        return
    if data.startswith("aptoggle:"):
        service_toggle(chat_id, int(data[9:]))
        return
    if data.startswith("apgb:"):
        service_extra_gb_start(chat_id, int(data[5:]))
        return
    if data.startswith("svc:"):
        parts = data.split(":")
        svc_id = int(parts[1])
        if len(parts) == 2:
            service_screen(chat_id, svc_id)
        elif parts[2] == "info":
            service_login_info(chat_id, svc_id)
        elif parts[2] == "pass":
            service_change_password_start(chat_id, svc_id)
        elif parts[2] == "ext":
            tg_send(chat_id, "برای حجم اضافه با پشتیبانی در تماس باش یا از 🔐 خرید اشتراک استفاده کن.")
        return
    if data.startswith("testpick:"):
        handle_test_pick(chat_id, urldec(data[9:]))
        return
    if not admin and data.startswith("um:msg:"):
        if int(data[7:]) == chat_id:
            st_set(chat_id, {"await": "support_msg"})
            send_or_edit(chat_id, "✍️ پاسخت را بنویس (ارسال به پشتیبانی)!")
        else:
            tg_send(chat_id, "⛔️ فقط ادمین.")
        return

    if not admin:
        tg_send(chat_id, "⛔️ فقط ادمین.")
        return

    simple = {
        "adm:general": admin_general_home, "adm:shopgeneral": admin_shopgeneral_home, "adm:power": admin_power_home,
        "adm:stats": admin_stats, "adm:receipts": admin_receipts_queue, "adm:users": admin_users_home,
        "adm:finduser": admin_finduser_start, "adm:search": admin_findorder_start, "adm:tickets": admin_tickets,
        "adm:discounts": admin_discounts_home, "adm:settings": admin_settings_home, "adm:payments": admin_payments_home,
        "adm:appearance": admin_appearance_home,
        "adm:gifts": admin_gifts_home, "adm:helps": admin_guide_home, "adm:guides": admin_guide_home,
        "adm:features": admin_features_home, "adm:panels": admin_panels_home, "adm:bcast": bcast_home,
        "set:channels": admin_channels_home, "addchan": admin_channel_add_start, "pnl:add": admin_panel_add_start,
        "helpadd": admin_help_add, "setcancel": admin_set_cancel,
    }
    if data in simple:
        simple[data](chat_id)
        return
    if data == "adm:back":
        st_pop(chat_id)
        send_or_edit(chat_id, "👨‍💼 پنل مدیریت:", admin_menu_kb())
        return
    if data == "adm:massbal":
        admin_massbal_start(chat_id, "add")
        return
    if data == "adm:masssub":
        admin_massbal_start(chat_id, "sub")
        return
    if data == "svcnoop":
        return
    if data.startswith("svcview:"):
        admin_svc_view(chat_id, int(data[8:]))
    elif data.startswith("svcordel:"):
        admin_svc_orderdel(chat_id, int(data[9:]))
    elif data.startswith("svcrefund:"):
        admin_svc_refund(chat_id, int(data[10:]))
    elif data.startswith("svcfulldel:"):
        admin_svc_fulldel(chat_id, int(data[11:]))
    elif data.startswith("umrepl:"):
        admin_umrepl(chat_id, data)
    elif data.startswith("paytoggle:"):
        pp = data.split(":")
        admin_pay_toggle(chat_id, pp[1], len(pp) > 2 and pp[2] == "cfg")
    elif data.startswith("paycfg:"):
        admin_pay_cfg(chat_id, data[7:])
    elif data.startswith("payapi:"):
        admin_pay_api_start(chat_id, data[7:])
    elif data.startswith(("rcok:", "rcno:")):
        handle_receipt_review(chat_id, data)
    elif data.startswith("rcfix:"):
        receipt_fix_start(chat_id, int(data[6:]))
    elif data.startswith("tkclose:"):
        admin_ticket_close(chat_id, int(data[8:]))
    elif data.startswith("um:"):
        admin_user_action(chat_id, data)
    elif data.startswith("bcast2:"):
        bcast_audience_pick(chat_id, data[7:])
    elif data.startswith("bcastbtn:"):
        bcast_btn_pick(chat_id, data[9:])
    elif data.startswith("bcastgo:"):
        bcast_run(chat_id, data[8:] == "yes")
    elif data.startswith("feat:"):
        admin_feature_toggle(chat_id, data[5:])
    elif data.startswith("delchan:"):
        admin_channel_delete(chat_id, urllib.parse.unquote_plus(data[8:]))
    elif data == "set:force_join":
        set_setting("force_join", not bool(get_setting("force_join", False)))
        admin_shopgeneral_home(chat_id)
    elif data.startswith("setcol:"):
        admin_appearance_setcol(chat_id, data[7:])
    elif data == "toggleemoji":
        admin_appearance_toggle_emoji(chat_id)
    elif data.startswith("set:"):
        admin_set_prompt(chat_id, data[4:])
    elif data in ("dsc:add", "gift:add", "disc:new"):
        admin_code_add_start(chat_id, "dsc" if data != "gift:add" else "gift")
    elif data.startswith(("okdel:discount:", "okdel:gift:")):
        admin_code_delete(chat_id, data)
    elif data.startswith("pnl:edit:"):
        admin_panel_edit_start(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:toggle:"):
        admin_panel_toggle(chat_id, urldec(data[11:]))
    elif data.startswith("pnl:view:"):
        admin_panel_view(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:ping:"):
        admin_panel_ping(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:testtoggle:"):
        admin_panel_test_toggle(chat_id, urldec(data[15:]))
    elif data.startswith("pnl:test:"):
        admin_panel_test_prompt(chat_id, urldec(data[9:]))
    elif data.startswith("pnlrolepick:"):
        admin_panel_rolepick(chat_id, urldec(data[12:]))
    elif data.startswith("pnlrole:"):
        parts = data.split(":", 2)
        admin_panel_role_set(chat_id, int(parts[1]), urldec(parts[2]))
    elif data.startswith("pnl:stats:"):
        admin_panel_stats(chat_id, urldec(data[10:]))
    elif data.startswith("pladd:"):
        admin_plan_add_prompt(chat_id, urldec(data[6:]))
    elif data.startswith("pled:"):
        parts = data.split(":", 3)
        admin_plan_edit_prompt(chat_id, int(parts[1]), parts[2], urldec(parts[3]))
    elif data.startswith("pltog:"):
        parts = data.split(":", 2)
        admin_plan_toggle(chat_id, int(parts[1]), urldec(parts[2]))
    elif data.startswith("pl:"):
        parts = data.split(":")
        admin_plan_view(chat_id, urldec(":".join(parts[1:-1])), int(parts[-1]))
    elif data.startswith("okdel:plan:"):
        parts = data.split(":", 3)
        admin_plan_delete(chat_id, int(parts[2]), urldec(parts[3]))
    elif data.startswith("pnledit:"):
        parts = data.split(":", 2)
        admin_panel_field_edit(chat_id, parts[1], urldec(parts[2]))
    elif data.startswith("askdel:pnl:"):
        admin_panel_delete_confirm(chat_id, urldec(data[11:]))
    elif data.startswith("okdel:pnl:"):
        admin_panel_delete_apply(chat_id, urldec(data[10:]))
    elif data.startswith("helpedit:"):
        admin_help_edit(chat_id, int(data[9:]))
    elif data.startswith("helpdel:"):
        admin_help_delete(chat_id, int(data[8:]))
    elif data.startswith("guideadm:"):
        admin_guide_home(chat_id)
    elif data.startswith("pw:"):
        admin_power_toggle(chat_id, data[3:])
    else:
        tg_send(chat_id, "دستور ناشناخته: " + esc(data))

def force_join_ok(u: dict) -> bool:
    frm = (u.get("message") or {}).get("from") or (u.get("callback_query") or {}).get("from") or {}
    uid = int(frm.get("id") or 0)
    if uid and is_admin(uid):
        return True
    chans = q_all("SELECT channel_id FROM channels ORDER BY id")
    if not chans:
        return True
    rows, missing = [], False
    for c in chans:
        cid = str(c["channel_id"])
        r = tg("getChatMember", {"chat_id": cid, "user_id": uid})
        if not r.get("ok"):
            continue
        if (r.get("result") or {}).get("status", "left") not in ("creator", "administrator", "member"):
            missing = True
            if cid.startswith("@"):
                rows.append([InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/" + cid[1:], style="success")])
            elif cid.startswith(("http://", "https://")):
                rows.append([InlineKeyboardButton("📢 عضویت در کانال", url=cid, style="success")])
    if not missing:
        return True
    rows.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="fj:check", style="success")])
    tg_send(uid, "⛔️ برای استفاده از ربات ابتدا در کانال‌های زیر عضو شو، بعد «🔄 بررسی عضویت» را بزن!", InlineKeyboardMarkup(rows))
    return False

def handle_message(m: dict) -> None:
    chat_id = int(m["chat"]["id"])
    if (m.get("chat") or {}).get("type") != "private":
        return
    text = str(m.get("text") or "").strip()
    frm = m.get("from") or {}
    upsert_user(chat_id, frm.get("username"))
    admin = is_admin(chat_id)
    _CTX["mid"] = None

    if not admin and q_val("SELECT is_banned FROM users WHERE tg_id=?", (chat_id,), 0):
        tg_send(chat_id, "🚫 دسترسی شما به ربات مسدود شده است.")
        return
    if not bot_enabled() and not admin:
        tg_send(chat_id, "🔴 ربات موقتاً غیرفعال است — بعداً مراجعه کنید.")
        return

    if text == "/start" or text.startswith("/start "):
        st_pop(chat_id)
        tg_send(chat_id, welcome_text(frm), main_menu_kb(admin))
        return
    if text == LBL["test"]:
        if not feat_on("test", True) and not admin:
            tg_send(chat_id, "🧪 تست فعلاً بسته است.")
            return
        handle_test_start(chat_id)
        return
    if text == LBL["buy"]:
        if not feat_on("buy", True) and not admin:
            tg_send(chat_id, "🛒 فروش فعلاً بسته است.")
            return
        show_buy_screen(chat_id)
        return
    if text == LBL["services"]:
        services_home(chat_id)
        return
    if text == LBL["wallet"]:
        wallet_screen(chat_id)
        return
    if text == LBL["guide"]:
        show_guide(chat_id)
        return
    if text == LBL["conditions"]:
        show_conditions(chat_id)
        return
    if text == LBL["support"]:
        start_support(chat_id)
        return
    if text == LBL["faq"]:
        tg_send(chat_id, str(get_setting("faq_text") or "❓ سوالات متداول فعلاً تنظیم نشده."), main_menu_kb(admin))
        return
    if text == LBL["admin"]:
        if admin:
            tg_send(chat_id, "👨‍💼 پنل مدیریت", admin_menu_kb())
        return

    if m.get("photo") and str(st_get(chat_id, "await", "")) == "wallet_receipt":
        handle_wallet_receipt_photo(chat_id, m)
        return
    handle_state_message(chat_id, text, m)

def handle_state_message(chat_id: int, text: str, m: dict) -> None:
    await_ = str(st_get(chat_id, "await", "") or "")
    if text == "/cancel":
        st_pop(chat_id)
        tg_send(chat_id, "↩️ لغو شد.", main_menu_kb(is_admin(chat_id)))
        return
    if not await_:
        return
    admin = is_admin(chat_id)

    if await_ == "support_msg":
        if text == "🏠 بازگشت به منوی اصلی":
            st_pop(chat_id)
            tg_send(chat_id, "🏠 بازگشتید!", main_menu_kb(admin))
            return
        if not text:
            tg_send(chat_id, "❌ فقط پیام متنی ارسال کنید!")
            return
        st_pop(chat_id)
        tid = int(ex("INSERT INTO tickets(tg_id,message,status) VALUES(?,?,?)", (chat_id, text, "open")).lastrowid)
        tg_send(chat_id, "🚀 پیام شما ارسال شد؛ منتظر پاسخ پشتیبانی باشید.", main_menu_kb(admin))
        notify_admins(f"🤙 تیکت پشتیبانی #{tid}\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n\n{esc(text[:800])}",
                      ikb([InlineKeyboardButton("✉️ پاسخ", callback_data=f"um:msg:{chat_id}"), InlineKeyboardButton("✅ بستن تیکت", callback_data=f"tkclose:{tid}")]))
        return
    if await_ == "topup_amount":
        mm = re.search(r"(\d{4,})", text.replace(",", ""))
        if not mm:
            tg_send(chat_id, "عدد معتبر بفرست (مثلاً 100000) یا «🏠 بازگشت به منوی اصلی» بزن!")
            return
        amount = int(mm.group(1))
        mn, mx = int(get_setting("min_charge", 0) or 0), int(get_setting("max_charge", 0) or 0)
        if mn and amount < mn:
            tg_send(chat_id, f"⬇️ حداقل شارژ {fmt_price(mn)} است.")
            return
        if mx and amount > mx:
            tg_send(chat_id, f"⬆️ حداکثر شارژ {fmt_price(mx)} است.")
            return
        st_set(chat_id, {"await": "wallet_card", "amount": amount})
        wallet_card_sent(chat_id)
        return
    if await_ in ("card_wait", "wallet_card"):
        return
    if await_ == "gift_redeem":
        handle_gift_redeem(chat_id, text)
        return
    if await_ == "wallet_receipt":
        handle_wallet_receipt_text(chat_id, text)
        return
    if await_ == "buy_custom_username":
        handle_buy_custom_username(chat_id, text)
        return
    if await_ == "agent_gb":
        handle_agent_gb(chat_id, text)
        return
    if await_ == "buy_discount_code":
        handle_buy_discount_code(chat_id, text)
        return
    if await_.startswith("svcnewpass:"):
        service_change_password_apply(chat_id, text)
        return

    if not admin:
        return
    if await_.startswith("payapi:"):
        admin_pay_api_apply(chat_id, text)
    elif await_.startswith("helpedit_body:"):
        admin_help_body_edit(chat_id, await_, text)
    elif await_.startswith("rcfix:"):
        receipt_fix_apply(chat_id, text)
    elif await_ == "finduser":
        admin_finduser_apply(chat_id, text)
    elif await_ == "search_order":
        admin_search_order_apply(chat_id, text)
    elif await_ == "addchan":
        admin_channel_add_apply(chat_id, text)
    elif await_ == "helpadd_title":
        admin_help_title_apply(chat_id, text)
    elif await_ == "helpadd_body":
        admin_help_body_apply(chat_id, text)
    elif await_ in ("massbal", "mass_sub"):
        admin_massbal_apply(chat_id, text)
    elif await_ in ("um:addbal", "um:subbal"):
        admin_um_bal_apply(chat_id, text)
    elif await_ == "um:msg":
        admin_um_msg_apply(chat_id, text)
    elif await_ == "dsc_code":
        admin_dsc_code_apply(chat_id, text)
    elif await_ == "dsc_value":
        admin_dsc_value_apply(chat_id, text)
    elif await_ == "gift_code":
        admin_gift_code_apply(chat_id, text)
    elif await_ == "gift_amount":
        admin_gift_amount_apply(chat_id, text)
    elif await_ == "pnltest":
        admin_panel_test_apply(chat_id, text)
    elif await_ == "pladd_gb":
        admin_plan_gb_apply(chat_id, text)
    elif await_ == "pladd_price":
        admin_plan_price_apply(chat_id, text)
    elif await_ == "pled:price":
        admin_plan_edit_apply(chat_id, "price", text)
    elif await_ == "pled:gb":
        admin_plan_edit_apply(chat_id, "gb", text)
    elif await_.startswith("pnledit_"):
        admin_panel_field_apply(chat_id, await_[8:], text)
    elif await_ == "bcast2_text":
        bcast_text_received(chat_id, text)
    elif await_.startswith("set:"):
        if admin_set_apply(chat_id, await_[4:], text):
            st_pop(chat_id)
            admin_settings_home(chat_id)
    elif await_.startswith("pnladd_"):
        admin_panel_add_step(chat_id, await_, text)

def handle_update(u: dict) -> None:
    if get_setting("force_join", False) and not force_join_ok(u):
        return
    if "message" in u:
        handle_message(u["message"])
        return
    if "callback_query" in u:
        cq = u["callback_query"]
        if str(cq.get("data") or "") == "fj:check":
            uid = int(cq["from"]["id"])
            mid = int((cq.get("message") or {}).get("message_id") or 0)
            if mid:
                tg("editMessageText", {"chat_id": uid, "message_id": mid, "text": "✅ عضویت تأیید شد! خوش آمدی 🎉"})
            st_pop(uid)
            tg_send(uid, welcome_text({"first_name": cq["from"].get("first_name", "")}), main_menu_kb(is_admin(uid)))
            return
        try:
            handle_callback(cq)
        finally:
            _CTX["mid"] = None

def run_cron() -> None:
    ex("DELETE FROM pending_buys WHERE created_at <= datetime('now','localtime','-24 hours')")

    expired = q_all("SELECT * FROM agent_panels WHERE is_test=1 AND status='active' AND expires_at IS NOT NULL"
                    " AND expires_at <= datetime('now','localtime')")
    panels = get_panels()
    for rec in expired:
        if any(pc.get("base_url") == rec.get("panel_name") for pc in panels.values()):
            p = panel_client(str(rec["panel_name"]), str(rec["panel_type"] or "pasarguard"))
            if p:
                res = panel_call(p, "delete_admin", {"username": str(rec["panel_username"])})
                if not res or not res.get("ok"):
                    err = (res or {}).get("description") or (res or {}).get("message") or "خطای اتصال یا پاسخ ناموفق پنل"
                    msg = (f"⚠️ <b>حذف خودکار پنل تست ناموفق است</b>\n\n"
                           f"یوزرنیم تست: <code>{esc(str(rec['panel_username']))}</code>\n"
                           f"آدرس پنل: {esc(str(rec['panel_name']))}\n"
                           f"خطا: {esc(str(err))}\n\n"
                           f"ربات هر چند دقیقه دوباره تلاش می‌کند. اگر ادامه داشت، ادمین تست و یوزرهایش را دستی پاک کنید.")
                    notify_admins(msg)
        ex("UPDATE agent_panels SET status='expired' WHERE id=?", (int(rec["id"]),))
        tg_send(int(rec["tg_id"]), f"⌛️ سرویس تست «{rec['panel_username']}» منقضی شد ({str(rec['expires_at'])[:10]}).\n"
                                   "برای ادامه می‌تونی سرویس اصلی رو از «🔐 خرید اشتراک» بگیری.")
        bot_log(f"test expired -> uid={rec['tg_id']} user={rec['panel_username']}")

    warn_pct = int(get_setting("quota_warn_pct", 80) or 80)
    warn_disc = int(get_setting("quota_warn_discount_pct", 10) or 10)
    warn_tpl = str(get_setting("quota_warn_text", "") or (
        "سلام {name} عزیز 👋\n\n⚠️ شما {pct}٪ از سرویس <code>{user}</code> رو مصرف کردی.\n"
        "🎁 یه کد تخفیف {disc}٪ اختصاصی برات ساختم — تا ۲۴ ساعت مهلت داری:\n"
        "برای افزایش حجم با تخفیف، کد تخفیف: <code>{code}</code>"))
    remove_tpl = str(get_setting("autoremove_text", "") or (
        "🗑 سهمیه پنل {user} تمام شد و پنل به‌صورت خودکار حذف شد.\nبرای ادامه، حجم اضافه خریداری کن."))
    warned = get_setting("quota_warned", {}) or {}
    if not isinstance(warned, dict):
        warned = {}

    for ap in q_all("SELECT id, tg_id, panel_username, panel_name, panel_type, quota_gb, status FROM agent_panels"
                    " WHERE status='active' AND is_test=0 LIMIT 300"):
        if warned.get(str(ap["id"])):
            continue
        p = panel_client(ap["panel_name"], ap["panel_type"] or None)
        if not p:
            continue
        res = panel_call(p, "get_admin_info", {"username": ap["panel_username"]})
        if not res or not res.get("ok") or not res.get("data"):
            continue
        u = res["data"]
        used = float(u.get("used_traffic") or 0)
        total = float(u.get("usage_limit") or u.get("data_limit") or 0)
        if total <= 0:
            continue
        pct = used / total * 100.0
        if warn_pct <= pct < 100:
            code = f"WARN{int(ap['tg_id']) % 100000}{secrets.token_hex(2).upper()}"
            ex("INSERT INTO discount_codes(code, kind, value, max_uses, used, active, expires_at)"
               " VALUES(?, 'percent', ?, 1, 0, 1, datetime('now','localtime','+24 hours'))", (code, warn_disc))
            urow = q_one("SELECT username FROM users WHERE tg_id=?", (int(ap["tg_id"]),)) or {}
            name = urow.get("username") or "کاربر"
            msg = (warn_tpl.replace("{name}", name).replace("{user}", str(ap["panel_username"]))
                   .replace("{pct}", str(int(pct))).replace("{disc}", str(warn_disc)).replace("{code}", code))
            tg_send(int(ap["tg_id"]), msg, ikb([InlineKeyboardButton("➕ خرید حجم اضافه", callback_data=f"apgb:{ap['id']}", style="success")]))
            warned[str(ap["id"])] = 1
            set_setting("quota_warned", warned)
            bot_log(f"quota warn uid={ap['tg_id']} pct={int(pct)} code={code}")
        elif pct >= 100:
            tg_send(int(ap["tg_id"]), remove_tpl.replace("{user}", str(ap["panel_username"])))
            ex("UPDATE agent_panels SET status='exhausted' WHERE id=?", (int(ap["id"]),))
            # سرویس‌های اصلی نباید پاک شوند تا قابلیت تمدید داشته باشند
            # فقط وضعیت غیرفعال در پنل ست می‌شود (اگر پنل پشتیبانی کند)
            panel_call(p, "modify_admin_status", {"username": ap["panel_username"], "status": "disabled"})
            bot_log(f"panel exhausted (disabled only) uid={ap['tg_id']} user={ap['panel_username']}")

def main() -> None:
    if not BOT_TOKEN:
        print("BOT_TOKEN خالیه؛ بالای فایل پرش کن", file=sys.stderr)
        sys.exit(1)
    db_init()
    for _k, _v in (("support_id", SUPPORT_ID), ("card_number", CARD_NUMBER), ("card_owner", CARD_OWNER)):
        if _v:
            set_setting(_k, _v)
    admin_ids()
    tg("deleteWebhook", {"drop_pending_updates": False})
    bot_log("=== WireNest python bot started (long polling) ===")
    offset, last_cron, ticks = 0, 0.0, 0
    while True:
        ticks += 1
        if time.time() - last_cron >= 60:
            last_cron = time.time()
            try:
                run_cron()
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"cron error: {e}\n{tb}")
                notify_admins(f"⚠️ <b>خطای سیستم پس‌زمینه (Cron)</b>\n\n❗️ <code>{esc(str(e))}\n{esc(tb[-400:])}</code>")
        try:
            updates = _run(
                bot_obj().get_updates(
                    offset=offset,
                    timeout=25,
                    allowed_updates=["message", "callback_query"],
                    read_timeout=40,
                    write_timeout=40,
                    connect_timeout=40,
                    pool_timeout=40,
                ),
                70,
            )
        except Exception as e:
            bot_log(f"getUpdates error: {e}")
            time.sleep(3)
            continue
        for upd in updates:
            offset = upd.update_id + 1
            u = upd.to_dict()
            try:
                handle_update(u)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"update error: {e}\n{tb}")
                utype = "message" if "message" in u else ("callback_query" if "callback_query" in u else "unknown")
                uid = 0
                if utype == "message":
                    uid = int(((u.get("message") or {}).get("from") or {}).get("id") or 0)
                elif utype == "callback_query":
                    uid = int(((u.get("callback_query") or {}).get("from") or {}).get("id") or 0)
                err_msg = (
                    f"⚠️ <b>خطای ربات</b>\n"
                    f"🔧 نوع: {utype}\n"
                    f"👤 کاربر: {uid}\n"
                    f"❗️ <code>{esc(str(e))}\n{esc(tb[-500:])}</code>"
                )
                notify_admins(err_msg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass