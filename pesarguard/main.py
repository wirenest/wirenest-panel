from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import sys
import time
from pesarguard.bootstrap import bot_log
from pesarguard.config import BOT_TOKEN, CARD_NUMBER, CARD_OWNER, SUPPORT_ID
from pesarguard.cron import run_cron
from pesarguard.database import admin_ids, db_init, set_setting
from pesarguard.dispatcher import handle_update
from pesarguard.telegram_api import _run, bot_obj, notify_admins, tg
from pesarguard.utils import esc


def main() -> None:
    if not BOT_TOKEN:
        print("BOT_TOKEN خالیه؛ بالای فایل پرش کن", file=sys.stderr)
        sys.exit(1)
    db_init()
    for _k, _v in (("support_id", SUPPORT_ID), ("card_number", CARD_NUMBER), ("card_owner", CARD_OWNER)):
        if _v:
            set_setting(_k, _v)
    admin_ids()
    tg("deleteWebhook", {"drop_pending_updates": False})
    bot_log("=== WireNest python bot started (long polling) ===")
    offset, last_cron, ticks = 0, 0.0, 0
    while True:
        ticks += 1
        if time.time() - last_cron >= 60:
            last_cron = time.time()
            try:
                run_cron()
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"cron error: {e}\n{tb}")
                notify_admins(f"⚠️ <b>خطای سیستم پس‌زمینه (Cron)</b>\n\n❗️ <code>{esc(str(e))}\n{esc(tb[-400:])}</code>")
        try:
            updates = _run(
                bot_obj().get_updates(
                    offset=offset,
                    timeout=25,
                    allowed_updates=["message", "callback_query"],
                    read_timeout=40,
                    write_timeout=40,
                    connect_timeout=40,
                    pool_timeout=40,
                ),
                70,
            )
        except Exception as e:
            bot_log(f"getUpdates error: {e}")
            time.sleep(3)
            continue
        for upd in updates:
            offset = upd.update_id + 1
            u = upd.to_dict()
            try:
                handle_update(u)
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                bot_log(f"update error: {e}\n{tb}")
                utype = "message" if "message" in u else ("callback_query" if "callback_query" in u else "unknown")
                uid = 0
                if utype == "message":
                    uid = int(((u.get("message") or {}).get("from") or {}).get("id") or 0)
                elif utype == "callback_query":
                    uid = int(((u.get("callback_query") or {}).get("from") or {}).get("id") or 0)
                err_msg = (
                    f"⚠️ <b>خطای ربات</b>\n"
                    f"🔧 نوع: {utype}\n"
                    f"👤 کاربر: {uid}\n"
                    f"❗️ <code>{esc(str(e))}\n{esc(tb[-500:])}</code>"
                )
                notify_admins(err_msg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
