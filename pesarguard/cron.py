from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import secrets
from telegram import InlineKeyboardButton
from pesarguard.bootstrap import bot_log
from pesarguard.database import ex, get_panels, get_setting, q_all, q_one, set_setting
from pesarguard.keyboards import ikb
from pesarguard.panel_api import panel_call, panel_client
from pesarguard.telegram_api import notify_admins, tg_send
from pesarguard.utils import esc


def run_cron() -> None:
    ex("DELETE FROM pending_buys WHERE created_at <= datetime('now','localtime','-24 hours')")

    expired = q_all("SELECT * FROM agent_panels WHERE is_test=1 AND status='active' AND expires_at IS NOT NULL"
                    " AND expires_at <= datetime('now','localtime')")
    panels = get_panels()
    for rec in expired:
        if any(pc.get("base_url") == rec.get("panel_name") for pc in panels.values()):
            p = panel_client(str(rec["panel_name"]), str(rec["panel_type"] or "pasarguard"))
            if p:
                res = panel_call(p, "delete_admin", {"username": str(rec["panel_username"])})
                if not res or not res.get("ok"):
                    err = (res or {}).get("description") or (res or {}).get("message") or "خطای اتصال یا پاسخ ناموفق پنل"
                    msg = (f"⚠️ <b>حذف خودکار پنل تست ناموفق است</b>\n\n"
                           f"یوزرنیم تست: <code>{esc(str(rec['panel_username']))}</code>\n"
                           f"آدرس پنل: {esc(str(rec['panel_name']))}\n"
                           f"خطا: {esc(str(err))}\n\n"
                           f"ربات هر چند دقیقه دوباره تلاش می‌کند. اگر ادامه داشت، ادمین تست و یوزرهایش را دستی پاک کنید.")
                    notify_admins(msg)
        ex("UPDATE agent_panels SET status='expired' WHERE id=?", (int(rec["id"]),))
        tg_send(int(rec["tg_id"]), f"⌛️ سرویس تست «{rec['panel_username']}» منقضی شد ({str(rec['expires_at'])[:10]}).\n"
                                   "برای ادامه می‌تونی سرویس اصلی رو از «🔐 خرید اشتراک» بگیری.")
        bot_log(f"test expired -> uid={rec['tg_id']} user={rec['panel_username']}")

    warn_pct = int(get_setting("quota_warn_pct", 80) or 80)
    warn_disc = int(get_setting("quota_warn_discount_pct", 10) or 10)
    warn_tpl = str(get_setting("quota_warn_text", "") or (
        "سلام {name} عزیز 👋\n\n⚠️ شما {pct}٪ از سرویس <code>{user}</code> رو مصرف کردی.\n"
        "🎁 یه کد تخفیف {disc}٪ اختصاصی برات ساختم — تا ۲۴ ساعت مهلت داری:\n"
        "برای افزایش حجم با تخفیف، کد تخفیف: <code>{code}</code>"))
    remove_tpl = str(get_setting("autoremove_text", "") or (
        "🗑 سهمیه پنل {user} تمام شد و پنل به‌صورت خودکار حذف شد.\nبرای ادامه، حجم اضافه خریداری کن."))
    warned = get_setting("quota_warned", {}) or {}
    if not isinstance(warned, dict):
        warned = {}

    for ap in q_all("SELECT id, tg_id, panel_username, panel_name, panel_type, quota_gb, status FROM agent_panels"
                    " WHERE status='active' AND is_test=0 LIMIT 300"):
        if warned.get(str(ap["id"])):
            continue
        p = panel_client(ap["panel_name"], ap["panel_type"] or None)
        if not p:
            continue
        res = panel_call(p, "get_admin_info", {"username": ap["panel_username"]})
        if not res or not res.get("ok") or not res.get("data"):
            continue
        u = res["data"]
        used = float(u.get("used_traffic") or 0)
        total = float(u.get("usage_limit") or u.get("data_limit") or 0)
        if total <= 0:
            continue
        pct = used / total * 100.0
        if warn_pct <= pct < 100:
            code = f"WARN{int(ap['tg_id']) % 100000}{secrets.token_hex(2).upper()}"
            ex("INSERT INTO discount_codes(code, kind, value, max_uses, used, active, expires_at)"
               " VALUES(?, 'percent', ?, 1, 0, 1, datetime('now','localtime','+24 hours'))", (code, warn_disc))
            urow = q_one("SELECT username FROM users WHERE tg_id=?", (int(ap["tg_id"]),)) or {}
            name = urow.get("username") or "کاربر"
            msg = (warn_tpl.replace("{name}", name).replace("{user}", str(ap["panel_username"]))
                   .replace("{pct}", str(int(pct))).replace("{disc}", str(warn_disc)).replace("{code}", code))
            tg_send(int(ap["tg_id"]), msg, ikb([InlineKeyboardButton("➕ خرید حجم اضافه", callback_data=f"apgb:{ap['id']}", style="success")]))
            warned[str(ap["id"])] = 1
            set_setting("quota_warned", warned)
            bot_log(f"quota warn uid={ap['tg_id']} pct={int(pct)} code={code}")
        elif pct >= 100:
            tg_send(int(ap["tg_id"]), remove_tpl.replace("{user}", str(ap["panel_username"])))
            ex("UPDATE agent_panels SET status='exhausted' WHERE id=?", (int(ap["id"]),))
            # سرویس‌های اصلی نباید پاک شوند تا قابلیت تمدید داشته باشند
            # فقط وضعیت غیرفعال در پنل ست می‌شود (اگر پنل پشتیبانی کند)
            panel_call(p, "modify_admin_status", {"username": ap["panel_username"], "status": "disabled"})
            bot_log(f"panel exhausted (disabled only) uid={ap['tg_id']} user={ap['panel_username']}")
