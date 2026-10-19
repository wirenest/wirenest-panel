import re, time, json, hashlib, urllib.parse
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from modules.database import *
from modules.utils import *
from modules.panel_api import *
from modules.keyboards import *
from handlers.user_handlers import admin_svc_view


def bcast_home(chat_id: int) -> None:
    send_or_edit(chat_id, "📣 <b>پیام همگانی</b>\nبه کدام گروه ارسال شود؟", ikb(
        [InlineKeyboardButton("👥 همه کاربران", callback_data="bcast2:all", style="primary"), InlineKeyboardButton("🛒 خریدارها", callback_data="bcast2:buyers")],
        [InlineKeyboardButton("🚫 خرید نداشته‌ها", callback_data="bcast2:nonbuyers", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:users")]))

AUD_LABELS = {"all": "همه کاربران", "buyers": "خریدارها", "nonbuyers": "خرید نداشته‌ها"}

def bcast_audience_pick(chat_id: int, aud: str) -> None:
    st_set(chat_id, {"await": "bcast2_text", "bcast_aud": aud})
    send_or_edit(chat_id, f"📣 متن پیام همگانی برای «{AUD_LABELS.get(aud, aud)}» را بفرست!")

def bcast_text_received(chat_id: int, text: str) -> None:
    st_set(chat_id, {"await": "bcast2_btn", "bcast_text": text})
    send_or_edit(chat_id, "📣 زیر پیام همگانی چه دکمه‌ای بگذارم؟", ikb(
        [InlineKeyboardButton("🔐 خرید اشتراک", callback_data="bcastbtn:buy", style="success"), InlineKeyboardButton("🧪 دریافت تست", callback_data="bcastbtn:test", style="primary")],
        [InlineKeyboardButton("☎️ پیام به پشتیبانی", callback_data="bcastbtn:support"), InlineKeyboardButton("📚 آموزش", callback_data="bcastbtn:help")],
        [InlineKeyboardButton("📤 ارسال بدون دکمه", callback_data="bcastbtn:none", style="danger")]))

def bcast_btn_pick(chat_id: int, b: str) -> None:
    if st_all(chat_id).get("await") != "bcast2_btn":
        send_or_edit(chat_id, "پیام یافت نشد — دوباره شروع کن!")
        return
    st_set(chat_id, {"bcast_btn": b})
    send_or_edit(chat_id, "📌 این پیام برای کاربر پین شود؟", ikb([InlineKeyboardButton("📌 بله، پین شود", callback_data="bcastgo:yes", style="success"), InlineKeyboardButton("🚫 خیر", callback_data="bcastgo:no", style="danger")]))

def bcast_run(chat_id: int, pin: bool) -> None:
    st = st_all(chat_id)
    if "bcast_text" not in st:
        send_or_edit(chat_id, "پیام یافت نشد.")
        return
    text, aud, b = str(st["bcast_text"]), str(st.get("bcast_aud", "all")), str(st.get("bcast_btn", "none"))
    st_pop(chat_id)
    if aud == "buyers":
        ids = [r["tg_id"] for r in q_all("SELECT DISTINCT tg_id FROM purchases")]
    elif aud == "nonbuyers":
        ids = [r["tg_id"] for r in q_all("SELECT tg_id FROM users WHERE is_banned=0 AND tg_id NOT IN (SELECT DISTINCT tg_id FROM purchases)")]
    else:
        ids = [r["tg_id"] for r in q_all("SELECT tg_id FROM users")]
    lbl = AUD_LABELS.get(aud, aud)
    btn_map = {"buy": ("🔐 خرید اشتراک", "m:buy"), "test": ("🧪 دریافت تست", "m:test"),
               "support": ("☎️ پیام به پشتیبانی", "m:support"), "help": ("📚 آموزش", "m:help")}
    kb = ikb([InlineKeyboardButton(btn_map[b][0], callback_data=btn_map[b][1], style="success")]) if b in btn_map else None
    total = len(ids)
    if not total:
        send_or_edit(chat_id, f"✅ ارسال تمام شد: 0 نفر ({lbl}).")
        return
    prog = tg_send(chat_id, f"📣 در حال ارسال به {total} نفر ({lbl})…\nارسال: 0.")
    prog_id = int((prog.get("result") or {}).get("message_id") or 0)

    def upd(t: str) -> None:
        if prog_id:
            tg("editMessageText", {"chat_id": chat_id, "message_id": prog_id, "text": t})
        else:
            tg_send(chat_id, t)

    sent = failed = 0
    BATCH = 15
    for i, uid in enumerate(ids, 1):
        time.sleep(0.25)
        resp = tg_send(uid, text, kb)
        ok = bool(resp.get("ok"))
        if not ok:
            time.sleep(0.3)
            resp = tg_send(uid, text, kb)
            ok = bool(resp.get("ok"))
        sent, failed = (sent + 1, failed) if ok else (sent, failed + 1)
        mid = int((resp.get("result") or {}).get("message_id") or 0)
        if pin and ok and mid:
            tg("pinChatMessage", {"chat_id": uid, "message_id": mid, "disable_notification": True})
        if i % BATCH == 0:
            upd(f"📣 در حال ارسال به {total} نفر ({lbl})…\nارسال: {sent} | خطا: {failed}")
            time.sleep(2)
    upd(f"✅ ارسال تمام شد: {sent} نفر ({lbl})" + (f" | ناموفق: {failed}" if failed else "") + (" — پیام پین شد. 📌" if pin else ""))

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

ROLE_LABELS = {2: "👑 مدیر کل", 3: "👤 اپراتور", 5: "🌐 CDN"}

def get_panel_role_label(panel: dict, role_id: int) -> str:
    try:
        tok = _panel_auth(panel)
        if tok:
            r = _preq(panel, 'GET', '/api/admin-roles/simple', token=tok)
            if r.status_code == 200:
                for role in r.json().get('roles', []):
                    if role.get('id') == role_id:
                        return f"🛡 {role.get('name')}"
    except Exception:
        pass
    return ROLE_LABELS.get(role_id, f"نقش {role_id}")


def admin_panels_home(chat_id: int) -> None:
    kb = [[InlineKeyboardButton(f"🌐 {n}", callback_data="pnl:view:" + n), InlineKeyboardButton("🔍 تست", callback_data="pnl:ping:" + n)] for n in get_panels()]
    kb.append([InlineKeyboardButton("➕ افزودن پنل", callback_data="pnl:add", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🌐 پنل‌های متصل:", InlineKeyboardMarkup(kb))

def admin_panel_view(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    active = d.get("active", name == str(get_setting("selected_panel", "") or ""))
    plans = q_all("SELECT * FROM panel_plans WHERE panel_name=? ORDER BY volume_gb", (name,))
    kb = []
    for pl in plans:
        mark = "" if pl["active"] else "❌ "
        kb.append([InlineKeyboardButton(f"{mark}{g2(pl['volume_gb'])} گیگ — {num(pl['price'])} ت", callback_data=f"pl:{name}:{pl['id']}")])
    kb.append([InlineKeyboardButton("➕ افزودن پلن حجمی +", callback_data=f"pladd:{name}", style="success")])
    xprice, xmin = int(d.get("extra_gb_price") or 0), int(d.get("extra_gb_min") or 0)
    role_lbl = get_panel_role_label(d, int(d.get("role_id") or 3))
    kb.append([InlineKeyboardButton(f"🛡 نقش مدیران: {role_lbl}", callback_data=f"pnlrolepick:{name}")])
    kb.append([InlineKeyboardButton("💰 قیمت حجم: " + (f"{num(xprice)} ت" if xprice else "— تنظیم نشده"), callback_data=f"pnledit:extra_price:{name}"),
               InlineKeyboardButton("⚖️ حداقل حجم: " + (f"{xmin} گیگ" if xmin else "— تنظیم نشده"), callback_data=f"pnledit:extra_min:{name}")])
    kb.append([InlineKeyboardButton("📊 آمار پنل", callback_data=f"pnl:stats:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش نام پنل", callback_data=f"pnledit:name:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش آدرس پنل", callback_data=f"pnledit:url:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("✏️ ویرایش پسورد ادمین", callback_data=f"pnledit:pass:{name}")])
    kb.append([InlineKeyboardButton("🧪 سرویس تست: ✅ روشن" if d.get("is_test_panel") else "🧪 سرویس تست: ⛔️ خاموش", callback_data=f"pnl:testtoggle:{name}"),
               InlineKeyboardButton("⚙️ حجم/مدت تست", callback_data=f"pnl:test:{name}")])
    kb.append([InlineKeyboardButton("🔴 غیرفعال کن" if active else "🟢 فعال کن", callback_data=f"pnl:toggle:{name}")])
    kb.append([InlineKeyboardButton("🗑 حذف این پنل", callback_data=f"askdel:pnl:{name}", style="danger")])
    kb.append([InlineKeyboardButton("◀️ پنل‌ها", callback_data="adm:panels")])
    send_or_edit(chat_id, f"🛠 مدیریت پنل «{esc(name)}» ({d.get('ptype', 'pasarguard')})\n"
                          f"{'🟢 فعال (قابل خرید)' if active else '🔴 غیرفعال'}\n🔗 {esc(d.get('base_url'))}\n\n📦 پلن‌های حجمی این پنل:",
                 InlineKeyboardMarkup(kb))

def admin_panel_ping(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    tg_send(chat_id, f"🔍 در حال تست {esc(name)} ...")
    r = panel_ping(d)
    send_or_edit(chat_id, f"🟢 وصله — {esc(name)}" if r.get("ok") else f"🔴 قطعه — {esc(name)}")

def admin_panel_add_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "pnladd_name"})
    send_or_edit(chat_id, "🏷 اسم پنل رو بفرست (همین اسم به کاربر نشون داده می‌شه، مثلاً: سرور1)!")

def admin_panel_delete_confirm(chat_id: int, name: str) -> None:
    send_or_edit(chat_id, f"⚠️ «{esc(name)}» برای همیشه حذف بشه؟ این عملیات غیرقابل‌بازگشته!",
                 ikb([InlineKeyboardButton("🔥 بله، حذف کن", callback_data="okdel:pnl:" + name, style="danger")], [InlineKeyboardButton("🚫 نه", callback_data="adm:panels")]))

def admin_panel_delete_apply(chat_id: int, name: str) -> None:
    st_pop(chat_id)
    panels = get_panels()
    panels.pop(name, None)
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🗑 پنل «{esc(name)}» حذف شد.", admin_menu_kb())

def admin_panel_add_step(chat_id: int, await_: str, text: str) -> None:
    if await_ == "pnladd_name":
        name = text.strip()
        if not name:
            send_or_edit(chat_id, "❌ اسم پنل نمی‌تونه خالی باشه، دوباره بفرست!")
            return
        if not valid_panel_name(name):
            send_or_edit(chat_id, "❌ اسم پنل باید حداکثر ۱۴ حرف باشد و شامل «:» یا «%» نباشد. دوباره بفرست!")
            return
        if name in get_panels():
            send_or_edit(chat_id, f"❌ پنلی با اسم «{esc(name)}» از قبل ثبت شده. اسم دیگه‌ای بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_url", "pnl_name": name})
        send_or_edit(chat_id, "🔗 آدرس پنل رو بفرست ( https://example.ir/dashboard)!")
    elif await_ == "pnladd_url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_user", "pnl_url": panel_clean_base_url(text.strip())})
        send_or_edit(chat_id, "👤 یوزرنیم ادمین پنل را بفرست!")
    elif await_ == "pnladd_user":
        st_set(chat_id, {"await": "pnladd_pass", "pnl_user": text.strip()})
        send_or_edit(chat_id, "🔑 پسورد ادمین پنل را بفرست!")
    elif await_ == "pnladd_pass":
        name, url, user = str(st_get(chat_id, "pnl_name", "")), str(st_get(chat_id, "pnl_url", "")), str(st_get(chat_id, "pnl_user", ""))
        pw = text.strip()
        st_pop(chat_id)
        send_or_edit(chat_id, "🔍 در حال تست اتصال...")
        r = panel_ping({"base_url": url, "username": user, "password": pw, "ptype": "pasarguard"})
        if not r.get("ok"):
            send_or_edit(chat_id, "❌ لاگین ناموفق\nدوباره از «➕ افزودن پنل» شروع کن.")
            return
        panels = get_panels()
        final = name or f"پنل {len(panels) + 1}"
        i = 2
        while final in panels:
            final = f"{name} {i}"
            i += 1
        panels[final] = {"base_url": url, "username": user, "password": panel_encrypt_pw(pw), "ptype": "pasarguard", "active": True}
        set_setting("panels", panels)
        send_or_edit(chat_id, f"✅ پنل «{esc(final)}» اضافه و وصل شد.", admin_menu_kb())

def admin_panel_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    panels[name]["active"] = not panels[name].get("active")
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🟢 پنل «{esc(name)}» فعال شد." if panels[name]["active"] else f"🔴 پنل «{esc(name)}» غیرفعال شد.")
    admin_panel_view(chat_id, name)

def admin_panel_edit_start(chat_id: int, name: str) -> None:
    if name not in get_panels():
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    send_or_edit(chat_id, f"✏️ چه چیزی از پنل «{esc(name)}» ویرایش بشه؟", ikb(
        [InlineKeyboardButton("📛 نام پنل", callback_data=f"pnledit:name:{name}")], [InlineKeyboardButton("🔗 آدرس پنل", callback_data=f"pnledit:url:{name}")],
        [InlineKeyboardButton("👤 یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("🔑 پسورد ادمین", callback_data=f"pnledit:pass:{name}")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_panel_test_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    d["is_test_panel"] = not d.get("is_test_panel")
    note = ""
    if d["is_test_panel"] and (not d.get("test_gb") or not d.get("test_days")):
        d["test_gb"] = d.get("test_gb") or 1
        d["test_days"] = d.get("test_days") or 1
        note = "\n⚙️ حجم/مدت ست نبود — دیفالت 1 گیگ / 1 روز اعمال شد (از «⚙️ حجم/مدت تست» قابل تغییر است)."
    set_setting("panels", panels)
    send_or_edit(chat_id, ("🧪 سرویس تست روشن شد." if d["is_test_panel"] else "🧪 سرویس تست خاموش شد.") + note)
    admin_panel_view(chat_id, name)

def admin_panel_test_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pnltest", "pnltest_name": name})
    send_or_edit(chat_id, "🖊 مشخصات سرویس تست را بفرست (دو خط):\n\nحجم به گیگ: مثلا 1\nمدت به روز: مثلا 1\n\n"
                          "(این پنل برای سرویس‌های تست کاربران استفاده خواهد شد).", cancel_kb())

def valid_panel_name(name: str) -> bool:
    return bool(name) and ":" not in name and "%" not in name and len(name.encode("utf-8")) <= 28

def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False

def admin_panel_test_apply(chat_id: int, text: str) -> None:
    name = str(st_get(chat_id, "pnltest_name", ""))
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2 or not _is_num(lines[0]) or not _is_num(lines[1]):
        send_or_edit(chat_id, "❌ فرمت درست نیست. دو خط بفرست:\nحجم (گیگ)\nمدت (روز) — مثلا:\n1\n1.")
        return
    panels = get_panels()
    if name in panels:
        panels[name]["test_gb"] = float(lines[0])
        panels[name]["test_days"] = int(float(lines[1]))
        set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, f"✅ سرویس تست ثبت شد: {lines[0]} گیگ / {lines[1]} روز.")
    admin_panel_view(chat_id, name)

def admin_panel_rolepick(chat_id: int, name: str) -> None:
    panels = get_panels()
    p = panels.get(name)
    if not p:
        send_or_edit(chat_id, "❌ پنل یافت نشد.")
        return
    rows = []
    tok = _panel_auth(p)
    if tok:
        try:
            r = _preq(p, "GET", "/api/admin-roles/simple", token=tok)
            if r.status_code == 200:
                roles = r.json().get("roles") or []
                for role in roles:
                    rname = str(role.get("name", "")).strip().lower()
                    if role.get("is_owner") or rname in ("owner", "administrator", "مدیر کل", "مدیرکل"):
                        continue
                    r_id = role["id"]
                    r_name = role.get("name") or f"نقش {r_id}"
                    rows.append([InlineKeyboardButton(f"🛡 {r_name}", callback_data=f"pnlrole:{r_id}:{name}")])
        except Exception:
            pass
    if not rows:
        rows = [
            [InlineKeyboardButton("👑 مدیر کل (همه‌چیز)", callback_data=f"pnlrole:2:{name}")],
            [InlineKeyboardButton("👤 اپراتور (ساخت سرویس)", callback_data=f"pnlrole:3:{name}")],
            [InlineKeyboardButton("🌐 CDN (فقط سرویس)", callback_data=f"pnlrole:5:{name}")],
        ]
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")])
    send_or_edit(chat_id, f"🛡 نقش مدیران ساخته‌شده توسط ربات در «{esc(name)}»:", InlineKeyboardMarkup(rows))

def admin_panel_role_set(chat_id: int, rid: int, name: str) -> None:
    panels = get_panels()
    if name in panels:
        panels[name]["role_id"] = rid
        set_setting("panels", panels)
        lbl = get_panel_role_label(panels[name], rid)
    else:
        lbl = f"نقش {rid}"
    send_or_edit(chat_id, f"✅ نقش مدیران: {lbl}")
    admin_panel_view(chat_id, name)

def admin_panel_stats(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    send_or_edit(chat_id, "📊 در حال دریافت آمار...")
    r = panel_call(d, "stats", {}) or {}
    if r.get("ok"):
        nadmins, ver = int(r.get("admins_count") or 0), r.get("version", "—")
        ram_t, ram_u, traffic, status = r.get("ram_total_gb", "—"), r.get("ram_used_gb", "—"), r.get("traffic_tb", "—"), "✅ پنل متصل است."
    else:
        nadmins, ver, ram_t, ram_u, traffic, status = 0, "—", "—", "—", "—", "🔴 قطع"
    row = q_one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM purchases WHERE status='active'") or {"c": 0, "s": 0}
    send_or_edit(
        chat_id,
        f"📊 آمار پنل شما 👇\n\n🖥 وضعیت اتصال: {status}\n👥 تعداد مدیران ساخته شده در پنل: {nadmins}\n"
        f"📡 نسخه پنل: {ver}\n💻 رم کل سرور: {ram_t} گیگابایت\n💻 مصرف رم پنل: {ram_u} گیگابایت\n"
        f"🌐 ترافیک کل مصرف شده: {traffic} ترابایت\n🛍 تعداد فروش کل در این پنل: {row['c']}\n"
        f"🛍 جمع فروش کل: {num(row['s'])} تومان",
    )

def admin_plan_add_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pladd_gb", "plan_panel": name})
    send_or_edit(chat_id, "➕ حجم پلن را بفرست (گیگ): مثلا 100!", cancel_kb())

def admin_plan_gb_apply(chat_id: int, text: str) -> None:
    gb = text.strip()
    if not _is_num(gb) or float(gb) <= 0:
        send_or_edit(chat_id, "❌ عدد گیگ نامعتبر. دوباره بفرست (مثلا 100)!")
        return
    st_set(chat_id, {"await": "pladd_price", "plan_gb": float(gb)})
    send_or_edit(chat_id, "💰 قیمت این پلن را بفرست (تومان): مثلا 300000!")

def admin_plan_price_apply(chat_id: int, text: str) -> None:
    price = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(price) or int(float(price)) <= 0:
        send_or_edit(chat_id, "❌ قیمت نامعتبر. دوباره بفرست (تومان)!")
        return
    name, gb = str(st_get(chat_id, "plan_panel", "")), float(st_get(chat_id, "plan_gb", 0))
    st_pop(chat_id)
    ex("INSERT INTO panel_plans(panel_name, volume_gb, price, active) VALUES(?,?,?,1)", (name, gb, int(float(price))))
    send_or_edit(chat_id, f"✅ پلن افزوده شد: {g2(gb)} گیگ — {num(float(price))} ت.")
    admin_panel_view(chat_id, name)

def admin_plan_view(chat_id: int, name: str, pid: int) -> None:
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    if not pl:
        send_or_edit(chat_id, "پلن یافت نشد.")
        return
    send_or_edit(chat_id, f"📦 پلن {g2(pl['volume_gb'])} گیگ\n💰 قیمت: {num(pl['price'])} تومان\n" + ("🟢 فعال" if pl["active"] else "🔴 غیرفعال"),
                 ikb([InlineKeyboardButton("✏️ ویرایش قیمت", callback_data=f"pled:{pid}:price:{name}"), InlineKeyboardButton("✏️ ویرایش حجم", callback_data=f"pled:{pid}:gb:{name}")],
                     [InlineKeyboardButton("🔴 غیرفعال کن" if pl["active"] else "🟢 فعال کن", callback_data=f"pltog:{pid}:{name}")],
                     [InlineKeyboardButton("🗑 حذف پلن", callback_data=f"okdel:plan:{pid}:{name}", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_plan_edit_prompt(chat_id: int, pid: int, field: str, name: str) -> None:
    st_set(chat_id, {"await": f"pled:{field}", "pled_pid": pid, "pled_panel": name})
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    cur = (f"{num(pl['price'])} تومان" if field == "price" else f"{g2(pl['volume_gb'])} گیگ") if pl else "—"
    send_or_edit(chat_id, f"✏️ مقدار فعلی: {cur}\n\nمقدار جدید {'قیمت (تومان)' if field == 'price' else 'حجم (گیگ)'} را بفرست!", cancel_kb())

def admin_plan_edit_apply(chat_id: int, field: str, text: str) -> None:
    pid, name = int(st_get(chat_id, "pled_pid", 0) or 0), str(st_get(chat_id, "pled_panel", ""))
    v = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(v) or float(v) <= 0:
        send_or_edit(chat_id, "❌ مقدار نامعتبر. دوباره بفرست!")
        return
    if field == "price":
        ex("UPDATE panel_plans SET price=? WHERE id=?", (int(float(v)), pid))
    else:
        ex("UPDATE panel_plans SET volume_gb=? WHERE id=?", (float(v), pid))
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ پلن ویرایش شد.")
    admin_plan_view(chat_id, name, pid)

def admin_plan_toggle(chat_id: int, pid: int, name: str) -> None:
    ex("UPDATE panel_plans SET active = 1 - active WHERE id=?", (pid,))
    admin_plan_view(chat_id, name, pid)

def admin_plan_delete(chat_id: int, pid: int, name: str) -> None:
    ex("DELETE FROM panel_plans WHERE id=?", (pid,))
    send_or_edit(chat_id, "🗑 پلن حذف شد.")
    admin_panel_view(chat_id, name)

def admin_panel_field_edit(chat_id: int, field: str, name: str) -> None:
    cur = get_panels().get(name, {})
    curval = {"user": cur.get("username", ""), "pass": "••••••", "url": cur.get("base_url", ""), "name": name,
              "extra_price": cur.get("extra_gb_price", ""), "extra_min": cur.get("extra_gb_min", "")}.get(field, "")
    st_set(chat_id, {"await": f"pnledit_{field}", "edit_pnl": name})
    hints = {"extra_price": "قیمت حجم اضافه به تومان برای هر گیگ (مثلاً 6000)!", "extra_min": "حداقل گیگ قابل خرید حجم اضافه (مثلاً 10)!",
             "name": "نام جدید پنل را بفرست!", "url": "آدرس جدید پنل را بفرست!", "user": "یوزر ادمین جدید را بفرست!",
             "pass": "پسورد ادمین جدید را بفرست!"}
    send_or_edit(chat_id, "✏️ مقدار فعلی: " + (str(curval) if curval not in ("", None) else "— تنظیم نشده") + "\n\n" + hints.get(field, "مقدار جدید را بفرست:"), cancel_kb())

def admin_panel_field_apply(chat_id: int, field: str, text: str) -> None:
    name = str(st_get(chat_id, "edit_pnl", ""))
    text = text.strip()
    panels = get_panels()
    if name not in panels:
        st_pop(chat_id)
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    if field == "name":
        if not valid_panel_name(text) or (text in panels and text != name):
            send_or_edit(chat_id, "❌ نام نامعتبر یا تکراری است (حداکثر ۱۴ حرف، بدون «:» و «%»). دوباره بفرست!")
            return
        panels = {(text if k == name else k): v for k, v in panels.items()}
        ex("UPDATE panel_plans SET panel_name=? WHERE panel_name=?", (text, name))
        set_setting("panels", panels)
        st_pop(chat_id)
        send_or_edit(chat_id, "✅ نام پنل شد: " + text)
        admin_panel_view(chat_id, text)
        return
    if field == "url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        panels[name]["base_url"] = panel_clean_base_url(text)
    elif field == "user":
        panels[name]["username"] = text
    elif field == "pass":
        panels[name]["password"] = panel_encrypt_pw(text)
    elif field == "extra_price":
        if not _is_num(text) or int(float(text)) < 0:
            send_or_edit(chat_id, "❌ قیمت نامعتبر (عدد تومان بفرست، 0 = حذف)!")
            return
        panels[name]["extra_gb_price"] = int(float(text))
    elif field == "extra_min":
        if not _is_num(text) or int(float(text)) < 1:
            send_or_edit(chat_id, "❌ حداقل نامعتبر (عدد گیگ بفرست)!")
            return
        panels[name]["extra_gb_min"] = int(float(text))
    else:
        st_pop(chat_id)
        return
    set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ ذخیره شد.")
    admin_panel_view(chat_id, name)
