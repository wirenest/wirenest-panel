from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.database import get_setting, is_admin, q_all
from pesarguard.keyboards import main_menu_kb, support_kb
from pesarguard.state import st_set
from pesarguard.telegram_api import send_or_edit, tg, tg_send
from pesarguard.utils import esc


def welcome_text(frm: dict) -> str:
    s = str(get_setting("start_text", "") or "")
    greet = s if s else "سلام {name} 👋\nبه ربات فروش سرویس خوش اومدی!"
    return greet.replace("{name}", esc(frm.get("first_name", ""))).replace("{username}", "@" + str(frm.get("username", "")))

def show_guide(chat_id: int) -> None:
    intro = get_setting("guide_intro") or "📌 راهنمای اتصال — سیستم‌عامل خود را انتخاب کنید!"
    rows = [[InlineKeyboardButton(str(t["title"]), callback_data=f"guide:{t['id']}")] for t in q_all("SELECT id, title FROM guide_topics ORDER BY id")]
    rows.append([InlineKeyboardButton("🏠 منوی اصلی", callback_data="m:home")])
    send_or_edit(chat_id, str(intro), InlineKeyboardMarkup(rows))

def show_conditions(chat_id: int) -> None:
    c = get_setting("conditions_text") or (
        "📋 <b>شرایط و توضیحات ربات</b>\n\n"
        "✅ پنل ادمین محدود روی سرور قدرتمند تحویل می‌گیرید\n"
        "♾️ <b>بدون محدودیت زمان</b> — پنل تا تمام شدن حجم معتبر است\n"
        "📦 سهمیه مشخص در هر پلن که بین مشتریان خود تقسیم می‌کنید\n"
        "🛠 پنل مدیریت کامل: ساخت و مدیریت سرویس‌ها برای مشتریانتان\n"
        "➕ امکان خرید حجم اضافه هر زمان\n"
        "⚡ تحویل آنی بعد از تایید پرداخت\n"
        "☎️ پشتیبانی پاسخ‌گو\n\n"
        "❗ مسئولیت استفاده از پنل با خریدار است؛ فروش غیرمجاز ممنوع."
    )
    tg_send(chat_id, str(c), main_menu_kb(is_admin(chat_id)))

def start_support(chat_id: int) -> None:
    sup = str(get_setting("support_id", "") or "")
    txt = "☎️ پشتیبانی"
    if sup:
        txt += "\nآیدی پشتیبانی: @" + sup.lstrip("@")
    txt += "\n\nبرای ارسال تیکت، روی دکمه زیر بزن و پیامت را بنویس!"
    tg_send(chat_id, txt, support_kb())
    st_set(chat_id, {"await": "support_msg"})

def force_join_ok(u: dict) -> bool:
    frm = (u.get("message") or {}).get("from") or (u.get("callback_query") or {}).get("from") or {}
    uid = int(frm.get("id") or 0)
    # Admin bypass removed for testing per user request if he wants to see it working
    # if uid and is_admin(uid):
    #     return True
    chans = q_all("SELECT channel_id FROM channels ORDER BY id")
    if not chans:
        return True
    rows, missing = [], False
    for c in chans:
        cid = str(c["channel_id"])
        r = tg("getChatMember", {"chat_id": cid, "user_id": uid})
        if not r.get("ok"):
            # If bot is not admin or channel is private/hidden, log it and ignore
            continue
        if (r.get("result") or {}).get("status", "left") not in ("creator", "administrator", "member"):
            missing = True
            link = None
            if cid.startswith("@"):
                link = "https://t.me/" + cid[1:]
            elif cid.startswith(("http://", "https://")):
                link = cid
            else:
                # Numeric ID or username without @
                gc = tg("getChat", {"chat_id": cid})
                if gc.get("ok"):
                    res = gc.get("result") or {}
                    link = res.get("invite_link") or (f"https://t.me/{res['username']}" if res.get("username") else None)
            
            if link:
                rows.append([InlineKeyboardButton("📢 عضویت در کانال", url=link, style="success")])
            else:
                rows.append([InlineKeyboardButton("📢 عضویت در کانال (لینک یافت نشد)", url="https://t.me/telegram", style="danger")])
    
    if not missing:
        return True
    rows.append([InlineKeyboardButton("🔄 بررسی عضویت", callback_data="fj:check", style="success")])
    tg_send(uid, "⛔️ برای استفاده از ربات ابتدا در کانال‌های زیر عضو شو، بعد «🔄 بررسی عضویت» را بزن!", InlineKeyboardMarkup(rows))
    return False
