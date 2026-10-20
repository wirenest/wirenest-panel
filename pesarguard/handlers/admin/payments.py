from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.constants import PAY_METHODS
from pesarguard.database import get_setting, set_setting
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit


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
