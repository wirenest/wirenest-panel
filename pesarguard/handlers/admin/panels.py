from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pesarguard.crypto import panel_decrypt_pw, panel_encrypt_pw
from pesarguard.database import ex, get_panels, get_setting, q_all, q_one, set_setting
from pesarguard.keyboards import admin_menu_kb, cancel_kb, ikb
from pesarguard.panel_api import _panel_auth, _preq, get_panel_role_label, panel_call, panel_clean_base_url, panel_ping
from pesarguard.state import st_get, st_pop, st_set
from pesarguard.telegram_api import send_or_edit, tg_send
from pesarguard.utils import _is_num, esc, g2, num, valid_panel_name


def admin_panels_home(chat_id: int) -> None:
    kb = [[InlineKeyboardButton(f"🌐 {n}", callback_data="pnl:view:" + n), InlineKeyboardButton("🔍 تست", callback_data="pnl:ping:" + n)] for n in get_panels()]
    kb.append([InlineKeyboardButton("➕ افزودن پنل", callback_data="pnl:add", style="success")])
    kb.append([InlineKeyboardButton("◀️ بازگشت", callback_data="adm:back")])
    send_or_edit(chat_id, "🌐 پنل‌های متصل:", InlineKeyboardMarkup(kb))

def admin_panel_view(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    active = d.get("active", name == str(get_setting("selected_panel", "") or ""))
    plans = q_all("SELECT * FROM panel_plans WHERE panel_name=? ORDER BY volume_gb", (name,))
    kb = []
    for pl in plans:
        mark = "" if pl["active"] else "❌ "
        kb.append([InlineKeyboardButton(f"{mark}{g2(pl['volume_gb'])} گیگ — {num(pl['price'])} ت", callback_data=f"pl:{name}:{pl['id']}")])
    kb.append([InlineKeyboardButton("➕ افزودن پلن حجمی +", callback_data=f"pladd:{name}", style="success")])
    xprice, xmin = int(d.get("extra_gb_price") or 0), int(d.get("extra_gb_min") or 0)
    role_lbl = get_panel_role_label(d, int(d.get("role_id") or 3))
    kb.append([InlineKeyboardButton(f"🛡 نقش مدیران: {role_lbl}", callback_data=f"pnlrolepick:{name}")])
    kb.append([InlineKeyboardButton("💰 قیمت حجم: " + (f"{num(xprice)} ت" if xprice else "— تنظیم نشده"), callback_data=f"pnledit:extra_price:{name}"),
               InlineKeyboardButton("⚖️ حداقل حجم: " + (f"{xmin} گیگ" if xmin else "— تنظیم نشده"), callback_data=f"pnledit:extra_min:{name}")])
    kb.append([InlineKeyboardButton("📊 آمار پنل", callback_data=f"pnl:stats:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش نام پنل", callback_data=f"pnledit:name:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش آدرس پنل", callback_data=f"pnledit:url:{name}")])
    kb.append([InlineKeyboardButton("✏️ ویرایش یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("✏️ ویرایش پسورد ادمین", callback_data=f"pnledit:pass:{name}")])
    kb.append([InlineKeyboardButton("🧪 سرویس تست: ✅ روشن" if d.get("is_test_panel") else "🧪 سرویس تست: ⛔️ خاموش", callback_data=f"pnl:testtoggle:{name}"),
               InlineKeyboardButton("⚙️ حجم/مدت تست", callback_data=f"pnl:test:{name}")])
    kb.append([InlineKeyboardButton("🔴 غیرفعال کن" if active else "🟢 فعال کن", callback_data=f"pnl:toggle:{name}")])
    kb.append([InlineKeyboardButton("🗑 حذف این پنل", callback_data=f"askdel:pnl:{name}", style="danger")])
    kb.append([InlineKeyboardButton("◀️ پنل‌ها", callback_data="adm:panels")])
    send_or_edit(chat_id, f"🛠 مدیریت پنل «{esc(name)}» ({d.get('ptype', 'pasarguard')})\n"
                          f"{'🟢 فعال (قابل خرید)' if active else '🔴 غیرفعال'}\n🔗 {esc(d.get('base_url'))}\n\n📦 پلن‌های حجمی این پنل:",
                 InlineKeyboardMarkup(kb))

def admin_panel_ping(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    tg_send(chat_id, f"🔍 در حال تست {esc(name)} ...")
    r = panel_ping(d)
    send_or_edit(chat_id, f"🟢 وصله — {esc(name)}" if r.get("ok") else f"🔴 قطعه — {esc(name)}")

def admin_panel_add_start(chat_id: int) -> None:
    st_set(chat_id, {"await": "pnladd_name"})
    send_or_edit(chat_id, "🏷 اسم پنل رو بفرست (همین اسم به کاربر نشون داده می‌شه، مثلاً: سرور1)!")

def admin_panel_delete_confirm(chat_id: int, name: str) -> None:
    send_or_edit(chat_id, f"⚠️ «{esc(name)}» برای همیشه حذف بشه؟ این عملیات غیرقابل‌بازگشته!",
                 ikb([InlineKeyboardButton("🔥 بله، حذف کن", callback_data="okdel:pnl:" + name, style="danger")], [InlineKeyboardButton("🚫 نه", callback_data="adm:panels")]))

def admin_panel_delete_apply(chat_id: int, name: str) -> None:
    st_pop(chat_id)
    panels = get_panels()
    panels.pop(name, None)
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🗑 پنل «{esc(name)}» حذف شد.", admin_menu_kb())

def admin_panel_add_step(chat_id: int, await_: str, text: str) -> None:
    if await_ == "pnladd_name":
        name = text.strip()
        if not name:
            send_or_edit(chat_id, "❌ اسم پنل نمی‌تونه خالی باشه، دوباره بفرست!")
            return
        if not valid_panel_name(name):
            send_or_edit(chat_id, "❌ اسم پنل باید حداکثر ۱۴ حرف باشد و شامل «:» یا «%» نباشد. دوباره بفرست!")
            return
        if name in get_panels():
            send_or_edit(chat_id, f"❌ پنلی با اسم «{esc(name)}» از قبل ثبت شده. اسم دیگه‌ای بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_url", "pnl_name": name})
        send_or_edit(chat_id, "🔗 آدرس پنل رو بفرست ( https://example.ir/dashboard)!")
    elif await_ == "pnladd_url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        st_set(chat_id, {"await": "pnladd_user", "pnl_url": panel_clean_base_url(text.strip())})
        send_or_edit(chat_id, "👤 یوزرنیم ادمین پنل را بفرست!")
    elif await_ == "pnladd_user":
        st_set(chat_id, {"await": "pnladd_pass", "pnl_user": text.strip()})
        send_or_edit(chat_id, "🔑 پسورد ادمین پنل را بفرست!")
    elif await_ == "pnladd_pass":
        name, url, user = str(st_get(chat_id, "pnl_name", "")), str(st_get(chat_id, "pnl_url", "")), str(st_get(chat_id, "pnl_user", ""))
        pw = text.strip()
        st_pop(chat_id)
        send_or_edit(chat_id, "🔍 در حال تست اتصال...")
        r = panel_ping({"base_url": url, "username": user, "password": pw, "ptype": "pasarguard"})
        if not r.get("ok"):
            send_or_edit(chat_id, "❌ لاگین ناموفق\nدوباره از «➕ افزودن پنل» شروع کن.")
            return
        panels = get_panels()
        final = name or f"پنل {len(panels) + 1}"
        i = 2
        while final in panels:
            final = f"{name} {i}"
            i += 1
        panels[final] = {"base_url": url, "username": user, "password": panel_encrypt_pw(pw), "ptype": "pasarguard", "active": True}
        set_setting("panels", panels)
        send_or_edit(chat_id, f"✅ پنل «{esc(final)}» اضافه و وصل شد.", admin_menu_kb())

def admin_panel_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    panels[name]["active"] = not panels[name].get("active")
    set_setting("panels", panels)
    send_or_edit(chat_id, f"🟢 پنل «{esc(name)}» فعال شد." if panels[name]["active"] else f"🔴 پنل «{esc(name)}» غیرفعال شد.")
    admin_panel_view(chat_id, name)

def admin_panel_edit_start(chat_id: int, name: str) -> None:
    if name not in get_panels():
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    send_or_edit(chat_id, f"✏️ چه چیزی از پنل «{esc(name)}» ویرایش بشه؟", ikb(
        [InlineKeyboardButton("📛 نام پنل", callback_data=f"pnledit:name:{name}")], [InlineKeyboardButton("🔗 آدرس پنل", callback_data=f"pnledit:url:{name}")],
        [InlineKeyboardButton("👤 یوزر ادمین", callback_data=f"pnledit:user:{name}"), InlineKeyboardButton("🔑 پسورد ادمین", callback_data=f"pnledit:pass:{name}")],
        [InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")]))

def admin_panel_test_toggle(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = panels[name]
    d["is_test_panel"] = not d.get("is_test_panel")
    note = ""
    if d["is_test_panel"] and (not d.get("test_gb") or not d.get("test_days")):
        d["test_gb"] = d.get("test_gb") or 1
        d["test_days"] = d.get("test_days") or 1
        note = "\n⚙️ حجم/مدت ست نبود — دیفالت 1 گیگ / 1 روز اعمال شد (از «⚙️ حجم/مدت تست» قابل تغییر است)."
    set_setting("panels", panels)
    send_or_edit(chat_id, ("🧪 سرویس تست روشن شد." if d["is_test_panel"] else "🧪 سرویس تست خاموش شد.") + note)
    admin_panel_view(chat_id, name)

def admin_panel_test_prompt(chat_id: int, name: str) -> None:
    st_set(chat_id, {"await": "pnltest", "pnltest_name": name})
    send_or_edit(chat_id, "🖊 مشخصات سرویس تست را بفرست (دو خط):\n\nحجم به گیگ: مثلا 1\nمدت به روز: مثلا 1\n\n"
                          "(این پنل برای سرویس‌های تست کاربران استفاده خواهد شد).", cancel_kb())

def admin_panel_test_apply(chat_id: int, text: str) -> None:
    name = str(st_get(chat_id, "pnltest_name", ""))
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 2 or not _is_num(lines[0]) or not _is_num(lines[1]):
        send_or_edit(chat_id, "❌ فرمت درست نیست. دو خط بفرست:\nحجم (گیگ)\nمدت (روز) — مثلا:\n1\n1.")
        return
    panels = get_panels()
    if name in panels:
        panels[name]["test_gb"] = float(lines[0])
        panels[name]["test_days"] = int(float(lines[1]))
        set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, f"✅ سرویس تست ثبت شد: {lines[0]} گیگ / {lines[1]} روز.")
    admin_panel_view(chat_id, name)

def admin_panel_rolepick(chat_id: int, name: str) -> None:
    panels = get_panels()
    p = panels.get(name)
    if not p:
        send_or_edit(chat_id, "❌ پنل یافت نشد.")
        return
    rows = []
    tok = _panel_auth(p)
    if tok:
        try:
            r = _preq(p, "GET", "/api/admin-roles/simple", token=tok)
            if r.status_code == 200:
                roles = r.json().get("roles") or []
                for role in roles:
                    rname = str(role.get("name", "")).strip().lower()
                    if role.get("is_owner") or rname in ("owner", "administrator", "مدیر کل", "مدیرکل"):
                        continue
                    r_id = role["id"]
                    r_name = role.get("name") or f"نقش {r_id}"
                    rows.append([InlineKeyboardButton(f"🛡 {r_name}", callback_data=f"pnlrole:{r_id}:{name}")])
        except Exception:
            pass
    if not rows:
        rows = [
            [InlineKeyboardButton("👑 مدیر کل (همه‌چیز)", callback_data=f"pnlrole:2:{name}")],
            [InlineKeyboardButton("👤 اپراتور (ساخت سرویس)", callback_data=f"pnlrole:3:{name}")],
            [InlineKeyboardButton("🌐 CDN (فقط سرویس)", callback_data=f"pnlrole:5:{name}")],
        ]
    rows.append([InlineKeyboardButton("◀️ بازگشت", callback_data=f"pnl:view:{name}")])
    send_or_edit(chat_id, f"🛡 نقش مدیران ساخته‌شده توسط ربات در «{esc(name)}»:", InlineKeyboardMarkup(rows))

def admin_panel_role_set(chat_id: int, rid: int, name: str) -> None:
    panels = get_panels()
    if name in panels:
        panels[name]["role_id"] = rid
        set_setting("panels", panels)
        lbl = get_panel_role_label(panels[name], rid)
    else:
        lbl = f"نقش {rid}"
    send_or_edit(chat_id, f"✅ نقش مدیران: {lbl}")
    admin_panel_view(chat_id, name)

def admin_panel_stats(chat_id: int, name: str) -> None:
    panels = get_panels()
    if name not in panels:
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    d = dict(panels[name])
    d["password"] = panel_decrypt_pw(d.get("password", ""))
    d["ptype"] = d.get("ptype") or "pasarguard"
    send_or_edit(chat_id, "📊 در حال دریافت آمار...")
    r = panel_call(d, "stats", {}) or {}
    if r.get("ok"):
        nadmins, ver = int(r.get("admins_count") or 0), r.get("version", "—")
        ram_t, ram_u, traffic, status = r.get("ram_total_gb", "—"), r.get("ram_used_gb", "—"), r.get("traffic_tb", "—"), "✅ پنل متصل است."
    else:
        nadmins, ver, ram_t, ram_u, traffic, status = 0, "—", "—", "—", "—", "🔴 قطع"
    row = q_one("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM purchases WHERE status='active'") or {"c": 0, "s": 0}
    send_or_edit(
        chat_id,
        f"📊 آمار پنل شما 👇\n\n🖥 وضعیت اتصال: {status}\n👥 تعداد مدیران ساخته شده در پنل: {nadmins}\n"
        f"📡 نسخه پنل: {ver}\n💻 رم کل سرور: {ram_t} گیگابایت\n💻 مصرف رم پنل: {ram_u} گیگابایت\n"
        f"🌐 ترافیک کل مصرف شده: {traffic} ترابایت\n🛍 تعداد فروش کل در این پنل: {row['c']}\n"
        f"🛍 جمع فروش کل: {num(row['s'])} تومان",
    )

def admin_panel_field_edit(chat_id: int, field: str, name: str) -> None:
    cur = get_panels().get(name, {})
    curval = {"user": cur.get("username", ""), "pass": "••••••", "url": cur.get("base_url", ""), "name": name,
              "extra_price": cur.get("extra_gb_price", ""), "extra_min": cur.get("extra_gb_min", "")}.get(field, "")
    st_set(chat_id, {"await": f"pnledit_{field}", "edit_pnl": name})
    hints = {"extra_price": "قیمت حجم اضافه به تومان برای هر گیگ (مثلاً 6000)!", "extra_min": "حداقل گیگ قابل خرید حجم اضافه (مثلاً 10)!",
             "name": "نام جدید پنل را بفرست!", "url": "آدرس جدید پنل را بفرست!", "user": "یوزر ادمین جدید را بفرست!",
             "pass": "پسورد ادمین جدید را بفرست!"}
    send_or_edit(chat_id, "✏️ مقدار فعلی: " + (str(curval) if curval not in ("", None) else "— تنظیم نشده") + "\n\n" + hints.get(field, "مقدار جدید را بفرست:"), cancel_kb())

def admin_panel_field_apply(chat_id: int, field: str, text: str) -> None:
    name = str(st_get(chat_id, "edit_pnl", ""))
    text = text.strip()
    panels = get_panels()
    if name not in panels:
        st_pop(chat_id)
        send_or_edit(chat_id, "پنل یافت نشد.")
        return
    if field == "name":
        if not valid_panel_name(text) or (text in panels and text != name):
            send_or_edit(chat_id, "❌ نام نامعتبر یا تکراری است (حداکثر ۱۴ حرف، بدون «:» و «%»). دوباره بفرست!")
            return
        panels = {(text if k == name else k): v for k, v in panels.items()}
        ex("UPDATE panel_plans SET panel_name=? WHERE panel_name=?", (text, name))
        set_setting("panels", panels)
        st_pop(chat_id)
        send_or_edit(chat_id, "✅ نام پنل شد: " + text)
        admin_panel_view(chat_id, text)
        return
    if field == "url":
        if not re.match(r"^https?://", text):
            send_or_edit(chat_id, "❌ آدرس باید با http(s) شروع شود. دوباره بفرست!")
            return
        panels[name]["base_url"] = panel_clean_base_url(text)
    elif field == "user":
        panels[name]["username"] = text
    elif field == "pass":
        panels[name]["password"] = panel_encrypt_pw(text)
    elif field == "extra_price":
        if not _is_num(text) or int(float(text)) < 0:
            send_or_edit(chat_id, "❌ قیمت نامعتبر (عدد تومان بفرست، 0 = حذف)!")
            return
        panels[name]["extra_gb_price"] = int(float(text))
    elif field == "extra_min":
        if not _is_num(text) or int(float(text)) < 1:
            send_or_edit(chat_id, "❌ حداقل نامعتبر (عدد گیگ بفرست)!")
            return
        panels[name]["extra_gb_min"] = int(float(text))
    else:
        st_pop(chat_id)
        return
    set_setting("panels", panels)
    st_pop(chat_id)
    send_or_edit(chat_id, "✅ ذخیره شد.")
    admin_panel_view(chat_id, name)
