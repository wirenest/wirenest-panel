from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.constants import CODE_RE
from pesarguard.database import add_balance, ex, q_all, q_one
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit, tg_send
from pesarguard.utils import esc, fmt_price


def start_gift_redeem(chat_id: int) -> None:
    st_set(chat_id, {"await": "gift_redeem"})
    send_or_edit(chat_id, "🎁 کد هدیه را بفرست (یا /cancel برای انصراف)!")

def handle_gift_redeem(chat_id: int, text: str) -> None:
    code = text.strip().upper()
    row = q_one("SELECT * FROM gift_codes WHERE UPPER(code)=? AND active=1", (code,))
    if not row:
        tg_send(chat_id, "❌ کد هدیه نامعتبر یا غیرفعال است. دوباره بفرست یا /cancel!")
        st_pop(chat_id)
        return
    
    # 1. Atomic check for duplicate usage by the same user via UNIQUE constraint (gift_id, tg_id)
    try:
        ex("INSERT INTO gift_redemptions(gift_id, tg_id) VALUES(?,?)", (row["id"], chat_id))
    except sqlite3.IntegrityError:
        tg_send(chat_id, "❌ شما قبلاً از این کد هدیه استفاده کرده‌اید.")
        st_pop(chat_id)
        return

    # 2. Atomic check for max_uses limit to prevent concurrent spam overload
    cur = ex("UPDATE gift_codes SET used = used + 1 WHERE id=? AND (max_uses=0 OR used < max_uses)", (row["id"],))
    if cur.rowcount == 0:
        # Revert the redemption entry if max uses was reached
        ex("DELETE FROM gift_redemptions WHERE gift_id=? AND tg_id=?", (row["id"], chat_id))
        tg_send(chat_id, "❌ ظرفیت استفاده از این کد هدیه به پایان رسیده است.")
        st_pop(chat_id)
        return

    add_balance(chat_id, int(row["amount"]))
    st_pop(chat_id)
    tg_send(chat_id, f"🎉 تبریک! کد هدیه «{esc(code)}» اعمال شد.\n{fmt_price(row['amount'])} به کیف پولت اضافه شد.")

def admin_discounts_home(chat_id: int) -> None:
    rows = []
    for c in q_all("SELECT * FROM discount_codes ORDER BY id DESC"):
        kind = "٪" if c["kind"] == "percent" else "ت"
        rows.append([InlineKeyboardButton(f"🗑 {c['code']} ({c['value']}{kind} — {c['used']}/{c['max_uses'] or '∞'})", callback_data=f"okdel:discount:{c['id']}", style="danger")])
    rows.append([InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="dsc:add", style="success")])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🏷️ <b>کدهای تخفیف</b>\n🗑 = حذف", InlineKeyboardMarkup(rows))

def admin_gifts_home(chat_id: int) -> None:
    rows = []
    for c in q_all("SELECT * FROM gift_codes ORDER BY id DESC"):
        rows.append([InlineKeyboardButton(f"🗑 {c['code']} ({fmt_price(c['amount'])} — {c['used']}/{c['max_uses'] or '∞'})", callback_data=f"okdel:gift:{c['id']}", style="danger")])
    rows.append([InlineKeyboardButton("➕ افزودن کد هدیه", callback_data="gift:add", style="success")])
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🎁 <b>کدهای هدیه</b>\n🗑 = حذف", InlineKeyboardMarkup(rows))

def admin_code_add_start(chat_id: int, typ: str) -> None:
    st_set(chat_id, {"await": "dsc_code" if typ == "dsc" else "gift_code"})
    send_or_edit(chat_id, "🏷 کد تخفیف (لاتین، بدون فاصله)!" if typ == "dsc" else "🎁 کد هدیه (لاتین، بدون فاصله)!")

def admin_code_delete(chat_id: int, data: str) -> None:
    parts = data.split(":")
    if parts[1] == "discount":
        ex("DELETE FROM discount_codes WHERE id=?", (int(parts[2]),))
        send_or_edit(chat_id, "کد تخفیف حذف شد.")
    else:
        ex("DELETE FROM gift_codes WHERE id=?", (int(parts[2]),))
        send_or_edit(chat_id, "کد هدیه حذف شد.")

def admin_dsc_code_apply(chat_id: int, text: str) -> None:
    code = text.strip().replace(" ", "")
    if not CODE_RE.match(code):
        send_or_edit(chat_id, "کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر!")
        return
    st_set(chat_id, {"await": "dsc_value", "dcode": code})
    send_or_edit(chat_id, "💰 مقدار تخفیف را بفرست:\nدرصد: مثلا 20\nمبلغ ثابت تومان: مثلا 50000\n(برای تعیین نوع، پسوند بزن: 20% یا 50000t)!")

def admin_dsc_value_apply(chat_id: int, text: str) -> None:
    v = text.strip()
    if m := re.match(r"^(\d+)\s*%$", v):
        kind, val = "percent", int(m.group(1))
    elif m := re.match(r"^(\d+)\s*t$", v, re.I):
        kind, val = "fixed", int(m.group(1))
    elif re.match(r"^\d+$", v):
        kind, val = "fixed", int(v)
    else:
        send_or_edit(chat_id, "فرمت: 20% یا 50000t یا 50000.")
        return
    code = str(st_get(chat_id, "dcode", ""))
    st_pop(chat_id)
    ex("INSERT OR REPLACE INTO discount_codes(code, kind, value, used) VALUES(?,?,?,0)", (code, kind, val))
    send_or_edit(chat_id, f"✅ کد تخفیف «{code}» ساخته شد ({val}{'%' if kind == 'percent' else ' تومان'}).")

def admin_gift_code_apply(chat_id: int, text: str) -> None:
    code = text.strip().replace(" ", "")
    if not CODE_RE.match(code):
        send_or_edit(chat_id, "کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر!")
        return
    st_set(chat_id, {"await": "gift_amount", "gcode": code})
    send_or_edit(chat_id, "💰 مبلغ هدیه (تومان) را بفرست!")

def admin_gift_amount_apply(chat_id: int, text: str) -> None:
    m = re.search(r"\d+", text.replace(",", ""))
    if not m:
        send_or_edit(chat_id, "عدد بفرست!")
        return
    code = str(st_get(chat_id, "gcode", ""))
    st_pop(chat_id)
    ex("INSERT OR REPLACE INTO gift_codes(code, amount, used) VALUES(?,?,0)", (code, int(m.group(0))))
    send_or_edit(chat_id, f"✅ کد هدیه «{code}» ساخته شد.")
