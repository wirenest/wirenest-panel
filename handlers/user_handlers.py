from telegram import Update
from telegram.ext import ContextTypes
from modules.config import log_event
from modules.utils import esc, num, fmt_price, fmt_gb
from modules.database import (
    q_one, q_all, ex, is_admin, get_setting,
    st_get, st_set, st_pop, st_all
)
from modules.keyboards import (
    main_menu_kb, wallet_kb, support_kb, cancel_kb, ikb
)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    log_event("user_handler", f"Command /start received from user {user.id} (@{user.username})")
    
    # Save user
    ex("INSERT OR REPLACE INTO users (tg_id, username) VALUES (?, ?)", (user.id, user.username))
    
    admin = is_admin(user.id)
    kb = main_menu_kb(admin=admin)
    
    welc = get_setting("welcome_text", "سلام کاربر عزیز! به ربات فروش خوش آمدید.")
    await update.message.reply_text(f"سلام {esc(user.first_name)} عزیز!\n\n{welc}", reply_markup=kb, parse_mode="HTML")

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_event("user_handler", f"Showing wallet for user {user.id}")
    u = q_one("SELECT balance FROM users WHERE tg_id = ?", (user.id,))
    bal = u["balance"] if u else 0
    
    txt = f"💰 <b>کیف پول شما</b>\n\nموجودی فعلی: <b>{fmt_price(bal)}</b>"
    kb = wallet_kb()
    
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_event("user_handler", f"Showing services for user {user.id}")
    services = q_all("SELECT * FROM services WHERE tg_id = ? AND status = 'active'", (user.id,))
    
    if not services:
        txt = "🌐 <b>سرویس‌های من</b>\n\nشما در حال حاضر هیچ سرویس فعالی ندارید."
        kb = ikb([("🛒 خرید سرویس جدید", "show_buy")])
    else:
        txt = f"🌐 <b>سرویس‌های فعال شما ({len(services)} عدد):</b>\n\n"
        rows = []
        for s in services:
            txt += f"🔹 <b>{esc(s['plan_title'])}</b> | {fmt_gb(s['volume_gb'])}\n"
            rows.append([(f"🔑 {s['plan_title']}", f"svc_view_{s['id']}")])
        rows.append([("🛒 خرید سرویس جدید", "show_buy")])
        kb = ikb(*rows)
        
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_event("user_handler", f"Showing support for user {user.id}")
    txt = "🎧 <b>پشتیبانی</b>\n\nجهت ارسال پیام برای تیم پشتیبانی، روی دکمه زیر کلیک کنید."
    kb = support_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
