from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import asyncio
import html
import re
import threading
import time
from datetime import timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from pesarguard.bootstrap import bot_log
from pesarguard.config import BOT_TOKEN
from pesarguard.database import admin_ids, get_setting, set_setting


_LOOP = asyncio.new_event_loop()

threading.Thread(target=_LOOP.run_forever, daemon=True).start()

_BOT_OBJ: Bot | None = None

def _run(coro, timeout: float = 60):
    return asyncio.run_coroutine_threadsafe(coro, _LOOP).result(timeout)

def bot_obj() -> Bot:
    global _BOT_OBJ
    if _BOT_OBJ is None:
        _BOT_OBJ = Bot(BOT_TOKEN)
        _run(_BOT_OBJ.initialize())
    return _BOT_OBJ

async def _tg_call(method: str, d: dict):
    b = bot_obj()
    if method == "sendMessage":
        extra = {k: v for k, v in d.items() if k not in ("chat_id", "text", "reply_markup", "parse_mode")}
        m = await b.send_message(
            chat_id=d["chat_id"],
            text=d["text"],
            parse_mode=ParseMode.HTML,
            reply_markup=d.get("reply_markup"),
            **extra,
        )
        return {"message_id": m.message_id}
    if method == "editMessageText":
        await b.edit_message_text(
            text=d["text"],
            chat_id=d["chat_id"],
            message_id=d["message_id"],
            parse_mode=ParseMode.HTML,
            reply_markup=d.get("reply_markup"),
        )
        return {}
    if method == "editMessageReplyMarkup":
        await b.edit_message_reply_markup(
            chat_id=d["chat_id"], message_id=d["message_id"], reply_markup=d.get("reply_markup")
        )
        return {}
    if method == "copyMessage":
        m = await b.copy_message(chat_id=d["chat_id"], from_chat_id=d["from_chat_id"], message_id=d["message_id"])
        return {"message_id": m.message_id}
    if method == "pinChatMessage":
        await b.pin_chat_message(
            chat_id=d["chat_id"],
            message_id=d["message_id"],
            disable_notification=bool(d.get("disable_notification", True)),
        )
        return {}
    if method == "answerCallbackQuery":
        await b.answer_callback_query(
            callback_query_id=d["callback_query_id"],
            text=d.get("text"),
            show_alert=bool(d.get("show_alert", False)),
        )
        return {}
    if method == "getChat":
        chat = await b.get_chat(chat_id=d["chat_id"])
        return {"username": chat.username, "invite_link": chat.invite_link}
    if method == "getChatMember":
        cm = await b.get_chat_member(chat_id=d["chat_id"], user_id=d["user_id"])
        return {"status": cm.status}
    if method == "getMe":
        me = await b.get_me()
        return {"username": me.username}
    if method == "deleteWebhook":
        await b.delete_webhook(drop_pending_updates=bool(d.get("drop_pending_updates", False)))
        return {}
    raise ValueError("unsupported method: " + method)

def _plain_html(text: str) -> str:
    return html.escape(html.unescape(re.sub(r"<[^>]+>", "", str(text))), quote=False)

def tg(method: str, data: dict | None = None, timeout: int = 35) -> dict:
    data = dict(data or {})
    fallback_used = False
    for _ in range(4):
        try:
            return {"ok": True, "result": _run(_tg_call(method, data), timeout + 25)}
        except RetryAfter as e:
            ra = e.retry_after
            time.sleep((ra.total_seconds() if isinstance(ra, timedelta) else float(ra)) + 1)
        except TelegramError as e:
            desc = str(e)
            if "parse entities" in desc.lower() and "text" in data and not fallback_used:
                fallback_used = True
                data["text"] = _plain_html(data["text"])
                bot_log(f"HTML parse fallback in {method}: {desc}")
                continue
            return {"ok": False, "description": desc}
        except Exception as e:
            bot_log(f"TG error {method}: {e}")
            return {"ok": False}
    return {"ok": False}

