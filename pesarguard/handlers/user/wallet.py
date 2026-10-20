from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import admin_ids, create_receipt, get_balance, get_setting, is_admin, q_val, receipt_ref_exists
from pesarguard.keyboards import ikb, main_menu_kb, wallet_kb
from pesarguard.state import st_all, st_get, st_pop, st_set
from pesarguard.telegram_api import notify_admins, send_or_edit, tg
from pesarguard.utils import esc, fmt_price


def wallet_screen(chat_id: int) -> None:
    send_or_edit(chat_id, f"🏦 <b>کیف پول شما</b>\n\n💵 موجودی: <b>{fmt_price(get_balance(chat_id))}</b>", wallet_kb())

def start_topup(chat_id: int) -> None:
    st_set(chat_id, {"await": "topup_amount"})
    send_or_edit(chat_id, "💰 مبلغ شارژ را به تومان بفرست (مثلاً: 100000)\n\nیا «🏠 بازگشت به منوی اصلی» بزن!")

def wallet_add_credit(chat_id: int) -> None:
    st = st_all(chat_id)
    price = 0
    bp = st.get("buy_plan")
    if isinstance(bp, dict):
        price = int(bp.get("orig_price") or bp.get("price") or 0)
    elif st.get("xp_kind") == "extragb":
        price = int(st.get("xp_price") or 0)
    elif st.get("back_tariff"):
        price = int(q_val("SELECT price FROM tariffs WHERE id=?", (int(st["back_tariff"]),), 0) or 0)
    if price:
        deficit = max(price - get_balance(chat_id), 0) or price
        st_set(chat_id, {"await": "card_wait", "amount": deficit, "buy_plan": bp, "back_tariff": st.get("back_tariff")})
        wallet_card_sent(chat_id)
        return
    start_topup(chat_id)

def wallet_card_sent(chat_id: int) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    gw = str(st_get(chat_id, "gw", "card"))
    gw_label = {"tron": "💵 ترون", "zarinpal": "🟡 زرین پال", "aqayepardakht": "🔵 آقای پرداخت"}.get(gw)
    if gw_label:
        body = (
            f"برای پرداخت {fmt_price(amount)} از طریق {gw_label}:\n\n"
            f"💼 آدرس ولت:\n<code>{esc(get_setting('wallet_address', '—'))}</code>\n\n"
            "پس از واریز، دکمه «✉️ ارسال کردم (ارسال رسید)» را بزن و هش تراکنش/عکس رسید را بفرست!"
        )
    else:
        card = get_setting("card_number", "—")
        owner = get_setting("card_owner", "—")
        body = (
            f"💳 کارت به کارت:\n\n💳 شماره کارت (کپی کن):\n<code>{esc(card)}</code>\n"
            f"👤 به نام: {esc(owner)}\n\n"
            f"💰 مبلغ واریزی: <b>{fmt_price(amount)}</b>\n\n"
            "مبلغ را دقیقاً همان عدد واریز کن. پس از واریز، دکمه زیر را بزن!"
        )
    st_set(chat_id, {"await": "card_wait", "amount": amount,
                     "buy_plan": st_get(chat_id, "buy_plan"), "back_tariff": st_get(chat_id, "back_tariff")})
    send_or_edit(chat_id, body, ikb([InlineKeyboardButton("✉️ ارسال کردم (ارسال رسید)", callback_data="wal:receipt", style="success")]))

def _keep_xp_and_clear(chat_id: int) -> None:
    keep = {}
    if str(st_get(chat_id, "xp_kind", "")) == "extragb":
        keep = {"xp_kind": "extragb", "xp_gb": st_get(chat_id, "xp_gb"), "xp_price": st_get(chat_id, "xp_price"),
                "xp": st_get(chat_id, "xp"), "pid": st_get(chat_id, "pid"), "await": "idle"}
    st_pop(chat_id)
    if keep:
        st_set(chat_id, keep)

def receipt_review_kb(rid: int) -> InlineKeyboardMarkup:
    return ikb([InlineKeyboardButton("⚡ تایید با همان مبلغ", callback_data=f"rcok:{rid}", style="success"), InlineKeyboardButton("✏️ ویرایش مبلغ و تایید", callback_data=f"rcfix:{rid}", style="success")],
               [InlineKeyboardButton("❌ رد درخواست", callback_data=f"rcno:{rid}")])

def handle_wallet_receipt_text(chat_id: int, text: str) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    if not amount:
        st_pop(chat_id)
        st_set(chat_id, {"await": "topup_amount"})
        send_or_edit(chat_id, "❌ مبلغ شارژ مشخص نیست. اول مبلغ را بفرست (مثلاً: 100000)!")
        return
    _keep_xp_and_clear(chat_id)
    ref = text.strip()
    if len(ref) >= 20 and receipt_ref_exists(ref):
        send_or_edit(chat_id, "⛔️ این TXID قبلاً ثبت شده است — هر تراکنش فقط یک‌بار قابل استفاده است.")
        return
    rid = create_receipt(chat_id, amount, "topup | " + text[:200])
    send_or_edit(chat_id, "✅ رسید شارژ ثبت شد و در انتظار تایید ادمین است.", main_menu_kb(is_admin(chat_id)))
    notify_admins(
        f"💳 رسید شارژ کیف پول #{rid}\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\n"
        f"مبلغ: {fmt_price(amount)}\nکد/پیگیری: <code>{esc(text[:200])}</code>",
        receipt_review_kb(rid),
    )

def handle_wallet_receipt_photo(chat_id: int, m: dict) -> None:
    amount = int(st_get(chat_id, "amount", 0) or 0)
    if not amount:
        st_pop(chat_id)
        st_set(chat_id, {"await": "topup_amount"})
        send_or_edit(chat_id, "❌ مبلغ شارژ مشخص نیست. اول مبلغ را بفرست (مثلاً: 100000)!")
        return
    _keep_xp_and_clear(chat_id)
    fid = (m.get("photo") or [{}])[-1].get("file_unique_id", "photo")
    rid = create_receipt(chat_id, amount, f"topup | photo:{fid}")
    send_or_edit(chat_id, "✅ رسید شارژ ثبت شد و در انتظار تایید ادمین است.", main_menu_kb(is_admin(chat_id)))
    for aid in admin_ids():
        tg("copyMessage", {"chat_id": aid, "from_chat_id": chat_id, "message_id": m["message_id"]})
    notify_admins(
        f"💳 رسید شارژ کیف پول #{rid} (عکس)\nاز: <a href='tg://user?id={chat_id}'>{chat_id}</a>\nمبلغ: {fmt_price(amount)}",
        receipt_review_kb(rid),
    )
