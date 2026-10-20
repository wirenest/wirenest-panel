from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import all_settings, get_setting, set_setting
from pesarguard.telegram_api import send_or_edit


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
