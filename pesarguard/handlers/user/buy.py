from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.crypto import panel_encrypt_pw
from pesarguard.database import add_balance, ex, get_balance, get_panels, get_setting, is_admin, q_all, q_one, spend_balance
from pesarguard.keyboards import buy_kb, ikb, main_menu_kb
from pesarguard.panel_api import panel_call, panel_client, panel_create_admin, panel_login_url
from pesarguard.state import st_all, st_get, st_pop, st_set
from pesarguard.telegram_api import bot_username, notify_admins, send_or_edit, tg_send
from pesarguard.utils import esc, fmt_gb, fmt_price, gen_username, jdate, mask_mid, num, strong_password


def report_purchase(tg_id: int, uname: str, plan_title: str, amount: int, tag: str, panel_url: str = "") -> None:
    rg = str(get_setting("report_group", "") or "")
    if not rg:
        return
    h = {"تست": "#تست", "افزایش": "#افزایش_حجم"}.get(tag, "#خرید_پنل")
    txt = (
        "🛒 <b>گزارش خرید پنل</b>\n"
        f"🗓 {jdate()} — ⏰ {datetime.now().strftime('%H:%M:%S')}\n"
        f"\n👤 کاربر:  {mask_mid(str(tg_id))}\n"
        f"🆔 سرویس: {mask_mid(uname)}\n"
        f"📦 پلن: {esc(plan_title)}\n"
        f"💵 مبلغ: {fmt_price(amount)}\n"
        f"{h}\n"
    )
    bot = bot_username()
    kb = None
    if bot:
        txt += f"🤖 ربات: @{bot}\n"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🌐 ورود به پنل‌ساز", url="https://t.me/" + bot, style="success")]])
    tg_send(rg, txt, kb)

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
