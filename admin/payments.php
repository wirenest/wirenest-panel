<?php
/**
 * admin/payments.php — Reza rule: ⚙️ تنظیمات پرداخت (کارت به کارت / درگاه‌ها / ارزی)
 * هر درگاه: نمایش وضعیت + چرخ‌دنده (⚙️) برای تنظیمات (خاموش/روشن + API/ولت)
 */
function pay_methods(): array {
    return [
        'card' => ['label' => '💳 کارت به کارت', 'api_key' => null],
        'tron' => ['label' => '💵 ترون (ارزی)', 'api_key' => 'wallet_address', 'api_prompt' => '💼 آدرس ولت ترون (TRC20) را بفرست:'],
        'zarinpal' => ['label' => '🟡 زرین‌پال', 'api_key' => 'zarinpal_api', 'api_prompt' => '🔑 API مرچنت زرین‌پال را بفرست:'],
        'aqayepardakht' => ['label' => '🔵 آقای پرداخت', 'api_key' => 'aqayepardakht_api', 'api_prompt' => '🔑 کد API آقای پرداخت را بفرست:'],
    ];
}

function pay_onoff(string $key): string {
    return !empty(get_setting("pay_$key", $key === 'card' ? 1 : 0)) ? '✅ روشن' : '⛔️ خاموش';
}

function admin_payments_home(int $chatId): void {
    $rows = [];
    foreach (pay_methods() as $key => $m) {
        $rows[] = [
            ['text' => $m['label'] . ': ' . pay_onoff($key), 'callback_data' => "paytoggle:$key"],
            ['text' => '⚙️', 'callback_data' => "paycfg:$key"],
        ];
    }
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:settings']];
    send_or_edit($chatId, "⚙️ <b>تنظیمات پرداخت</b>

روشن/خاموش هر روش را با کلیک عوض کن؛ با ⚙️ تنظیمات هر روش (API/ولت) باز می‌شود.", ['inline_keyboard' => $rows]);
}

/** toggle خاموش/روشن. */
function admin_pay_toggle(int $chatId, string $key, bool $fromCfg = false): void {
    if (!isset(pay_methods()[$key])) { send_or_edit($chatId, 'روش نامعتبر.'); return; }
    $cur = !empty(get_setting("pay_$key", $key === 'card' ? 1 : 0));
    set_setting("pay_$key", $cur ? 0 : 1);
    // اگر از صفحهٔ تنظیمات همان درگاه آمده (paytoggle:key:cfg)، به همان صفحه برگرد (UX)
    if ($fromCfg) {
        admin_pay_cfg($chatId, $key);
    } else {
        admin_payments_home($chatId);
    }
}

/** ⚙️ تنظیمات یک درگاه. */
function admin_pay_cfg(int $chatId, string $key): void {
    $m = pay_methods()[$key] ?? null;
    if (!$m) { send_or_edit($chatId, 'روش نامعتبر.'); return; }
    $on = pay_onoff($key);
    $rows = [[['text' => '🔌 ' . ($on === '✅ روشن' ? 'خاموش کردن' : 'روشن کردن'), 'callback_data' => "paytoggle:$key:cfg"]]];
    if (!empty($m['api_key'])) {
        $curv = (string)get_setting($m['api_key'], '');
        $rows[] = [['text' => '🔑 تنظیم API/ولت' . ($curv !== '' ? ' (ثبت شده ✅)' : ' (ثبت نشده ❌)'), 'callback_data' => "payapi:$key"]];
        $body = $m['label'] . " — وضعیت: $on\n🔑 API: " . ($curv !== '' ? 'ثبت شده ✅' : 'ثبت نشده ❌');
    } else {
        $body = $m['label'] . " — وضعیت: $on\nبرای این روش تنظیم API لازم نیست.";
        // Reza rule: شماره کارت و صاحب کارت همین‌جا تنظیم می‌شوند (از تنظیمات پنل منتقل شد)
        if ($key === 'card') {
            $card = (string)get_setting('card_number', '');
            $owner = (string)get_setting('card_owner', '');
            $rows[] = [['text' => '💳 شماره کارت' . ($card !== '' ? ': ' . mb_substr($card, 0, 19) : ' (ثبت نشده ❌)'), 'callback_data' => 'set:card_number']];
            $rows[] = [['text' => '👤 صاحب کارت' . ($owner !== '' ? ': ' . mb_substr($owner, 0, 20) : ' (ثبت نشده ❌)'), 'callback_data' => 'set:card_owner']];
        }
    }
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:payments']];
    send_or_edit($chatId, $body, ['inline_keyboard' => $rows]);
}

/** شروع تنظیم API key. */
function admin_pay_api_start(int $chatId, string $key): void {
    $m = pay_methods()[$key] ?? null;
    if (!$m || empty($m['api_key'])) { send_or_edit($chatId, 'روش نامعتبر.'); return; }
    st_set($chatId, ['await' => "payapi:$key"]);
    send_or_edit($chatId, $m['api_prompt']);
}

/** ثبت API key از متن. */
function admin_pay_api_apply(int $chatId, string $text): void {
    $key = (string)st_get($chatId, 'await', '');
    $key = substr($key, 7); // payapi:
    $m = pay_methods()[$key] ?? null;
    st_pop($chatId);
    if (!$m || empty($m['api_key'])) { send_or_edit($chatId, 'روش نامعتبر.'); return; }
    $val = trim($text);
    if (mb_strlen($val) < 8) { send_or_edit($chatId, '❌ مقدار خیلی کوتاه است. دوباره بفرست:'); st_set($chatId, ['await' => "payapi:$key"]); return; }
    set_setting($m['api_key'], $val);
    send_or_edit($chatId, '✅ ذخیره شد.');
}
