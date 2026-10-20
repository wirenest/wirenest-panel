from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.constants import FEATURE_ITEMS, NUMERIC_KEYS, SET_PROMPTS, TXT_KEYS
from pesarguard.database import all_settings, bot_enabled, get_setting, set_setting
from pesarguard.keyboards import cancel_kb, feat_on, features, ikb
from pesarguard.state import st_pop, st_set
from pesarguard.telegram_api import send_or_edit


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
