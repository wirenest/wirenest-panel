<?php
/**
 * admin/settings.php — کپی مو‌به‌موی پایتون:
 * adm:settings → settings_kb (ui.py 223-230)، adm:general → general_settings_kb (ui.py 273-289)،
 * adm:shopgeneral → shop_general_kb (ui.py 250-270)، adm:power → power_kb (ui.py 233-247) + pw: toggles.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';

/** adm:settings — «🏬 تنظیمات فروشگاه» (کپی main.py 1934-1936 + ui.py 223-230). */
function admin_settings_home(int $chatId): void {
    send_or_edit($chatId, '🏬 <b>تنظیمات فروشگاه</b>', ['inline_keyboard' => [
        [['text' => '⚙️ تنظیمات پنل', 'callback_data' => 'adm:general']],
        [['text' => '⚙️ تنظیمات عمومی', 'callback_data' => 'adm:shopgeneral']],
        [['text' => '⚙️ تنظیمات پرداخت', 'callback_data' => 'adm:payments']],
        [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']],
    ]]);
}

/** adm:general — تنظیمات پنل (کپی ui.py 273-289). */
function admin_general_home(int $chatId): void {
    $s = all_settings();
    $tl = (int)($s['test_limit'] ?? 1);
    $card = (string)($s['card_number'] ?? 'ثبت نشده');
    $wpct = $s['quota_warn_pct'] ?? 80;
    $wd = $s['quota_warn_discount_pct'] ?? 10;
    $owner = mb_substr((string)($s['card_owner'] ?? '—'), 0, 12);
    $usd = (int)($s['usd_rate'] ?? 220000);
    send_or_edit($chatId, '⚙️ <b>تنظیمات پنل</b>', ['inline_keyboard' => [
        [['text' => "🧪 تعداد تست هر کاربر: $tl", 'callback_data' => 'set:testlimit']],
        [['text' => '💳 حداقل واریز: ' . ((int)get_setting('min_charge', 0) ?: 'خاموش') . ' تومان', 'callback_data' => 'set:min_charge'],
         ['text' => '💳 حداکثر واریز: ' . ((int)get_setting('max_charge', 0) ?: 'خاموش') . ' تومان', 'callback_data' => 'set:max_charge']],
        [['text' => "⚠️ درصد هشدار حجم: {$wpct}٪", 'callback_data' => 'set:quota_warn_pct'],
         ['text' => "🎁 تخفیف هشدار: {$wd}٪", 'callback_data' => 'set:quota_warn_discount_pct']],
        // Reza rule: شماره کارت/صاحب کارت به تنظیمات پرداخت (درگاه کارت) منتقل شد
        [['text' => '💲 نرخ دلار: ' . number_format($usd) . ' تومان (دستی)', 'callback_data' => 'set:usd_rate']],
        [['text' => '◀️ بازگشت', 'callback_data' => 'adm:settings']],
    ]]);
}

/** adm:shopgeneral — تنظیمات عمومی (کپی ui.py 250-270). */
function admin_shopgeneral_home(int $chatId): void {
    $s = all_settings();
    $fj = !empty($s['force_join']) ? '✅ فعال' : '⛔️ خاموش';
    $rg = !empty($s['report_group']) ? 'ثبت شده ✅' : 'ثبت نشده ❌';
    send_or_edit($chatId, '⚙️ <b>تنظیمات عمومی</b>', ['inline_keyboard' => [
        [['text' => "🔒 عضویت اجباری: $fj", 'callback_data' => 'set:force_join'],
         ['text' => '📢 کانال‌های اجباری', 'callback_data' => 'set:channels']],
        [['text' => '📝 متن شروع', 'callback_data' => 'set:start_text']],
        [['text' => '📝 متن رد رسید', 'callback_data' => 'set:reject_text'],
         ['text' => '⚠️ هشدار اتمام حجم', 'callback_data' => 'set:quota_warn_text']],
        [['text' => '🗑 اطلاع‌رسانی حذف', 'callback_data' => 'set:autoremove_text'],
         ['text' => '❓ متن سوالات متداول', 'callback_data' => 'set:faq_text']],
        [['text' => '📝 متن ضوابط و مقررات خرید', 'callback_data' => 'set:nonrefund_text'],
         ['text' => '✅ متن شرایط و توضیحات', 'callback_data' => 'set:conditions_text']],
        [['text' => '📡 راهنمای اتصال', 'callback_data' => 'adm:guides']],
        [['text' => "📣 کانال گزارشات: $rg", 'callback_data' => 'set:report_group']],
        [['text' => '◀️ بازگشت', 'callback_data' => 'adm:settings']],
    ]]);
}

/** adm:power — خاموش/روشن (کپی ui.py 233-247). */
function admin_power_home(int $chatId): void {
    send_or_edit($chatId, "🔌 <b>خاموش/روشن</b>\nبخش‌ها را باز/بسته کن:", ['inline_keyboard' => [
        [['text' => '🛒 فروش: ' . (feat_on('buy', true) ? '🟢 باز' : '🔴 بسته'), 'callback_data' => 'pw:buy'],
         ['text' => '🧪 تست: ' . (feat_on('test', true) ? '🟢 باز' : '🔴 بسته'), 'callback_data' => 'pw:test']],
        [['text' => '🤖 ربات: ' . (bot_enabled() ? '🟢 روشن' : '🔴 خاموش'), 'callback_data' => 'pw:bot']],
        [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']],
    ]]);
}

/** pw:<key> toggle — کپی main.py 2084-2094. */
function admin_power_toggle(int $chatId, string $key): void {
    if ($key === 'bot') {
        set_setting('bot_enabled', bot_enabled() ? 0 : 1);
    } else {
        $f = features();
        $f[$key] = !feat_on($key, true);
        set_setting('features', $f);
    }
    admin_power_home($chatId);
}

/** set:<key> prompt — python map of prompts (کپی متن‌های درخواست مقدار). */
function admin_set_prompt(int $chatId, string $key): void {
    st_set($chatId, ['await' => "set:$key"]);
    $prompts = [
        'start_text' => '📝 متن پیام /start را بفرست (متغیرهای {name} و {username} مجازند):',
        'reject_text' => '📝 متن رد رسید را بفرست:',
        'quota_warn_text' => '⚠️ متن هشدار اتمام حجم را بفرست:',
        'autoremove_text' => '🗑 متن اطلاع‌رسانی حذف را بفرست:',
        'faq_text' => '❓ متن سوالات متداول را بفرست:',
        'nonrefund_text' => '📝 متن ضوابط و مقررات خرید را بفرست:',
        'conditions_text' => '✅ متن شرایط و توضیحات را بفرست:',
        'report_group' => '📣 آیدی کانال گزارشات را بفرست (مثل @mychannel یا -100...):',
        'testlimit' => '🧪 تعداد تست هر کاربر را بفرست:',
        'quota_warn_pct' => '⚠️ درصد هشدار حجم را بفرست (مثلاً 90):',
        'quota_warn_discount_pct' => '🎁 درصد تخفیف هشدار را بفرست (مثلاً 10):',
        'card_number' => '💳 شماره کارت را بفرست:',
        'card_owner' => '👤 نام صاحب کارت را بفرست:',
        'usd_rate' => '💲 نرخ دلار (تومان) را بفرست:',
        'tron_wallet' => '💼 آدرس ولت ترون را بفرست:',
        'min_charge' => '💳 حداقل واریز را بفرست (تومان):',
        'max_charge' => '💳 حداکثر واریز را بفرست (تومان):',
    ];
    // Reza rule: مقدار فعلی + دکمهٔ لغو هنگام ویرایش متن‌ها
    $txtKeys = ['start_text','reject_text','quota_warn_text','autoremove_text','faq_text','nonrefund_text','conditions_text','report_group','card_number','card_owner','tron_wallet'];
    $prompt = $prompts[$key] ?? ("مقدار جدید برای $key را بفرست:");
    $cur = (string)get_setting($key, '');
    $preview = '';
    if (in_array($key, $txtKeys, true)) {
        $preview = $cur !== ''
            ? "\n\n📌 مقدار فعلی:\n" . mb_substr($cur, 0, 400)
            : "\n\n📌 متنی تنظیم نشده — پیش‌فرض ربات استفاده می‌شود.";
    }
    $kb = ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]];
    send_or_edit($chatId, $prompt . $preview, $kb);
}