def theme_kb(kb: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    bc = get_setting("btn_color", "colorful")
    if bc == "none":
        return kb
    new_rows = []
    for row in kb.inline_keyboard:
        new_row = []
        for btn in row:
            text = btn.text
            if any(text.startswith(e) for e in ["🔵", "🟢", "🔴", "🟡", "🟠", "🟣"]):
                new_row.append(btn)
                continue

            prefix = ""
            style = None
            if bc == "blue":
                style = "primary"
            elif bc == "green":
                style = "success"
            elif bc == "red":
                style = "danger"
            elif bc == "colorful":
                cbd = btn.callback_data or ""
                t = text.lower()
                if any(x in cbd for x in ["buy", "confirm", "pay", "ok", "add", "submit", "apcreds", "apgb"]) or any(x in t for x in ["تایید", "خرید", "شارژ", "افزودن", "ثبت", "پرداخت"]):
                    style = "success"
                elif any(x in cbd for x in ["cancel", "del", "remove", "no", "reject", "close", "off"]) or any(x in t for x in ["حذف", "لغو", "انصراف", "رد", "بستن", "خاموش"]):
                    style = "danger"
                elif any(x in cbd for x in ["back", "home", "return"]) or any(x in t for x in ["بازگشت", "منوی"]):
                    style = "primary"
                else:
                    style = "primary"

            kwargs = {
                "text": text,
                "style": style
            }
            for attr in ["callback_data", "url", "login_url", "web_app", "switch_inline_query", 
                         "switch_inline_query_current_chat", "switch_inline_query_chosen_chat", 
                         "callback_game", "pay", "copy_text", "icon_custom_emoji_id"]:
                val = getattr(btn, attr, None)
                if val is not None:
                    kwargs[attr] = val
            
            btn = InlineKeyboardButton(**kwargs)
            # فقط در صورتی که پلتفرم بله باشد یا متد ارسالی فیلد استایل را بپذیرد
            # چون روی تلگرام خطای 400 می‌دهد، اینجا برای تلگرام حذفش می‌کنیم
            # if style: btn.style = style 
            new_row.append(btn)
        new_rows.append(new_row)
    return InlineKeyboardMarkup(new_rows)

def theme_reply_kb(kb: ReplyKeyboardMarkup) -> ReplyKeyboardMarkup:
    bc = get_setting("btn_color", "colorful")
    if bc == "none":
        return kb
    new_rows = []
    for row in kb.keyboard:
        new_row = []
        for btn in row:
            text = btn.text
            style = "primary"
            if bc == "blue":
                style = "primary"
            elif bc == "green":
                style = "success"
            elif bc == "red":
                style = "danger"
            elif bc == "colorful":
                t = text.lower()
                if any(x in t for x in ["خرید", "شارژ", "موجودی", "تایید", "افزودن"]):
                    style = "success"
                elif any(x in t for x in ["لغو", "خروج", "بستن"]):
                    style = "danger"
                elif any(x in t for x in ["مدیریت", "پشتیبانی", "راهنما", "سوالات"]):
                    style = "primary"
                else:
                    style = "primary"

            kwargs = {
                "text": text,
                "style": style
            }
            for attr in ["request_users", "request_chat", "request_contact", "request_location", "request_poll", "web_app"]:
                val = getattr(btn, attr, None)
                if val is not None:
                    kwargs[attr] = val
            new_row.append(KeyboardButton(**kwargs))
        new_rows.append(new_row)

    return ReplyKeyboardMarkup(
        new_rows,
        resize_keyboard=getattr(kb, "resize_keyboard", True),
        one_time_keyboard=getattr(kb, "one_time_keyboard", False),
        selective=getattr(kb, "selective", False),
        input_field_placeholder=getattr(kb, "input_field_placeholder", None)
    )

def tg_send(chat, text: str, kb=None, extra: dict | None = None) -> dict:
    if isinstance(kb, InlineKeyboardMarkup):
        kb = theme_kb(kb)
    elif isinstance(kb, ReplyKeyboardMarkup):
        kb = theme_reply_kb(kb)
    data = {"chat_id": chat, "text": text, "parse_mode": "HTML"}
    if kb:
        data["reply_markup"] = kb
    if extra:
        data.update(extra)
    return tg("sendMessage", data)

def edit_menu(chat_id: int, msg_id: int, text: str, kb=None) -> None:
    if isinstance(kb, InlineKeyboardMarkup):
        kb = theme_kb(kb)
    if msg_id:
        params = {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"}
        if kb:
            params["reply_markup"] = kb
        r = tg("editMessageText", params)
        if r.get("ok"):
            return
        if "message is not modified" in str(r.get("description", "")).lower():
            return
        if kb:
            r2 = tg("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": msg_id, "reply_markup": kb})
            if r2.get("ok") or "message is not modified" in str(r2.get("description", "")).lower():
                return
        r3 = tg("editMessageText", params)
        if not r3.get("ok"):
            tg("editMessageText", {"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"})
        return
    tg_send(chat_id, text, kb)

_CTX = {"mid": None}

def send_or_edit(chat_id: int, text: str, kb=None) -> None:
    mid = _CTX["mid"]
    if kb and isinstance(kb, ReplyKeyboardMarkup):
        tg_send(chat_id, text, kb)
    elif mid:
        edit_menu(chat_id, mid, text, kb)
    else:
        tg_send(chat_id, text, kb)

def notify_admins(text: str, kb=None) -> None:
    first = True
    for aid in admin_ids():
        if not first:
            time.sleep(0.3)
        tg_send(aid, text, kb)
        first = False

_BOT_USERNAME = {"v": ""}

def bot_username() -> str:
    cached = str(get_setting("bot_username", "") or "")
    if cached:
        return cached
    me = tg("getMe")
    un = str((me.get("result") or {}).get("username", ""))
    if un:
        set_setting("bot_username", un)
    return un
