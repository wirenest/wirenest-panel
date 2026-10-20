from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
from telegram import InlineKeyboardButton
from pesarguard.database import add_balance, ex, get_balance, q_all, q_one, spend_balance
from pesarguard.handlers.user.services import complete_extra_gb
from pesarguard.handlers.user.wallet import receipt_review_kb
from pesarguard.keyboards import ikb
from pesarguard.state import st_all, st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit, tg_send
from pesarguard.utils import esc, fmt_price, num


def admin_receipts_queue(chat_id: int) -> None:
    recs = q_all("SELECT id, tg_id, amount, ref_text FROM receipts WHERE status='pending' ORDER BY id")
    if not recs:
        send_or_edit(chat_id, "🧾 در انتظار تاییدی نیست.")
        return
    for r in recs:
        tg_send(chat_id, f"#{r['id']} از {r['tg_id']} — {fmt_price(r['amount'])}\n<code>{esc(r['ref_text'])}</code>",
                receipt_review_kb(r["id"]))

def handle_receipt_review(chat_id: int, data: str) -> None:
    rid = int(data.split(":")[1])
    approve = data.startswith("rcok")
    rec = q_one("SELECT * FROM receipts WHERE id=?", (rid,))
    if not rec or rec["status"] != "pending":
        send_or_edit(chat_id, "قبلا پردازش شده.")
        return
    cur = ex("UPDATE receipts SET status=? WHERE id=? AND status='pending'", ("approved" if approve else "rejected", rid))
    if cur.rowcount == 0:
        send_or_edit(chat_id, "قبلا پردازش شده.")
        return
    uid = int(rec["tg_id"])
    if not approve:
        tg_send(uid, "❌ رسید شما رد شد. برای بررسی با پشتیبانی در تماس باش.")
        send_or_edit(chat_id, f"❌ رسید #{rid} رد شد.")
        return
    add_balance(uid, int(rec["amount"]))
    send_or_edit(chat_id, f"✅ رسید #{rid} تایید شد و {fmt_price(rec['amount'])} به کیف پول کاربر اضافه شد.")
    tg_send(uid, f"✅ پرداخت {fmt_price(rec['amount'])} تایید و به موجودی‌ات اضافه شد.")
    xst = st_all(uid)
    if xst.get("xp_kind") == "extragb" and xst.get("xp_gb"):
        st_pop(uid)
        xprice = int(xst.get("xp_price") or 0)
        if xprice > 0 and not spend_balance(uid, xprice):
            tg_send(uid, "⚠️ موجودی برای تکمیل خرید حجم اضافه کافی نشد — مبلغ در کیف پولت باقی ماند. دوباره تلاش کن.")
            return
        complete_extra_gb(uid, int(xst["xp_gb"]), int(xst.get("pid") or 0), int(xst.get("xp") or 0), xprice)
        return
    if str(rec["ref_text"] or "").startswith("topup"):
        b = q_one("SELECT * FROM pending_buys WHERE tg_id=? ORDER BY id DESC LIMIT 1", (uid,))
        if b and b["pid"]:
            prow = q_one("SELECT * FROM panel_plans WHERE id=?", (int(b["pid"]),))
            if prow and get_balance(uid) >= float(prow["price"]):
                st_set(uid, {"buy_plan": {"pid": int(prow["id"]), "gb": float(prow["volume_gb"]),
                                          "price": int(prow["price"]), "orig_price": int(prow["price"])}})
                tg_send(uid, "✅ موجودی کافی شد. برای پرداخت و ساخت آنی پنل بزن!",
                        ikb([InlineKeyboardButton(f"✅ پرداخت از موجودی کیف پول ({num(prow['price'])} تومان)", callback_data=f"paybalplan:{prow['id']}", style="success")]))

def receipt_fix_start(chat_id: int, rid: int) -> None:
    st_set(chat_id, {"await": f"rcfix:{rid}"})
    send_or_edit(chat_id, "✏️ مبلغ صحیح رسید را به تومان بفرست (تایید با این مبلغ انجام می‌شود)!")

def receipt_fix_apply(chat_id: int, text: str) -> None:
    rid = int(str(st_get(chat_id, "await", ""))[6:] or 0)
    st_pop(chat_id)
    clean = int(re.sub(r"[^\d]", "", text.replace(",", "")) or 0)
    if not clean:
        send_or_edit(chat_id, "❌ فقط عدد بفرست!")
        st_set(chat_id, {"await": f"rcfix:{rid}"})
        return
    ex("UPDATE receipts SET amount=? WHERE id=?", (clean, rid))
    handle_receipt_review(chat_id, f"rcok:{rid}")
