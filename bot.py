import sys
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from modules.config import BOT_TOKEN
from modules.database import db_init, bot_log
from handlers.user_handlers import cmd_start, show_wallet, show_services, show_support
from handlers.admin_handlers import cmd_admin, admin_stats

def main():
    bot_log("Initializing database...")
    db_init()
    
    bot_log("Building application...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Command Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    
    # Message Handlers
    app.add_handler(MessageHandler(filters.Regex("^💰 کیف پول$"), show_wallet))
    app.add_handler(MessageHandler(filters.Regex("^🌐 سرویس‌های من$"), show_services))
    app.add_handler(MessageHandler(filters.Regex("^🎧 پشتیبانی$"), show_support))
    app.add_handler(MessageHandler(filters.Regex("^⚙️ پنل مدیریت$"), cmd_admin))
    
    # Callback Handlers
    app.add_handler(CallbackQueryHandler(cmd_admin, pattern="^adm_home$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(show_wallet, pattern="^topup_card$"))
    app.add_handler(CallbackQueryHandler(show_services, pattern="^show_buy$"))
    
    bot_log("=== Modular PasarGuard Bot Started ===")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
