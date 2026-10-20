from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import ex, q_all, q_one
from pesarguard.telegram_api import send_or_edit


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
