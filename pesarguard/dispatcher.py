from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
import urllib.parse
from telegram import InlineKeyboardButton
from pesarguard.constants import LBL
from pesarguard.database import bot_enabled, ex, get_setting, is_admin, q_one, q_val, set_setting, upsert_user
from pesarguard.handlers.admin.appearance import admin_appearance_home, admin_appearance_setcol, admin_appearance_toggle_emoji
from pesarguard.handlers.admin.broadcast import bcast_audience_pick, bcast_btn_pick, bcast_home, bcast_run, bcast_text_received
from pesarguard.handlers.admin.channels import admin_channel_add_apply, admin_channel_add_start, admin_channel_delete, admin_channels_home
from pesarguard.handlers.admin.discounts_gifts import admin_code_add_start, admin_code_delete, admin_discounts_home, admin_dsc_code_apply, admin_dsc_value_apply, admin_gift_amount_apply, admin_gift_code_apply, admin_gifts_home, handle_gift_redeem, start_gift_redeem
from pesarguard.handlers.admin.help import admin_guide_home, admin_help_add, admin_help_body_apply, admin_help_body_edit, admin_help_delete, admin_help_edit, admin_help_title_apply
from pesarguard.handlers.admin.panels import admin_panel_add_start, admin_panel_add_step, admin_panel_delete_apply, admin_panel_delete_confirm, admin_panel_edit_start, admin_panel_field_apply, admin_panel_field_edit, admin_panel_ping, admin_panel_role_set, admin_panel_rolepick, admin_panel_stats, admin_panel_test_apply, admin_panel_test_prompt, admin_panel_test_toggle, admin_panel_toggle, admin_panel_view, admin_panels_home
from pesarguard.handlers.admin.payments import admin_pay_api_apply, admin_pay_api_start, admin_pay_cfg, admin_pay_toggle, admin_payments_home
from pesarguard.handlers.admin.plans import admin_plan_add_prompt, admin_plan_delete, admin_plan_edit_apply, admin_plan_edit_prompt, admin_plan_gb_apply, admin_plan_price_apply, admin_plan_toggle, admin_plan_view
from pesarguard.handlers.admin.receipts import admin_receipts_queue, handle_receipt_review, receipt_fix_apply, receipt_fix_start
from pesarguard.handlers.admin.settings_features import admin_feature_toggle, admin_features_home, admin_general_home, admin_power_home, admin_power_toggle, admin_set_apply, admin_set_cancel, admin_set_prompt, admin_settings_home, admin_shopgeneral_home
from pesarguard.handlers.admin.stats import admin_stats
from pesarguard.handlers.admin.tickets import admin_ticket_close, admin_tickets
from pesarguard.handlers.admin.users import admin_findorder_start, admin_finduser_apply, admin_finduser_start, admin_massbal_apply, admin_massbal_start, admin_search_order_apply, admin_svc_fulldel, admin_svc_orderdel, admin_svc_refund, admin_svc_view, admin_um_bal_apply, admin_um_msg_apply, admin_umrepl, admin_user_action, admin_users_home
from pesarguard.handlers.user.buy import handle_buy_callback, handle_buy_custom_username, handle_buy_discount_code, show_buy_screen
from pesarguard.handlers.user.info import force_join_ok, show_conditions, show_guide, start_support, welcome_text
from pesarguard.handlers.user.receipts import my_receipts
from pesarguard.handlers.user.services import extra_gb_invoice_cancel, extra_gb_invoice_confirm, handle_agent_gb, service_change_password_apply, service_change_password_start, service_extra_gb_start, service_login_info, service_screen, service_toggle, services_home
from pesarguard.handlers.user.test import handle_test_pick, handle_test_start
from pesarguard.handlers.user.wallet import handle_wallet_receipt_photo, handle_wallet_receipt_text, start_topup, wallet_add_credit, wallet_card_sent, wallet_screen
from pesarguard.keyboards import admin_menu_kb, feat_on, ikb, main_menu_kb
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import _CTX, notify_admins, send_or_edit, tg, tg_send
from pesarguard.utils import esc, fmt_price, urldec


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
            if force_join_ok(u):
                if mid:
                    tg("editMessageText", {"chat_id": uid, "message_id": mid, "text": "✅ عضویت تأیید شد! خوش آمدی 🎉"})
                st_pop(uid)
                tg_send(uid, welcome_text({"first_name": cq["from"].get("first_name", "")}), main_menu_kb(is_admin(uid)))
            else:
                tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "⚠️ هنوز عضو کانال نشدی! لطفاً ابتدا عضو شو.", "show_alert": True})
                if mid:
                    try:
                        tg("deleteMessage", {"chat_id": uid, "message_id": mid})
                    except Exception:
                        pass
            return
        try:
            handle_callback(cq)
        finally:
            _CTX["mid"] = None