/** ❌ لغو ویرایش متن تنظیمات. */
function admin_set_cancel(int $chatId): void {
    st_pop($chatId);
    send_or_edit($chatId, '↩️ ویرایش لغو شد.');
    admin_shopgeneral_home($chatId);
}

/** Numeric keys: comma-strip + validate (parity with python R2.2 fix). */
function admin_set_apply(int $chatId, string $key, string $text): bool {
    $numeric = ['usd_rate', 'min_charge', 'max_charge', 'quota_warn_pct', 'quota_warn_discount_pct', 'testlimit'];
    if (in_array($key, $numeric, true)) {
        // اعداد امضادار/مثبت با regex دقیق وارد شوند — ساکتانه منفی حذف نمی‌شود
        $clean = trim(str_replace(',', '', $text));
        if (!preg_match('/^-?\d+(\.\d+)?$/', $clean) || (float)$clean < 0) {
            send_or_edit($chatId, '❌ فقط عدد مثبت بفرست (مثلاً 220000 یا 220,000):');
            return false; // keep state
        }
        $val = str_contains($clean, '.') ? (float)$clean : (int)$clean;
        set_setting($key, $val);
        send_or_edit($chatId, '✅ ذخیره شد.'); // Reza rule: کلید داخلی $key در پیام نمایش داده نشود
        return true;
    }
    // text keys
    set_setting($key, $text);
    send_or_edit($chatId, '✅ ذخیره شد.');
    return true;
}


