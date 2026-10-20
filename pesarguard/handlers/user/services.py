from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.crypto import panel_decrypt_pw, panel_encrypt_pw
from pesarguard.database import add_balance, ex, get_balance, get_panels, get_setting, is_admin, q_all, q_one, q_val, set_setting, spend_balance
from pesarguard.handlers.user.buy import report_purchase
from pesarguard.handlers.user.wallet import wallet_card_sent
from pesarguard.keyboards import ikb, main_menu_kb
from pesarguard.panel_api import panel_call, panel_client, panel_login_url
from pesarguard.state import st_all, st_get, st_pop, st_set
from pesarguard.telegram_api import notify_admins, send_or_edit
from pesarguard.utils import esc, fmt_price, g2, num


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
