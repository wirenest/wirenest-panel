from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import time
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton
from pesarguard.database import get_panels, q_all
from pesarguard.keyboards import ikb
from pesarguard.telegram_api import send_or_edit
from pesarguard.utils import num


def build_full_stats() -> str:
    users = q_all("SELECT COALESCE(balance,0) b FROM users")
    total_users = len(users)
    total_bal = sum(int(u["b"]) for u in users)
    buys = q_all("SELECT tg_id, price, status, tariff_id, panel_username, created_at FROM purchases")
    recs = q_all("SELECT amount, status, ref_text FROM receipts WHERE status='approved'")
    total_sales = len(buys)
    active_sales = sum(1 for b in buys if b.get("status") == "active")
    sum_sales = sum(int(b.get("price") or 0) for b in buys)
    sum_active = sum(int(b.get("price") or 0) for b in buys if b.get("status") == "active")
    buyers = len({int(b["tg_id"]) for b in buys})
    conv = (buyers / total_users * 100) if total_users else 0.0
    avg_buy = (sum_sales / total_sales) if total_sales else 0
    since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    m_sales = sum(int(b.get("price") or 0) for b in buys if str(b.get("created_at") or "") >= since)
    per_user: dict = {}
    for b in buys:
        k = f"{b['tg_id']}:{b['tariff_id']}"
        per_user[k] = per_user.get(k, 0) + 1
    renews = sum(v - 1 for v in per_user.values() if v > 1)
    renew_pct = (renews / total_sales * 100) if total_sales else 0.0
    gw_stat: dict = {}
    for r in recs:
        ref = str(r.get("ref_text") or "")
        gw = "wallet" if ref.startswith("topup") else "buy" if ref.startswith("buy:") else "other"
        gw_stat.setdefault(gw, {"n": 0, "sum": 0})
        gw_stat[gw]["n"] += 1
        gw_stat[gw]["sum"] += int(r.get("amount") or 0)
    labels = {"card": "💳 کارت به کارت", "wallet": "🏦 شارژ کیف پول", "buy": "🛒 خرید مستقیم", "other": "📄 سایر"}
    L = [
        "📊 آمار کلی ربات", "━━━━━━━━━━━━━━━━━━",
        f"👥 تعداد کل کاربران: {total_users} نفر",
        f"💳 کاربران دارای خرید: {buyers} نفر",
        f"💰 موجودی کل کاربران: {num(total_bal)} تومان", "",
        f"🧾 تعداد کل فروش: {total_sales} عدد",
        f"🧾 تعداد کل فروش سرویس های فعال: {active_sales} عدد",
        f"💵 جمع کل فروش : {num(sum_sales)} تومان",
        f"💵 جمع کل فروش سرویس های فعال: {num(sum_active)} تومان",
        f"📈 نرخ تبدیل به مشتری: {conv:,.2f}٪",
        f"💳 میانگین خرید هر مشتری: {avg_buy:,.0f} تومان",
        f"📅 درآمد پیش‌بینی‌شده ماهانه: {num(m_sales)} تومان",
        f"📊 درصد تمدید از فروش: {renew_pct:,.2f}٪", "",
        f"🧩 تعداد پنل‌ها: {len(get_panels())} عدد",
    ]
    if gw_stat:
        L.append("")
        for g, s in gw_stat.items():
            L.append(f"\n📌 نام درگاه : {labels.get(g, g)}\n - تعداد پرداخت موفق : {s['n']}\n - جمع پرداختی ها : {num(s['sum'])}")
    return "\n".join(L)

def admin_stats(chat_id: int) -> None:
    t0 = time.time()
    try:
        txt = build_full_stats()
    except Exception as e:
        txt = "⚠️ خطا در آمار: " + str(e)[:150]
    txt += f"\n📡 پینگ ربات: {int((time.time() - t0) * 1000)} میلی‌ثانیه"
    send_or_edit(chat_id, txt, ikb([InlineKeyboardButton("◀️ بازگشت به پنل مدیریت", callback_data="adm:back")]))
