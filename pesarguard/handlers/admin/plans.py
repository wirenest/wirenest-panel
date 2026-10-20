from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton
from pesarguard.database import ex, q_one
from pesarguard.handlers.admin.panels import admin_panel_view
from pesarguard.keyboards import cancel_kb, ikb
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit
from pesarguard.utils import _is_num, g2, num


def admin_plan_add_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pladd_gb", "plan_panel": name})
    send_or_edit(chat_id, "➕ حجم پلن را بفرست (گیگ): مثلا 100!", cancel_kb())

def admin_plan_gb_apply(chat_id: int, text: str) -> None:
    gb = text.strip()
    if not _is_num(gb) or float(gb) <= 0:
        send_or_edit(chat_id, "❌ عدد گیگ نامعتبر. دوباره بفرست (مثلا 100)!")
        return
    st_set(chat_id, {"await": "pladd_price", "plan_gb": float(gb)})
    send_or_edit(chat_id, "💰 قیمت این پلن را بفرست (تومان): مثلا 300000!")

def admin_plan_price_apply(chat_id: int, text: str) -> None:
    price = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(price) or int(float(price)) <= 0:
        send_or_edit(chat_id, "❌ قیمت نامعتبر. دوباره بفرست (تومان)!")
        return
    name, gb = str(st_get(chat_id, "plan_panel", "")), float(st_get(chat_id, "plan_gb", 0))
    st_pop(chat_id)
    ex("INSERT INTO panel_plans(panel_name, volume_gb, price, active) VALUES(?,?,?,1)", (name, gb, int(float(price))))
    send_or_edit(chat_id, f"✅ پلن افزوده شد: {g2(gb)} گیگ — {num(float(price))} ت.")
    admin_panel_view(chat_id, name)

def admin_plan_view(chat_id: int, name: str, pid: int) -> None:
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    if not pl:
        send_or_edit(chat_id, "پلن یافت نشد.")
        return
    send_or_edit(chat_id, f"📦 پلن {g2(pl['volume_gb'])} گیگ\n💰 قیمت: {num(pl['price'])} تومان\n" + ("🟢 فعال" if pl["active"] else "🔴 غیرفعال"),
                 ikb([InlineKeyboardButton("✏️ ویرایش قیمت", callback_data=f"pled:{pid}:price:{name}"), InlineKeyboardButton("✏️ ویرایش حجم", callback_data=f"pled:{pid}:gb:{name}")],
                     [InlineKeyboardButton("🔴 غیرفعال کن" if pl["active"] else "🟢 فعال کن", callback_data=f"pltog:{pid}:{name}")],
                     [InlineKeyboardButton("🗑 حذف پلن", callback_data=f"okdel:plan:{pid}:{name}", style="danger")], [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_plan_edit_prompt(chat_id: int, pid: int, field: str, name: str) -> None:
    st_set(chat_id, {"await": f"pled:{field}", "pled_pid": pid, "pled_panel": name})
    pl = q_one("SELECT * FROM panel_plans WHERE id=?", (pid,))
    cur = (f"{num(pl['price'])} تومان" if field == "price" else f"{g2(pl['volume_gb'])} گیگ") if pl else "—"
    send_or_edit(chat_id, f"✏️ مقدار فعلی: {cur}\n\nمقدار جدید {'قیمت (تومان)' if field == 'price' else 'حجم (گیگ)'} را بفرست!", cancel_kb())

def admin_plan_edit_apply(chat_id: int, field: str, text: str) -> None:
    pid, name = int(st_get(chat_id, "pled_pid", 0) or 0), str(st_get(chat_id, "pled_panel", ""))
    v = text.strip().replace(",", "").replace(" ", "")
    if not _is_num(v) or float(v) <= 0:
        send_or_edit(chat_id, "❌ مقدار نامعتبر. دوباره بفرست!")
        return
    if field == "price":
        ex("UPDATE panel_plans SET price=? WHERE id=?", (int(float(v)), pid))
    else:
        ex("UPDATE panel_plans SET volume_gb=? WHERE id=?", (float(v), pid))
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ پلن ویرایش شد.")
    admin_plan_view(chat_id, name, pid)

def admin_plan_toggle(chat_id: int, pid: int, name: str) -> None:
    ex("UPDATE panel_plans SET active = 1 - active WHERE id=?", (pid,))
    admin_plan_view(chat_id, name, pid)

def admin_plan_delete(chat_id: int, pid: int, name: str) -> None:
    ex("DELETE FROM panel_plans WHERE id=?", (pid,))
    send_or_edit(chat_id, "🗑 پلن حذف شد.")
    admin_panel_view(chat_id, name)
