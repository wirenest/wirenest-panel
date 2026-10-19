from telegram import Update
from telegram.ext import ContextTypes
from modules.utils import esc, num, fmt_price
from modules.database import q_one, q_all, is_admin
from modules.keyboards import admin_menu_kb, back_adm_kb

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
        
    txt = "⚙️ <b>مدیریت ربات</b>\n\nبه پنل مدیریت خوش آمدید. بخش مورد نظر خود را انتخاب کنید:"
    kb = admin_menu_kb()
    
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        return
        
    u_count = q_one("SELECT COUNT(*) as c FROM users")["c"]
    s_count = q_one("SELECT COUNT(*) as c FROM services WHERE status = 'active'")["c"]
    r_count = q_one("SELECT COUNT(*) as c FROM receipts WHERE status = 'pending'")["c"]
    
    txt = f"📊 <b>آمار کل ربات</b>\n\n" \
          f"👥 تعداد کاربران: <b>{num(u_count)}</b>\n" \
          f"🌐 سرویس‌های فعال: <b>{num(s_count)}</b>\n" \
          f"💳 رسیدهای منتظر تایید: <b>{num(r_count)}</b>"
          
    kb = back_adm_kb()
    if update.callback_query:
        await update.callback_query.edit_message_text(txt, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=kb, parse_mode="HTML")
