from telegram import Bot
from telegram.constants import ParseMode
from modules.config import BOT_TOKEN
from modules.database import bot_log

_BOT_OBJ = None

def bot_obj() -> Bot:
    global _BOT_OBJ
    if _BOT_OBJ is None:
        _BOT_OBJ = Bot(BOT_TOKEN)
    return _BOT_OBJ

async def send_msg_async(chat_id: int, text: str, kb=None):
    bot = bot_obj()
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True
        )
    except Exception as e:
        bot_log(f"Send msg async error ({chat_id}): {e}")
        return None

async def edit_msg_async(chat_id: int, msg_id: int, text: str, kb=None):
    bot = bot_obj()
    try:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
            disable_web_page_preview=True
        )
    except Exception as e:
        bot_log(f"Edit msg async error ({chat_id}/{msg_id}): {e}")
        return None
