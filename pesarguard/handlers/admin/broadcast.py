from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import time
from telegram import InlineKeyboardButton
from pesarguard.constants import AUD_LABELS
from pesarguard.database import q_all
from pesarguard.keyboards import ikb
from pesarguard.state import st_all, st_pop, st_set
from pesarguard.telegram_api import send_or_edit, tg, tg_send


def bcast_home(chat_id: int) -> None:
    send_or_edit(chat_id, "📣 <b>پیام همگانی</b>\nبه کدام گروه ارسال شود؟", ikb(
        [InlineKeyboardButton("👥 همه کاربران", callback_data="bcast2:all", style="primary"), InlineKeyboardButton("🛒 خریدارها", callback_data="bcast2:buyers")],
        [InlineKeyboardButton("🚫 خرید نداشته‌ها", callback_data="bcast2:nonbuyers", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data="adm:users")]))

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