/** set:channels — کانال‌های اجباری (کپی main.py 2604-2614). */
function admin_channels_home(int $chatId): void {
    $chans = db()->query('SELECT * FROM channels ORDER BY id')->fetchAll();
    $kb = ['inline_keyboard' => []];
    foreach ($chans as $c) {
        $kb['inline_keyboard'][] = [['text' => "❌ {$c['channel_id']}", 'callback_data' => "delchan:" . urlencode((string)$c['channel_id'])]];
    }
    $kb['inline_keyboard'][] = [['text' => '➕ افزودن @کانال', 'callback_data' => 'addchan']];
    // toggle عضویت اجباری فقط در تنظیمات عمومی است (فرمان رضا: دکمهٔ تکراری از اینجا حذف شد)
    $kb['inline_keyboard'][] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:shopgeneral']];
    send_or_edit($chatId, '📢 کانال‌های اجباری:', $kb);
}

/** delchan:<id> — حذف کانال (کپی main.py 3120-3131). */
function admin_channel_delete(int $chatId, string $cid): void {
    db()->prepare('DELETE FROM channels WHERE channel_id=?')->execute([$cid]);
    admin_channels_home($chatId);
}

/** addchan — پرامپت افزودن (کپی main.py 3606-3609). */
function admin_channel_add_start(int $chatId): void {
    st_set($chatId, ['await' => 'addchan']);
    send_or_edit($chatId, '📢 آیدی کانال را بفرست (@id یا -100...):');
}

/** addchan state — ثبت کانال (کپی main.py 3606-3609). */
function admin_channel_add_apply(int $chatId, string $text): void {
    st_pop($chatId);
    $ch = trim($text);
    if ($ch === '' ) { send_or_edit($chatId, '❌ آیدی معتبر بفرست:'); return; }
    if ($ch[0] !== '@' && $ch[0] !== '-') { $ch = '@' . $ch; }
    db()->prepare('INSERT INTO channels(channel_id, title) VALUES(?,?)')->execute([$ch, '']);
    send_or_edit($chatId, '✅ کانال اضافه شد');
}