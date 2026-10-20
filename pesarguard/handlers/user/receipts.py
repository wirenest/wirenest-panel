from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from pesarguard.database import q_all
from pesarguard.telegram_api import send_or_edit
from pesarguard.utils import fmt_price, jdate


def my_receipts(chat_id: int) -> None:
    rows = q_all("SELECT id, amount, status, created_at FROM receipts WHERE tg_id=? ORDER BY id DESC LIMIT 10", (chat_id,))
    if not rows:
        send_or_edit(chat_id, "هنوز رسیدی ثبت نکردی.")
        return
    smap = {"pending": "⏳ در انتظار", "approved": "✅ تایید شده", "rejected": "❌ رد شده", "deleted": "🗑 حذف"}
    txt = "📄 آخرین رسیدها:\n\n"
    for r in rows:
        txt += f"#{r['id']} — {fmt_price(r['amount'])} — {smap.get(r['status'], r['status'])} — {jdate(r['created_at'])}\n"
    send_or_edit(chat_id, txt)
