from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from modules.utils import num, fmt_price, fmt_gb

def ikb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(b[0], callback_data=b[1]) if isinstance(b, tuple) else b for b in r] for r in rows if r])

def main_menu_kb(admin: bool = False) -> ReplyKeyboardMarkup:
    btns = [
        [KeyboardButton("🛒 خرید سرویس"), KeyboardButton("🌐 سرویس‌های من")],
        [KeyboardButton("💰 کیف پول"), KeyboardButton("🎁 تست رایگان")],
        [KeyboardButton("📌 راهنما / شرایط"), KeyboardButton("🎧 پشتیبانی")]
    ]
    if admin:
        btns.append([KeyboardButton("⚙️ پنل مدیریت")])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

def admin_menu_kb() -> InlineKeyboardMarkup:
    return ikb(
        [("📊 آمار فروش", "adm_stats"), ("📩 پیام همگانی", "adm_bcast")],
        [("👥 مدیریت کاربران", "adm_users"), ("🖥 مدیریت پنل‌ها", "adm_panels")],
        [("📦 رسیدهای واریزی", "adm_receipts"), ("⚙️ تنظیمات ربات", "adm_settings")],
        [("🔙 بازگشت به منوی اصلی", "user_home")]
    )

def support_kb() -> InlineKeyboardMarkup:
    return ikb(
        [("🎧 ارسال پیام پشتیبانی", "sup_send")],
        [("🔙 بازگشت", "user_home")]
    )

def wallet_kb() -> InlineKeyboardMarkup:
    return ikb(
        [("💳 کارت به کارت", "topup_card"), ("🎁 ثبت کد هدیه", "redeem_gift")],
        [("📜 رسیدهای من", "my_receipts")],
        [("🔙 بازگشت", "user_home")]
    )

def cancel_kb() -> InlineKeyboardMarkup:
    return ikb([("❌ انصراف", "cancel")])

def back_adm_kb() -> InlineKeyboardMarkup:
    return ikb([("🔙 بازگشت به پنل مدیریت", "adm_home")])
