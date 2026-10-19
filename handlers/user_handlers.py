import re, sqlite3, json, time, secrets, urllib.parse
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from modules.config import bot_log, ADMIN_ID
from modules.database import *
from modules.utils import *
from modules.panel_api import *
from modules.keyboards import *


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
