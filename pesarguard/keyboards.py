from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from pesarguard.constants import LBL
from pesarguard.database import get_setting
from pesarguard.utils import fmt_gb, fmt_price


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
