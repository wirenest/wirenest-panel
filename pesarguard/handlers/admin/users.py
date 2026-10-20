from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import hashlib
import re
import time
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import add_balance, ex, get_balance, get_panels, q_all, q_one, q_val
from pesarguard.keyboards import back_adm_kb, ikb
from pesarguard.panel_api import panel_call, panel_client
from pesarguard.state import st_all, st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit, tg_send
from pesarguard.utils import esc, fmt_gb, fmt_price, jdate, num


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
