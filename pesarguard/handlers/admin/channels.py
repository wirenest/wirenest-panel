from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import urllib.parse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import ex, q_all
from pesarguard.state import st_pop, st_set
from pesarguard.telegram_api import send_or_edit


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
