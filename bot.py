import sys, time, traceback, secrets
from telegram import Bot
from telegram.constants import ParseMode
from modules.config import *
from modules.database import *
from modules.utils import *
from modules.panel_api import *
from modules.keyboards import *
from handlers.user_handlers import *
from handlers.admin_handlers import *


def handle_callback(cq: dict) -> None:
    chat_id = int(cq["from"]["id"])
    data = str(cq.get("data") or "")
    _CTX["mid"] = int((cq.get("message") or {}).get("message_id") or 0) or None
    tg("answerCallbackQuery", {"callback_query_id": cq["id"]})
    admin = is_admin(chat_id)

    if not admin and q_val("SELECT is_banned FROM users WHERE tg_id=?", (chat_id,), 0):
        tg_send(chat_id, "🚫 دسترسی شما به ربات مسدود شده است.")
        return

    if data.startswith(("buyplan:", "confirmplan:", "paybalplan:", "apdc:", "confirm:", "paybal:", "buy:")) or data == "cancelbuy":
        handle_buy_callback(chat_id, data)
        return
    if data == "m:home":
        st_pop(chat_id)
        send_or_edit(chat_id, "🏠 منوی اصلی:", main_menu_kb(admin))
        return
    if data == "m:buy":
        show_buy_screen(chat_id)
        return
    if data == "m:test":
        handle_test_start(chat_id)
        return
    if data == "m:support":
        start_support(chat_id)
        return
    if data == "m:help":
        show_guide(chat_id)
        return
    if data == "m:services":
        services_home(chat_id)
        return
    if data == "topup":
        start_topup(chat_id)
        return
    if data == "myreceipts" or data == "wal:receipts":
        my_receipts(chat_id)
        return
    if data == "m:tkt":
        st_set(chat_id, {"await": "support_msg"})
        tg_send(chat_id, "✍️ پیامت را بنویس (ارسال به پشتیبانی)!")
        return
    if data == "wal:addcredit":
        wallet_add_credit(chat_id)
        return
    if data == "wal:gift":
        start_gift_redeem(chat_id)
        return
    if data == "wal:receipt":
        st_set(chat_id, {"await": "wallet_receipt"})
        send_or_edit(chat_id, "✉️ کد پیگیری واریز را بفرست (یا عکس رسید)!")
        return
    if data.startswith("xgpay:"):
        parts = (data.split(":") + ["0", "0", "0"])[:4]
        extra_gb_invoice_confirm(chat_id, int(parts[1]), int(parts[2]), int(parts[3]))
        return
    if data == "xgcancel":
        extra_gb_invoice_cancel(chat_id)
        return
    if data.startswith("guide:"):
        t = q_one("SELECT content FROM guide_topics WHERE id=? LIMIT 1", (int(data[6:]),))
        send_or_edit(chat_id, str(t["content"]) if t else "راهنمایی ثبت نشده.",
                     ikb([InlineKeyboardButton("◀️ بازگشت به لیست پلتفرم‌ها", callback_data="m:help")], [InlineKeyboardButton("🏠 منوی اصلی", callback_data="m:home")]))
        return
    if data.startswith("apchpw:"):
        service_change_password_start(chat_id, int(data[7:]))
        return
    if data.startswith("apcreds:"):
        service_login_info(chat_id, int(data[8:]))
        return
    if data.startswith("aptoggle:"):
        service_toggle(chat_id, int(data[9:]))
        return
    if data.startswith("apgb:"):
        service_extra_gb_start(chat_id, int(data[5:]))
        return
    if data.startswith("svc:"):
        parts = data.split(":")
        svc_id = int(parts[1])
        if len(parts) == 2:
            service_screen(chat_id, svc_id)
        elif parts[2] == "info":
            service_login_info(chat_id, svc_id)
        elif parts[2] == "pass":
            service_change_password_start(chat_id, svc_id)
        elif parts[2] == "ext":
            tg_send(chat_id, "برای حجم اضافه با پشتیبانی در تماس باش یا از 🔐 خرید اشتراک استفاده کن.")
        return
    if data.startswith("testpick:"):
        handle_test_pick(chat_id, urldec(data[9:]))
        return
    if not admin and data.startswith("um:msg:"):
        if int(data[7:]) == chat_id:
            st_set(chat_id, {"await": "support_msg"})
            send_or_edit(chat_id, "✍️ پاسخت را بنویس (ارسال به پشتیبانی)!")
        else:
            tg_send(chat_id, "⛔️ فقط ادمین.")
        return

    if not admin:
        tg_send(chat_id, "⛔️ فقط ادمین.")
        return

    simple = {
        "adm:general": admin_general_home, "adm:shopgeneral": admin_shopgeneral_home, "adm:power": admin_power_home,
        "adm:stats": admin_stats, "adm:receipts": admin_receipts_queue, "adm:users": admin_users_home,
        "adm:finduser": admin_finduser_start, "adm:search": admin_findorder_start, "adm:tickets": admin_tickets,
        "adm:discounts": admin_discounts_home, "adm:settings": admin_settings_home, "adm:payments": admin_payments_home,
        "adm:appearance": admin_appearance_home,
        "adm:gifts": admin_gifts_home, "adm:helps": admin_guide_home, "adm:guides": admin_guide_home,
        "adm:features": admin_features_home, "adm:panels": admin_panels_home, "adm:bcast": bcast_home,
        "set:channels": admin_channels_home, "addchan": admin_channel_add_start, "pnl:add": admin_panel_add_start,
        "helpadd": admin_help_add, "setcancel": admin_set_cancel,
    }
    if data in simple:
        simple[data](chat_id)
        return
    if data == "adm:back":
        st_pop(chat_id)
        send_or_edit(chat_id, "👨‍💼 پنل مدیریت:", admin_menu_kb())
        return
    if data == "adm:massbal":
        admin_massbal_start(chat_id, "add")
        return
    if data == "adm:masssub":
        admin_massbal_start(chat_id, "sub")
        return
    if data == "svcnoop":
        return
    if data.startswith("svcview:"):
        admin_svc_view(chat_id, int(data[8:]))
    elif data.startswith("svcordel:"):
        admin_svc_orderdel(chat_id, int(data[9:]))
    elif data.startswith("svcrefund:"):
        admin_svc_refund(chat_id, int(data[10:]))
    elif data.startswith("svcfulldel:"):
        admin_svc_fulldel(chat_id, int(data[11:]))
    elif data.startswith("umrepl:"):
        admin_umrepl(chat_id, data)
    elif data.startswith("paytoggle:"):
        pp = data.split(":")
        admin_pay_toggle(chat_id, pp[1], len(pp) > 2 and pp[2] == "cfg")
    elif data.startswith("paycfg:"):
        admin_pay_cfg(chat_id, data[7:])
    elif data.startswith("payapi:"):
        admin_pay_api_start(chat_id, data[7:])
    elif data.startswith(("rcok:", "rcno:")):
        handle_receipt_review(chat_id, data)
    elif data.startswith("rcfix:"):
        receipt_fix_start(chat_id, int(data[6:]))
    elif data.startswith("tkclose:"):
        admin_ticket_close(chat_id, int(data[8:]))
    elif data.startswith("um:"):
        admin_user_action(chat_id, data)
    elif data.startswith("bcast2:"):
        bcast_audience_pick(chat_id, data[7:])
    elif data.startswith("bcastbtn:"):
        bcast_btn_pick(chat_id, data[9:])
    elif data.startswith("bcastgo:"):
        bcast_run(chat_id, data[8:] == "yes")
    elif data.startswith("feat:"):
        admin_feature_toggle(chat_id, data[5:])
    elif data.startswith("delchan:"):
        admin_channel_delete(chat_id, urllib.parse.unquote_plus(data[8:]))
    elif data == "set:force_join":
        set_setting("force_join", not bool(get_setting("force_join", False)))
        admin_shopgeneral_home(chat_id)
    elif data.startswith("setcol:"):
        admin_appearance_setcol(chat_id, data[7:])
    elif data == "toggleemoji":
        admin_appearance_toggle_emoji(chat_id)
    elif data.startswith("set:"):
        admin_set_prompt(chat_id, data[4:])
    elif data in ("dsc:add", "gift:add", "disc:new"):
        admin_code_add_start(chat_id, "dsc" if data != "gift:add" else "gift")
    elif data.startswith(("okdel:discount:", "okdel:gift:")):
        admin_code_delete(chat_id, data)
    elif data.startswith("pnl:edit:"):
        admin_panel_edit_start(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:toggle:"):
        admin_panel_toggle(chat_id, urldec(data[11:]))
    elif data.startswith("pnl:view:"):
        admin_panel_view(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:ping:"):
        admin_panel_ping(chat_id, urldec(data[9:]))
    elif data.startswith("pnl:testtoggle:"):
        admin_panel_test_toggle(chat_id, urldec(data[15:]))
    elif data.startswith("pnl:test:"):
        admin_panel_test_prompt(chat_id, urldec(data[9:]))
    elif data.startswith("pnlrolepick:"):
        admin_panel_rolepick(chat_id, urldec(data[12:]))
    elif data.startswith("pnlrole:"):
        parts = data.split(":", 2)
        admin_panel_role_set(chat_id, int(parts[1]), urldec(parts[2]))
    elif data.startswith("pnl:stats:"):
        admin_panel_stats(chat_id, urldec(data[10:]))
    elif data.startswith("pladd:"):
        admin_plan_add_prompt(chat_id, urldec(data[6:]))
    elif data.startswith("pled:"):
        parts = data.split(":", 3)
        admin_plan_edit_prompt(chat_id, int(parts[1]), parts[2], urldec(parts[3]))
    elif data.startswith("pltog:"):
        parts = data.split(":", 2)
        admin_plan_toggle(chat_id, int(parts[1]), urldec(parts[2]))
    elif data.startswith("pl:"):
        parts = data.split(":")
        admin_plan_view(chat_id, urldec(":".join(parts[1:-1])), int(parts[-1]))
    elif data.startswith("okdel:plan:"):
        parts = data.split(":", 3)
        admin_plan_delete(chat_id, int(parts[2]), urldec(parts[3]))
    elif data.startswith("pnledit:"):
        parts = data.split(":", 2)
        admin_panel_field_edit(chat_id, parts[1], urldec(parts[2]))
    elif data.startswith("askdel:pnl:"):
        admin_panel_delete_confirm(chat_id, urldec(data[11:]))
    elif data.startswith("okdel:pnl:"):
        admin_panel_delete_apply(chat_id, urldec(data[10:]))
    elif data.startswith("helpedit:"):
        admin_help_edit(chat_id, int(data[9:]))
    elif data.startswith("helpdel:"):
        admin_help_delete(chat_id, int(data[8:]))
    elif data.startswith("guideadm:"):
        admin_guide_home(chat_id)
    elif data.startswith("pw:"):
        admin_power_toggle(chat_id, data[3:])
    else:
        tg_send(chat_id, "دستور ناشناخته: " + esc(data))

def force_join_ok(u: dict) -> bool:
    frm = (u.get("message") or {}).get("from") or (u.get("callback_query") or {}).get("from") or {}
    uid = int(frm.get("id") or 0)
    if uid and is_admin(uid):
        return True
    chans = q_all("SELECT channel_id FROM channels ORDER BY id")
    if not chans:
        return True
    rows, missing = [], False
    for c in chans:
        cid = str(c["channel_id"])
        r = tg("getChatMember", {"chat_id": cid, "user_id": uid})
        if not r.get("ok"):
            continue
        if (r.get("result") or {}).get("status", "left") not in ("creator", "administrator", "member"):
            missing = True
            if cid.startswith("@"):
                rows.append([InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/" + cid[1:], style="success")])
            elif cid.startswith(("http://", "https://")):
                rows.append([InlineKeyboardButton("📢 عضویت در کانال", url=cid, style="success")])
    if not missing:
        return True
    rows.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="fj:check", style="success")])
    tg_send(uid, "⛔️ برای استفاده از ربات ابتدا در کانال‌های زیر عضو شو، بعد «🔄 بررسی عضویت» را بزن!", InlineKeyboardMarkup(rows))
    return False

def handle_message(m: dict) -> None:
    chat_id = int(m["chat"]["id"])
    if (m.get("chat") or {}).get("type") != "private":
        return
    text = str(m.get("text") or "").strip()
    frm = m.get("from") or {}
    upsert_user(chat_id, frm.get("username"))
    admin = is_admin(chat_id)
    _CTX["mid"] = None

    if not admin and q_val("SELECT is_banned FROM users WHERE tg_id=?", (chat_id,), 0):
        tg_send(chat_id, "🚫 دسترسی شما به ربات مسدود شده است.")
        return
    if not bot_enabled() and not admin:
        tg_send(chat_id, "🔴 ربات موقتاً غیرفعال است — بعداً مراجعه کنید.")
        return

    if text == "/start" or text.startswith("/start "):
        st_pop(chat_id)
        tg_send(chat_id, welcome_text(frm), main_menu_kb(admin))
        return
    if text == LBL["test"]:
        if not feat_on("test", True) and not admin:
            tg_send(chat_id, "🧪 تست فعلاً بسته است.")
            return
        handle_test_start(chat_id)
        return
    if text == LBL["buy"]:
        if not feat_on("buy", True) and not admin:
            tg_send(chat_id, "🛒 فروش فعلاً بسته است.")
            return
        show_buy_screen(chat_id)
        return
    if text == LBL["services"]:
        services_home(chat_id)
        return
    if text == LBL["wallet"]:
        wallet_screen(chat_id)
        return
    if text == LBL["guide"]:
        show_guide(chat_id)
        return
    if text == LBL["conditions"]:
        show_conditions(chat_id)
        return
    if text == LBL["support"]:
        start_support(chat_id)
        return
    if text == LBL["faq"]:
        tg_send(chat_id, str(get_setting("faq_text") or "❓ سوالات متداول فعلاً تنظیم نشده."), main_menu_kb(admin))
        return
    if text == LBL["admin"]:
        if admin:
            tg_send(chat_id, "👨‍💼 پنل مدیریت", admin_menu_kb())
        return

    if m.get("photo") and str(st_get(chat_id, "await", "")) == "wallet_receipt":
        handle_wallet_receipt_photo(chat_id, m)
        return
    handle_state_message(chat_id, text, m)

def handle_state_message(chat_id: int, text: str, m: dict) -> None:
    await_ = str(st_get(chat_id, "await", "") or "")
    if text == "/cancel":
        st_pop(chat_id)
        tg_send(chat_id, "↩️ لغو شد.", main_menu_kb(is_admin(chat_id)))
        return
    if not await_:
        return
    admin = is_admin(chat_id)

    if await_ == "support_msg":
        if text == "🏠 بازگشت به منوی اصلی":
            st_pop(chat_id)
            tg_send(chat_id, "🏠 بازگشتید!", main_menu_kb(admin))
            return
        if not text:
            tg_send(chat_id, "❌ فقط پیام متنی ارسال کنید!")
            return
        st_pop(chat_id)
        tid = int(ex("INSERT INTO tickets(tg_id,message,status) VALUES(?,?,?)", (chat_id, text, "open")).lastrowid)
        tg_send(chat_id, "🚀 پیام شما ارسال شد؛ منتظر پاسخ پشتیبانی باشید.", main_menu_kb(admin))
        notify_admins(f"🤙 تیکت پشتیبانی #{tid}\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n\n{esc(text[:800])}",
                      ikb([InlineKeyboardButton("✉️ پاسخ", callback_data=f"um:msg:{chat_id}"), InlineKeyboardButton("✅ بستن تیکت", callback_data=f"tkclose:{tid}")]))
        return
    if await_ == "topup_amount":
        mm = re.search(r"(\d{4,})", text.replace(",", ""))
        if not mm:
            tg_send(chat_id, "عدد معتبر بفرست (مثلاً 100000) یا «🏠 بازگشت به منوی اصلی» بزن!")
            return
        amount = int(mm.group(1))
        mn, mx = int(get_setting("min_charge", 0) or 0), int(get_setting("max_charge", 0) or 0)
        if mn and amount < mn:
            tg_send(chat_id, f"⬇️ حداقل شارژ {fmt_price(mn)} است.")
            return
        if mx and amount > mx:
            tg_send(chat_id, f"⬆️ حداکثر شارژ {fmt_price(mx)} است.")
            return
        st_set(chat_id, {"await": "wallet_card", "amount": amount})
        wallet_card_sent(chat_id)
        return
    if await_ in ("card_wait", "wallet_card"):
        return
    if await_ == "gift_redeem":
        handle_gift_redeem(chat_id, text)
        return
    if await_ == "wallet_receipt":
        handle_wallet_receipt_text(chat_id, text)
        return
    if await_ == "buy_custom_username":
        handle_buy_custom_username(chat_id, text)
        return
    if await_ == "agent_gb":
        handle_agent_gb(chat_id, text)
        return
    if await_ == "buy_discount_code":
        handle_buy_discount_code(chat_id, text)
        return
    if await_.startswith("svcnewpass:"):
        service_change_password_apply(chat_id, text)
        return

    if not admin:
        return
    if await_.startswith("payapi:"):
        admin_pay_api_apply(chat_id, text)
    elif await_.startswith("helpedit_body:"):
        admin_help_body_edit(chat_id, await_, text)
    elif await_.startswith("rcfix:"):
        receipt_fix_apply(chat_id, text)
    elif await_ == "finduser":
        admin_finduser_apply(chat_id, text)
    elif await_ == "search_order":
        admin_search_order_apply(chat_id, text)
    elif await_ == "addchan":
        admin_channel_add_apply(chat_id, text)
    elif await_ == "helpadd_title":
        admin_help_title_apply(chat_id, text)
    elif await_ == "helpadd_body":
        admin_help_body_apply(chat_id, text)
    elif await_ in ("massbal", "mass_sub"):
        admin_massbal_apply(chat_id, text)
    elif await_ in ("um:addbal", "um:subbal"):
        admin_um_bal_apply(chat_id, text)
    elif await_ == "um:msg":
        admin_um_msg_apply(chat_id, text)
    elif await_ == "dsc_code":
        admin_dsc_code_apply(chat_id, text)
    elif await_ == "dsc_value":
        admin_dsc_value_apply(chat_id, text)
    elif await_ == "gift_code":
        admin_gift_code_apply(chat_id, text)
    elif await_ == "gift_amount":
        admin_gift_amount_apply(chat_id, text)
    elif await_ == "pnltest":
        admin_panel_test_apply(chat_id, text)
    elif await_ == "pladd_gb":
        admin_plan_gb_apply(chat_id, text)
    elif await_ == "pladd_price":
        admin_plan_price_apply(chat_id, text)
    elif await_ == "pled:price":
        admin_plan_edit_apply(chat_id, "price", text)
    elif await_ == "pled:gb":
        admin_plan_edit_apply(chat_id, "gb", text)
    elif await_.startswith("pnledit_"):
        admin_panel_field_apply(chat_id, await_[8:], text)
    elif await_ == "bcast2_text":
        bcast_text_received(chat_id, text)
    elif await_.startswith("set:"):
        if admin_set_apply(chat_id, await_[4:], text):
            st_pop(chat_id)
            admin_settings_home(chat_id)
    elif await_.startswith("pnladd_"):
        admin_panel_add_step(chat_id, await_, text)

def handle_update(u: dict) -> None:
    if get_setting("force_join", False) and not force_join_ok(u):
        return
    if "message" in u:
        handle_message(u["message"])
        return
    if "callback_query" in u:
        cq = u["callback_query"]
        if str(cq.get("data") or "") == "fj:check":
            uid = int(cq["from"]["id"])
            mid = int((cq.get("message") or {}).get("message_id") or 0)
            if mid:
                tg("editMessageText", {"chat_id": uid, "message_id": mid, "text": "✅ عضویت تأیید شد! خوش آمدی 🎉"})
            st_pop(uid)
            tg_send(uid, welcome_text({"first_name": cq["from"].get("first_name", "")}), main_menu_kb(is_admin(uid)))
            return
        try:
            handle_callback(cq)
        finally:
            _CTX["mid"] = None

def run_cron() -> None:
    ex("DELETE FROM pending_buys WHERE created_at <= datetime('now','localtime','-24 hours')")

    expired = q_all("SELECT * FROM agent_panels WHERE is_test=1 AND status='active' AND expires_at IS NOT NULL"
                    " AND expires_at <= datetime('now','localtime')")
    panels = get_panels()
    for rec in expired:
        if any(pc.get("base_url") == rec.get("panel_name") for pc in panels.values()):
            p = panel_client(str(rec["panel_name"]), str(rec["panel_type"] or "pasarguard"))
            if p:
                res = panel_call(p, "delete_admin", {"username": str(rec["panel_username"])})
                if not res or not res.get("ok"):
                    err = (res or {}).get("description") or (res or {}).get("message") or "خطای اتصال یا پاسخ ناموفق پنل"
                    msg = (f"⚠️ <b>حذف خودکار پنل تست ناموفق است</b>\n\n"
                           f"یوزرنیم تست: <code>{esc(str(rec['panel_username']))}</code>\n"
                           f"آدرس پنل: {esc(str(rec['panel_name']))}\n"
                           f"خطا: {esc(str(err))}\n\n"
                           f"ربات هر چند دقیقه دوباره تلاش می‌کند. اگر ادامه داشت، ادمین تست و یوزرهایش را دستی پاک کنید.")
                    notify_admins(msg)
        ex("UPDATE agent_panels SET status='expired' WHERE id=?", (int(rec["id"]),))
        tg_send(int(rec["tg_id"]), f"⌛️ سرویس تست «{rec['panel_username']}» منقضی شد ({str(rec['expires_at'])[:10]}).\n"
                                   "برای ادامه می‌تونی سرویس اصلی رو از «🔐 خرید اشتراک» بگیری.")
        bot_log(f"test expired -> uid={rec['tg_id']} user={rec['panel_username']}")

    warn_pct = int(get_setting("quota_warn_pct", 80) or 80)
    warn_disc = int(get_setting("quota_warn_discount_pct", 10) or 10)
    warn_tpl = str(get_setting("quota_warn_text", "") or (
        "سلام {name} عزیز 👋\n\n⚠️ شما {pct}٪ از سرویس <code>{user}</code> رو مصرف کردی.\n"
        "🎁 یه کد تخفیف {disc}٪ اختصاصی برات ساختم — تا ۲۴ ساعت مهلت داری:\n"
        "برای افزایش حجم با تخفیف، کد تخفیف: <code>{code}</code>"))
    remove_tpl = str(get_setting("autoremove_text", "") or (
        "🗑 سهمیه پنل {user} تمام شد و پنل به‌صورت خودکار حذف شد.\nبرای ادامه، حجم اضافه خریداری کن."))
    warned = get_setting("quota_warned", {}) or {}
    if not isinstance(warned, dict):
        warned = {}

    for ap in q_all("SELECT id, tg_id, panel_username, panel_name, panel_type, quota_gb, status FROM agent_panels"
                    " WHERE status='active' AND is_test=0 LIMIT 300"):
        if warned.get(str(ap["id"])):
            continue
        p = panel_client(ap["panel_name"], ap["panel_type"] or None)
        if not p:
            continue
        res = panel_call(p, "get_admin_info", {"username": ap["panel_username"]})
        if not res or not res.get("ok") or not res.get("data"):
            continue
        u = res["data"]
        used = float(u.get("used_traffic") or 0)
        total = float(u.get("usage_limit") or u.get("data_limit") or 0)
        if total <= 0:
            continue
        pct = used / total * 100.0
        if warn_pct <= pct < 100:
            code = f"WARN{int(ap['tg_id']) % 100000}{secrets.token_hex(2).upper()}"
            ex("INSERT INTO discount_codes(code, kind, value, max_uses, used, active, expires_at)"
               " VALUES(?, 'percent', ?, 1, 0, 1, datetime('now','localtime','+24 hours'))", (code, warn_disc))
            urow = q_one("SELECT username FROM users WHERE tg_id=?", (int(ap["tg_id"]),)) or {}
            name = urow.get("username") or "کاربر"
            msg = (warn_tpl.replace("{name}", name).replace("{user}", str(ap["panel_username"]))
                   .replace("{pct}", str(int(pct))).replace("{disc}", str(warn_disc)).replace("{code}", code))
            tg_send(int(ap["tg_id"]), msg, ikb([InlineKeyboardButton("➕ خرید حجم اضافه", callback_data=f"apgb:{ap['id']}", style="success")]))
            warned[str(ap["id"])] = 1
            set_setting("quota_warned", warned)
            bot_log(f"quota warn uid={ap['tg_id']} pct={int(pct)} code={code}")
        elif pct >= 100:
            tg_send(int(ap["tg_id"]), remove_tpl.replace("{user}", str(ap["panel_username"])))
            ex("UPDATE agent_panels SET status='exhausted' WHERE id=?", (int(ap["id"]),))
            # سرویس‌های اصلی نباید پاک شوند تا قابلیت تمدید داشته باشند
            # فقط وضعیت غیرفعال در پنل ست می‌شود (اگر پنل پشتیبانی کند)
            panel_call(p, "modify_admin_status", {"username": ap["panel_username"], "status": "disabled"})
            bot_log(f"panel exhausted (disabled only) uid={ap['tg_id']} user={ap['panel_username']}")

def main() -> None:
    if not BOT_TOKEN:
        print("BOT_TOKEN خالیه؛ بالای فایل پرش کن", file=sys.stderr)
        sys.exit(1)
    db_init()
    for _k, _v in (("support_id", SUPPORT_ID), ("card_number", CARD_NUMBER), ("card_owner", CARD_OWNER)):
        if _v:
            set_setting(_k, _v)
    admin_ids()
    tg("deleteWebhook", {"drop_pending_updates": False})
    bot_log("=== WireNest python bot started (long polling) ===")
    offset, last_cron, ticks = 0, 0.0, 0
    while True:
        ticks += 1
        if time.time() - last_cron >= 60:
            last_cron = time.time()
            try:
                run_cron()
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"cron error: {e}\n{tb}")
                notify_admins(f"⚠️ <b>خطای سیستم پس‌زمینه (Cron)</b>\n\n❗️ <code>{esc(str(e))}\n{esc(tb[-400:])}</code>")
        try:
            updates = _run(
                bot_obj().get_updates(
                    offset=offset,
                    timeout=25,
                    allowed_updates=["message", "callback_query"],
                    read_timeout=40,
                    write_timeout=40,
                    connect_timeout=40,
                    pool_timeout=40,
                ),
                70,
            )
        except Exception as e:
            bot_log(f"getUpdates error: {e}")
            time.sleep(3)
            continue
        for upd in updates:
            offset = upd.update_id + 1
            u = upd.to_dict()
            try:
                handle_update(u)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"update error: {e}\n{tb}")
                utype = "message" if "message" in u else ("callback_query" if "callback_query" in u else "unknown")
                uid = 0
                if utype == "message":
                    uid = int(((u.get("message") or {}).get("from") or {}).get("id") or 0)
                elif utype == "callback_query":
                    uid = int(((u.get("callback_query") or {}).get("from") or {}).get("id") or 0)
                err_msg = (
                    f"⚠️ <b>خطای ربات</b>\n"
                    f"🔧 نوع: {utype}\n"
                    f"👤 کاربر: {uid}\n"
                    f"❗️ <code>{esc(str(e))}\n{esc(tb[-500:])}</code>"
                )
                notify_admins(err_msg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass