<?php
/**
 * handlers.php — update router (parity با main.py)
 * Message texts, callback queries, STATE machine, single-flight buy.
 */

require_once __DIR__ . '/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';
require_once BASE_DIR . '/flows/test_service.php';
require_once BASE_DIR . '/flows/extra_gb.php';

// ---------- STATE (in-memory, parity with python STATE) — file-backed for CLI persistence ----------
$STATE_FILE = BASE_DIR . '/data/state.json';
function state_load(): array {
    global $STATE_FILE;
    return is_file($STATE_FILE) ? (json_decode(file_get_contents($STATE_FILE), true) ?: []) : [];
}
function state_save(array $s): void {
    global $STATE_FILE;
    file_put_contents($STATE_FILE, json_encode($s, JSON_UNESCAPED_UNICODE), LOCK_EX);
}
$STATE = state_load();
function st_get(int $uid, string $k, $default = null) {
    global $STATE;
    return $STATE[$uid][$k] ?? $default;
}
function st_set(int $uid, array $kv): void {
    global $STATE;
    $STATE[$uid] = array_merge($STATE[$uid] ?? [], $kv);
    state_save($STATE);
}
function st_pop(int $uid): void {
    global $STATE;
    unset($STATE[$uid]);
    state_save($STATE);
}
function st_all(int $uid): array {
    global $STATE;
    return $STATE[$uid] ?? [];
}

// ---------- user helpers ----------
function upsert_user(int $tgId, ?string $username): void {
    db()->prepare("INSERT INTO users(tg_id,username) VALUES(?,?)
                   ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username")
       ->execute([$tgId, $username]);
}
function get_balance(int $tgId): int {
    $st = db()->prepare('SELECT balance FROM users WHERE tg_id=?');
    $st->execute([$tgId]);
    $r = $st->fetch();
    return (int)($r['balance'] ?? 0);
}
function spend_balance(int $tgId, int $amount): bool {
    // atomic — parity with db.spend_balance
    $st = db()->prepare("UPDATE users SET balance = balance - ? WHERE tg_id=? AND balance >= ?");
    $st->execute([$amount, $tgId, $amount]);
    return $st->rowCount() === 1;
}
function add_balance(int $tgId, int $amount): void {
    db()->prepare("INSERT INTO users(tg_id,balance) VALUES(?,?) ON CONFLICT(tg_id) DO UPDATE SET balance=balance+?")
       ->execute([$tgId, max(0, $amount), $amount]);
}
function gen_username(string $prefix = 'srv'): string {
    $chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    $s = $prefix;
    for ($i = 0; $i < 8; $i++) $s .= $chars[random_int(0, 35)];
    return $s;
}
function strong_password(): string {
    // پالیسی پسورد پنل (Pasarguard): حداقل ۱۲ کاراکتر + ۲ حرف بزرگ + کاراکتر خاص — در غیر این صورت 422
    $lower = 'abcdefghjkmnpqrstuvwxyz';
    $upper = 'ABCDEFGHJKLMNPQRSTUVWXYZ';
    $digit = '23456789';
    $special = '!@#$%&*?';
    $out = '';
    for ($i = 0; $i < 6; $i++) $out .= $lower[random_int(0, strlen($lower) - 1)];
    for ($i = 0; $i < 3; $i++) $out .= $upper[random_int(0, strlen($upper) - 1)];
    for ($i = 0; $i < 3; $i++) $out .= $digit[random_int(0, strlen($digit) - 1)];
    $out .= $special[random_int(0, strlen($special) - 1)];
    return str_shuffle($out);
}

// ---------- receipts ----------
function create_receipt(int $tgId, int $amount, string $refText): int {
    db()->prepare('INSERT INTO receipts(tg_id,amount,ref_text) VALUES(?,?,?)')->execute([$tgId, $amount, $refText]);
    return (int)db()->lastInsertId();
}
function receipt_ref_exists(string $needle): bool {
    // exact OR token-match inside composite ref_text (tron replay guard parity)
    $st = db()->prepare("SELECT 1 FROM receipts WHERE ref_text=? LIMIT 1");
    $st->execute([$needle]);
    if ($st->fetch()) return true;
    $st = db()->prepare("SELECT 1 FROM receipts WHERE ('|' || ref_text || '|') LIKE ? LIMIT 1");
    $st->execute(['%' . "| $needle|" . '%']);
    return (bool)$st->fetch();
}

/** Purchase report to channel (گزارش خرید) — purchase-only + masked + jalali.
 * دکمهٔ شیشه‌ای «ورود به پنل‌ساز» (URL پنل) + لینک ربات (username از getMe، بدون هاردکد).
 * قالب (فرمان رضا): کاربر/سرویس ماسک‌شده، پلن، مبلغ، هشتگ‌ها + دکمهٔ ورود به پنل‌ساز. */
function bot_username(): string {
    // username ربات را از getMe می‌گیرد و در settings کش می‌کند — روی هر رباتی که سورس ران شود خودش تشخیص می‌دهد.
    $cached = (string)get_setting('bot_username', '');
    if ($cached !== '') return $cached;
    $me = tg('getMe');
    $un = (string)($me['result']['username'] ?? '');
    if ($un !== '') set_setting('bot_username', $un);
    return $un;
}

function report_purchase(int $tgId, string $uname, string $planTitle, int $amount, string $tag, string $panelUrl = ''): void {
    // قالب فرمان رضا: هدر + تاریخ + کاربر + سرویس ماسک‌شده + پلن + مبلغ + «فقط یک هشتگ» + فقط یک دکمهٔ شیشه‌ای
    // tag = 'خرید' → #خرید_پنل | 'تست' → #تست | 'افزایش' → #افزایش_حجم
    $rg = (string)get_setting('report_group');
    if ($rg === '') return; // هنوز تنظیم نشده
    $u = mask_mid((string)$tgId);
    $un = mask_mid($uname);
    $hash = match ($tag) {
        'تست' => '#تست',
        'افزایش' => '#افزایش_حجم',
        default => '#خرید_پنل',
    };
    $txt = "🛒 <b>گزارش خرید پنل</b>\n"
         . "🗓 " . jdate() . " — ⏰ " . date('H:i:s') . "\n"
         . "\n👤 کاربر:  $u\n"
         . "🆔 سرویس: $un\n"
         . "📦 پلن: $planTitle\n"
         . "💵 مبلغ: " . fmt_price($amount) . "\n"
         . $hash . "\n";
    $bot = bot_username();
    if ($bot !== '') $txt .= "🤖 ربات: @" . $bot . "\n";
    // فقط یک دکمهٔ شیشه‌ای: ورود به پنل‌ساز → لینک **ربات** (t.me/username از getMe) — فرمان رضا؛ لینک پنل نیست.
    $kb = null;
    if ($bot !== '') {
        $kb = ['inline_keyboard' => [[['text' => '🌐 ورود به پنل‌ساز', 'url' => 'https://t.me/' . $bot]]]];
    }
    tg_send(get_setting('report_group'), $txt, $kb); // @username یا id عددی هر دو
}

// ---------- main menu texts (کپی main.py 199-200: {name} و {username} جایگزین می‌شوند) ----------
function welcome_text(array $from = []): string {
    $s = (string)get_setting('start_text', '');
    $greet = $s !== '' ? $s : "سلام {name} 👋\nبه ربات فروش سرویس خوش اومدی!";
    $name = (string)($from['first_name'] ?? '');
    $uname = (string)($from['username'] ?? '');
    return str_replace(
        ['{name}', '{username}'],
        [htmlspecialchars($name), '@' . $uname],
        $greet);
}

// ================= ROUTER =================
function handle_update(array $u): void {
    // ---- force join gate (قبل از هر چیز؛ ادمین‌ها مستثنا) ----
    if (get_setting('force_join', false) && !force_join_ok($u)) return;
    if (isset($u['message']))      { handle_message($u['message']); return; }
    if (isset($u['callback_query'])) {
        $cq = $u['callback_query'];
        $cbData = (string)($cq['data'] ?? '');
        if ($cbData === 'fj:check') {
            $uid = (int)($cq['from']['id'] ?? 0);
            $mid = (int)($cq['message']['message_id'] ?? 0);
            if ($mid) tg('editMessageText', ['chat_id' => $uid, 'message_id' => $mid, 'text' => '✅ عضویت تأیید شد! خوش آمدی 🎉']);
            st_pop($uid);
            tg_send($uid, welcome_text(['first_name' => (string)($cq['from']['first_name'] ?? '')]), main_menu_kb(is_admin($uid)));
            return;
        }
        ctx_msg_id_set((int)($cq['message']['message_id'] ?? 0)); handle_callback($u['callback_query']); ctx_msg_id_set(null); return;
    }
}

/** عضویت اجباری: اگر کاربر در همهٔ کانال‌ها عضو باشد true. غیرعضو → پیام هشدار با دکمه‌ها و false. */
function force_join_ok(array $u): bool {
    $uid = (int)($u['message']['from']['id'] ?? $u['callback_query']['from']['id'] ?? 0);
    if ($uid && is_admin($uid)) return true;
    $chans = db()->query('SELECT channel_id FROM channels ORDER BY id')->fetchAll();
    if (!$chans) return true; // کانالی ثبت نشده → gate بلااثر
    $kb = ['inline_keyboard' => []];
    $missing = false;
    foreach ($chans as $c) {
        $cid = (string)$c['channel_id'];
        $joined = false;
        try {
            $r = tg('getChatMember', ['chat_id' => $cid, 'user_id' => $uid]);
            $st = $r['result']['status'] ?? 'left';
            $joined = in_array($st, ['creator', 'administrator', 'member'], true);
        } catch (Throwable $e) { $joined = true; /* کانال در دسترس نیست → بلاک نکن */ }
        if (!$joined) {
            $missing = true;
            if (str_starts_with($cid, '@') || str_starts_with($cid, 'https://') || str_starts_with($cid, 'http://')) {
                $kb['inline_keyboard'][] = [['text' => '📢 عضویت در کانال', 'url' => str_starts_with($cid, '@') ? ('https://t.me/' . substr($cid, 1)) : $cid]];
            }
        }
    }
    if (!$missing) return true;
    $kb['inline_keyboard'][] = [['text' => '🔄 بررسی عضویت', 'callback_data' => 'fj:check']];
    tg_send($uid, '⛔️ برای استفاده از ربات ابتدا در کانال‌های زیر عضو شو، بعد «🔄 بررسی عضویت» را بزن:', $kb);
    return false;
}

function handle_message(array $m): void {
    $chatId = (int)$m['chat']['id'];
    $text = trim((string)($m['text'] ?? ''));
    $from = $m['from'];
    if (($m['chat']['type'] ?? '') !== 'private') return;

    upsert_user($chatId, $from['username'] ?? null);
    $admin = is_admin($chatId);

    // master power switch (admins bypass) — parity
    if (!get_setting('bot_enabled', true) && !$admin) {
        tg_send($chatId, '🔴 ربات موقتاً غیرفعال است — بعداً مراجعه کنید.');
        return;
    }

    // ---- menu buttons (reply kb) ----
    $L = LBL();
    switch ($text) {
        case '/start':
            st_pop($chatId);
            tg_send($chatId, welcome_text($from), main_menu_kb($admin));
            return;
        case $L['test']:
            if (!feat_on('test', true) && !$admin) { tg_send($chatId, '🧪 تست فعلاً بسته است.'); return; }
            handle_test_start($chatId); return;
        case $L['buy']:
            if (!feat_on('buy', true) && !$admin) { tg_send($chatId, '🛒 فروش فعلاً بسته است.'); return; }
            show_buy_screen($chatId); return;
        case $L['services']:
            show_services($chatId); return;
        case $L['wallet']:
            show_wallet($chatId); return;
        case $L['guide']:
            show_guide($chatId); return;
        case $L['conditions']:
            show_conditions($chatId); return;
        case $L['support']:
            start_support($chatId); return;
        case $L['faq']:
            // FAQ: send text ABOVE the menu — must NOT close the menu (Reza rule)
            $faq = get_setting('faq_text') ?: '❓ سوالات متداول فعلاً تنظیم نشده.';
            tg_send($chatId, (string)$faq, main_menu_kb($admin));
            return;
        case $L['admin']:
            if ($admin) tg_send($chatId, '👨‍💼 پنل مدیریت', admin_menu_kb());
            return;
    }

    // ---- STATE machine (dialogs) ----
    handle_state_message($chatId, $text, $m);
}

// ---------- buy / wallet / misc screens (کپی مو‌به‌موی main.py) ----------
function show_buy_screen(int $chatId): void {
    $plans = db()->query('SELECT * FROM panel_plans WHERE active=1 ORDER BY price')->fetchAll() ?: [];
    $tariffs = db()->query('SELECT * FROM tariffs WHERE is_active=1 ORDER BY price')->fetchAll() ?: [];
    if (!$plans && !$tariffs) { tg_send($chatId, 'فعلا تعرفه‌ای تعریف نشده.', main_menu_kb(is_admin($chatId))); return; }
    $text = "💳 <b>تعرفه‌های سرویس:</b>\n\n";
    if ($tariffs) {
        $text .= implode("\n", array_map(fn($t) => '• ' . htmlspecialchars((string)$t['title']), $tariffs)) . "\n";
    }
    if ($plans) {
        if ($tariffs) $text .= "\n";
        $text .= "📦 <b>پلن‌های حجمی:</b>\n" . implode("\n", array_map(
            fn($pl) => '• ' . fmt_gb($pl['volume_gb']) . ' گیگ — ' . number_format((float)$pl['price']) . ' تومان',
            $plans));
    }
    tg_send($chatId, $text, buy_kb($plans, $tariffs));
}

function show_services(int $chatId): void {
    services_home($chatId); // exact copy in flows/services.php
}

function show_wallet(int $chatId): void {
    wallet_screen($chatId); // exact copy in flows/wallet.php
}

function show_guide(int $chatId): void {
    // پاریتی main.py 1389-1401: منوی راهنما داینامیک از guide_topics (guide:<id>)
    // داخل callback همان پیام ویرایش می‌شود (فرمان رضا: ویرایش پیام، نه پیام جدید)
    $intro = get_setting('guide_intro') ?: '📌 راهنمای اتصال — سیستم‌عامل خود را انتخاب کنید:';
    $topics = db()->query('SELECT id, title FROM guide_topics ORDER BY id')->fetchAll();
    $kb = ['inline_keyboard' => []];
    foreach ($topics as $t) {
        $kb['inline_keyboard'][] = [['text' => (string)$t['title'], 'callback_data' => 'guide:' . (int)$t['id']]];
    }
    $kb['inline_keyboard'][] = [['text' => '🏠 منوی اصلی', 'callback_data' => 'm:home']];
    send_or_edit($chatId, (string)$intro, $kb);
}

function show_conditions(int $chatId): void {
    // کپی دقیق متن پیش‌فرض main.py 4250-4259
    $c = get_setting('conditions_text') ?: (
        "📋 <b>شرایط و توضیحات ربات</b>\n\n"
        . "✅ پنل ادمین محدود روی سرور قدرتمند تحویل می‌گیرید\n"
        . "♾️ <b>بدون محدودیت زمان</b> — پنل تا تمام شدن حجم معتبر است\n"
        . "📦 سهمیه مشخص در هر پلن که بین مشتریان خود تقسیم می‌کنید\n"
        . "🛠 پنل مدیریت کامل: ساخت و مدیریت سرویس‌ها برای مشتریانتان\n"
        . "➕ امکان خرید حجم اضافه هر زمان\n"
        . "⚡ تحویل آنی بعد از تایید پرداخت\n"
        . "☎️ پشتیبانی پاسخ‌گو\n\n"
        . "❗ مسئولیت استفاده از پنل با خریدار است؛ فروش غیرمجاز ممنوع.");
    tg_send($chatId, (string)$c, main_menu_kb(is_admin($chatId)));
}

function start_support(int $chatId): void {
    // کپی دقیق main.py 4261-4269: نمایش آیدی پشتیبانی + دعوت به تیکت
    $sup = (string)get_setting('support_id', '');
    $txt = '☎️ پشتیبانی';
    if ($sup) $txt .= "\nآیدی پشتیبانی: @" . ltrim($sup, '@');
    $txt .= "\n\nبرای ارسال تیکت، روی دکمه زیر بزن و پیامت را بنویس.";
    tg_send($chatId, $txt, support_kb());
    st_set($chatId, ['await' => 'support_msg']);
}

// ---------- STATE dialog handling ----------
function handle_state_message(int $chatId, string $text, array $m): void {
    $await = (string)st_get($chatId, 'await', '');
    if ($text === '/cancel') { st_pop($chatId); tg_send($chatId, '↩️ لغو شد.', main_menu_kb(is_admin($chatId))); return; }
    if ($await === '') return; // no dialog

    // Reza rule: payapi:<gateway> — ثبت API/ولت درگاه‌ها
    if (str_starts_with($await, 'payapi:')) {
        admin_pay_api_apply($chatId, $text);
        return;
    }

    // آموزش: ویرایش متن موضوع (کپی main.py 3802-3810)
    if (str_starts_with($await, 'helpedit_body:')) {
        admin_help_body_edit($chatId, $await, $text);
        return;
    }

    switch ($await) {
        case 'support_msg':
            // کپی main.py 3877-3898: بازگشت/ثبت تیکت/پیام به ادمین با دکمه پاسخ و بستن
            if ($text === '🏠 بازگشت به منوی اصلی') {
                st_pop($chatId);
                tg_send($chatId, '🏠 بازگشتید!', main_menu_kb(is_admin($chatId)));
                return;
            }
            st_pop($chatId);
            db()->prepare('INSERT INTO tickets(tg_id,message,status) VALUES(?,?,?)')->execute([$chatId, $text, 'open']);
            $tid = (int)db()->lastInsertId();
            tg_send($chatId, '🚀 پیام شما ارسال شد؛ منتظر پاسخ پشتیبانی باشید.', main_menu_kb(is_admin($chatId)));
            notify_admins(
                "🤙 تیکت پشتیبانی #$tid\nاز: <a href='tg://user?id=$chatId'>$chatId</a>\n\n"
                . htmlspecialchars(mb_substr($text, 0, 800)),
                ['inline_keyboard' => [[
                    ['text' => '✉️ پاسخ', 'callback_data' => "um:msg:$chatId"],
                    ['text' => '✅ بستن تیکت', 'callback_data' => "tkclose:$tid"],
                ]]]);
            return;

        case 'topup_amount':
            // کپی پایتون: بعد از دریافت مبلغ → نمایش کارت + دکمه ارسال رسید (main.py 1217-1249)
            // پایتون \d{4,} می‌خواهد (main.py 4015) — حداقل ۴ رقم متوالی
            if (!preg_match('/(\d{4,})/', str_replace(',', '', $text), $mm2)) {
                tg_send($chatId, 'عدد معتبر بفرست (مثلاً 100000) یا «🏠 بازگشت به منوی اصلی» بزن.');
                return;
            }
            $amount = (int)$mm2[1];
            $mn = (int)(get_setting('min_charge', 0) ?: 0);
            $mx = (int)(get_setting('max_charge', 0) ?: 0);
            if ($mn && $amount < $mn) { tg_send($chatId, "⬇️ حداقل شارژ " . fmt_price($mn) . " است."); return; }
            if ($mx && $amount > $mx) { tg_send($chatId, "⬆️ حداکثر شارژ " . fmt_price($mx) . " است."); return; }
            st_set($chatId, ['await' => 'wallet_card', 'amount' => $amount]);
            wallet_card_sent($chatId);
            return;

        case 'card_wait':
        case 'wallet_card':
            // passive: تا وقتی دکمه «ارسال کردم» نزده، متن نادیده (main.py 1239 + await wallet_card 4027)
            return;

        // ----- admin dialogs -----
        case 'finduser':
            admin_finduser_apply($chatId, $text);
            return;

        case 'search_order':
            admin_search_order_apply($chatId, $text);
            return;

        case 'addchan':
            admin_channel_add_apply($chatId, $text);
            return;

        case 'helpadd_title':
            admin_help_title_apply($chatId, $text);
            return;

        case 'helpadd_body':
            admin_help_body_apply($chatId, $text);
            return;

        case 'massbal':
        case 'mass_sub':
            admin_massbal_apply($chatId, $text);
            return;

        case 'um:addbal':
        case 'um:subbal':
            admin_um_bal_apply($chatId, $text);
            return;

        case 'um:msg':
            admin_um_msg_apply($chatId, $text);
            return;

        case 'dsc_code':
            admin_dsc_code_apply($chatId, $text);
            return;
        case 'dsc_value':
            admin_dsc_value_apply($chatId, $text);
            return;
        case 'gift_code':
            admin_gift_code_apply($chatId, $text);
            return;
        case 'gift_amount':
            admin_gift_amount_apply($chatId, $text);
            return;
        case 'pnltest':
            admin_panel_test_apply($chatId, $text);
            return;
        case 'pladd_gb':
            admin_plan_gb_apply($chatId, $text);
            return;
        case 'pladd_price':
            admin_plan_price_apply($chatId, $text);
            return;
        case 'pled:price':
            admin_plan_edit_apply($chatId, 'price', $text);
            return;
        case 'pled:gb':
            admin_plan_edit_apply($chatId, 'gb', $text);
            return;
        case 'pnledit_name':
            admin_panel_field_apply($chatId, 'name', $text);
            return;
        case 'pnledit_extra_price':
            admin_panel_field_apply($chatId, 'extra_price', $text);
            return;
        case 'pnledit_extra_min':
            admin_panel_field_apply($chatId, 'extra_min', $text);
            return;
        case 'pnledit_pass':
            admin_panel_field_apply($chatId, 'pass', $text);
            return;
        case 'pnledit_user':
            admin_panel_field_apply($chatId, 'user', $text);
            return;
        case 'gift_redeem':
            // کد هدیه کاربر (کپی main.py 3272-3278) — max_uses=0 یعنی بی‌نهایت
            $code = strtoupper(trim($text));
            $g = db()->prepare('SELECT * FROM gift_codes WHERE code=? AND active=1 AND (max_uses=0 OR used < max_uses)');
            $g->execute([$code]);
            $row = $g->fetch();
            if (!$row) { tg_send($chatId, '❌ کد هدیه نامعتبر یا قبلاً استفاده شده. دوباره بفرست یا /cancel:'); return; }
            // هر کاربر هر کد را فقط یک‌بار می‌تواند استفاده کند (پاریتی db.redeem_gift پایتون)
            $dup = db()->prepare('SELECT 1 FROM gift_redemptions g WHERE g.gift_id=? AND g.tg_id=?');
            $dup->execute([(int)$row['id'], $chatId]);
            if ($dup->fetch()) { tg_send($chatId, '❌ تو قبلاً این کد هدیه را استفاده کردی.'); return; }
            db()->prepare('UPDATE gift_codes SET used = used + 1 WHERE id=?')->execute([(int)$row['id']]);
            db()->prepare('INSERT OR IGNORE INTO gift_redemptions(gift_id, tg_id) VALUES(?,?)')->execute([(int)$row['id'], $chatId]);
            add_balance($chatId, (int)$row['amount']);
            st_pop($chatId);
            tg_send($chatId, "🎉 تبریک! کد هدیه «{$code}» اعمال شد\n" . fmt_price((int)$row['amount']) . ' به کیف پولت اضافه شد.');
            return;
        case 'bcast2_text':
            bcast_text_received($chatId, $text);
            return;

        case 'bcast_text':
            $b = st_get($chatId, 'bcast', []);
            $b['text'] = $text;
            $b['stage'] = 'aud';
            st_set($chatId, ['bcast' => $b]);
            st_pop($chatId);
            tg_send($chatId, 'مخاطب پیام؟', bcast_audience_kb());
            return;
    }

    // set:<key> numeric/text dialogs (admin settings)
    if (str_starts_with($await, 'set:')) {
        $key = substr($await, 4);
        if (admin_set_apply($chatId, $key, $text)) {
            st_pop($chatId);
            admin_settings_home($chatId);
        }
        return;
    }

    // panel add wizard: name -> url -> user -> pass
    if (str_starts_with($await, 'pnladd_')) {
        admin_panel_add_step($chatId, $await, $text);
        return;
    }

    // service password change
    if (str_starts_with($await, 'svcnewpass:')) {
        service_change_password_apply($chatId, $text);
        return;
    }

    // pending buy: custom username / photo receipt flows (parity python buy_custom_username)
    if ($await === 'buy_custom_username') {
        handle_buy_custom_username($chatId, $text);
        return;
    }
    // خرید حجم اضافه (main.py 4119-4190)
    if ($await === 'agent_gb') {
        handle_agent_gb($chatId, $text);
        return;
    }
    // کد تخفیف خرید (main.py 296-304 → state)
    if ($await === 'buy_discount_code') {
        handle_buy_discount_code($chatId, $text);
        return;
    }
    // رسید شارژ متنی (کد پیگیری) (main.py 4030-4054)
    if ($await === 'wallet_receipt') {
        handle_wallet_receipt_text($chatId, $text);
        return;
    }
    // ویرایش مبلغ رسید ادمین (main.py 1928-1931)
    if (str_starts_with($await, 'rcfix:')) {
        receipt_fix_apply($chatId, $text);
        return;
    }
}

function notify_admins(string $text, ?array $kb = null): void {
    $first = true;
    foreach (admin_ids() as $aid) {
        if (!$first) usleep(300000); // 0.3s spacing: avoid Telegram flood limits with many admins
        tg_send((int)$aid, $text, $kb);
        $first = false;
    }
}