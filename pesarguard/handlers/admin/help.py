from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import ex, q_all, q_one
from pesarguard.keyboards import cancel_kb
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit
from pesarguard.utils import esc


def admin_guide_home(chat_id: int) -> None:
    kb = []
    for t in q_all("SELECT * FROM guide_topics ORDER BY id"):
        kb.append([InlineKeyboardButton(f"✏️ {t['title']}", callback_data=f"helpedit:{t['id']}"), InlineKeyboardButton(f"🗑 {t['title']}", callback_data=f"helpdel:{t['id']}")])
    kb.append([InlineKeyboardButton("➕ افزودن راهنما", callback_data="helpadd", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "📚 مدیریت راهنما:\n✏️ = ویرایش متن | 🗑 = حذف", InlineKeyboardMarkup(kb))

def admin_help_add(chat_id: int) -> None:
    st_set(chat_id, {"await": "helpadd_title"})
    send_or_edit(chat_id, "📚 عنوان آموزش را بفرست!")

def admin_help_edit(chat_id: int, tid: int) -> None:
    t = q_one("SELECT * FROM guide_topics WHERE id=?", (tid,))
    if not t:
        send_or_edit(chat_id, "آموزش یافت نشد.")
        return
    st_set(chat_id, {"await": f"helpedit_body:{tid}"})
    send_or_edit(chat_id, f"✏️ ویرایش آموزش «{esc(t['title'])}»\n\n📄 متن فعلی:\n{esc(str(t['content'])[:2500])}\n\n✍️ متن جدید را بفرست!", cancel_kb())

def admin_help_delete(chat_id: int, tid: int) -> None:
    ex("DELETE FROM guide_topics WHERE id=?", (tid,))
    admin_guide_home(chat_id)

def admin_help_title_apply(chat_id: int, text: str) -> None:
    st_set(chat_id, {"await": "helpadd_body", "htitle": text.strip()})
    send_or_edit(chat_id, "📚 توضیحات آموزش را بفرست (متن/لینک/فیلم)!")

def admin_help_body_apply(chat_id: int, text: str) -> None:
    title = str(st_get(chat_id, "htitle", "آموزش"))
    st_pop(chat_id)
    ex("INSERT INTO guide_topics(title, content) VALUES(?,?)", (title, text))
    send_or_edit(chat_id, f"✅ آموزش «{esc(title)}» اضافه شد.")

def admin_help_body_edit(chat_id: int, await_: str, text: str) -> None:
    tid = int(await_[len("helpedit_body:"):])
    st_pop(chat_id)
    ex("UPDATE guide_topics SET content=? WHERE id=?", (text, tid))
    t = q_one("SELECT title FROM guide_topics WHERE id=?", (tid,))
    send_or_edit(chat_id, f"✅ آموزش «{esc((t or {}).get('title', '?'))}» به‌روزرسانی شد.")
