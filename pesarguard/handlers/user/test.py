from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.crypto import panel_encrypt_pw
from pesarguard.database import ex, get_panels, get_setting, is_admin, q_val
from pesarguard.handlers.user.buy import report_purchase
from pesarguard.keyboards import ikb, main_menu_kb
from pesarguard.panel_api import panel_call, panel_client, panel_login_url
from pesarguard.telegram_api import notify_admins, send_or_edit, tg_send
from pesarguard.utils import esc, fmt_gb, g2, strong_password


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
