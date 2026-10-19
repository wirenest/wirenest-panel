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
