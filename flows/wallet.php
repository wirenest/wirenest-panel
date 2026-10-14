<?php
/**
 * flows/wallet.php — کیف پول (کپی مو‌به‌موی main.py 1193-1249)
 * topup screen + add credit + card/tron receipt body exact texts.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';

/** Exact copy of topup() (main.py 1193-1204): wallet home. */
function wallet_screen(int $chatId): void {
    $bal = get_balance($chatId);
    send_or_edit($chatId,
        "🏦 <b>کیف پول شما</b>\n\n💵 موجودی: <b>" . fmt_price($bal) . "</b>",
        wallet_kb());
}

/** Exact copy of on_wallet_add_credit() (main.py 1207-1214). */
function start_topup(int $chatId): void {
    st_set($chatId, ['await' => 'topup_amount']);
    send_or_edit($chatId,
        "💰 مبلغ شارژ را به تومان بفرست (مثلاً: 100000)\n\n"
        . "یا «🏠 بازگشت به منوی اصلی» بزن.");
}

/** wal:addcredit — کپی on_wallet_add_credit_btn (main.py 681-712):
 * در حین خرید فعال مبلغِ کسری (قیمت − موجودی) مستقیم به صفحهٔ پرداخت می‌رود؛ بدون پرسیدن مبلغ. */
function wallet_add_credit(int $chatId): void {
    $st = st_all($chatId);
    $price = 0;
    $bp = $st['buy_plan'] ?? null;
    if (is_array($bp)) {
        $price = (int)($bp['orig_price'] ?? $bp['price'] ?? 0);
    } elseif (($st['xp_kind'] ?? '') === 'extragb') {
        $price = (int)($st['xp_price'] ?? 0);
    } elseif (!empty($st['back_tariff'])) {
        $q = db()->prepare('SELECT price FROM tariffs WHERE id=?');
        $q->execute([(int)$st['back_tariff']]);
        $price = (int)($q->fetchColumn() ?: 0);
    }
    if ($price) {
        $bal = get_balance($chatId);
        $deficit = max($price - $bal, 0);
        if ($deficit <= 0) $deficit = $price; // «or price» پایتون
        st_set($chatId, ['await' => 'card_wait', 'amount' => $deficit,
                         'buy_plan' => $bp, 'back_tariff' => $st['back_tariff'] ?? null]);
        wallet_card_sent($chatId);
        return;
    }
    start_topup($chatId);
}

/** Exact copy of on_wallet_card_sent() body (main.py 1217-1249). */
function wallet_card_sent(int $chatId): void {
    $amount = (int)st_get($chatId, 'amount', 0);
    $gw = (string)st_get($chatId, 'gw', 'card');
    $gwLabel = ['tron' => '💵 ترون', 'zarinpal' => '🟡 زرین پال', 'aqayepardakht' => '🔵 آقای پرداخت'][$gw] ?? null;
    if ($gwLabel) {
        $body = "برای پرداخت " . fmt_price($amount) . " از طریق {$gwLabel}:\n\n"
              . "💼 آدرس ولت:\n<code>" . htmlspecialchars((string)get_setting('wallet_address', '—')) . "</code>\n\n"
              . "پس از واریز، دکمه «✉️ ارسال کردم (ارسال رسید)» را بزن و هش تراکنش/عکس رسید را بفرست.";
    } else {
        $card = (string)get_setting('card_number', '—');
        $owner = (string)get_setting('card_owner', '—');
        $body = "💳 کارت به کارت:\n\n"
              . "💳 شماره کارت (کپی کن):\n<code>$card</code>\n"
              . "👤 به نام: " . htmlspecialchars($owner) . "\n\n"
              . "💰 مبلغ واریزی: <b>" . fmt_price($amount) . "</b>\n\n"
              . "مبلغ را دقیقاً همان عدد واریز کن. پس از واریز، دکمه زیر را بزن:";
    }
    // passive: bot ignores texts until «ارسال کردم» pressed (حفظ buy_plan/back_tariff مثل پایتون **st)
    st_set($chatId, ['await' => 'card_wait', 'amount' => $amount,
                     'buy_plan' => st_get($chatId, 'buy_plan'),
                     'back_tariff' => st_get($chatId, 'back_tariff')]);
    send_or_edit($chatId, $body, ['inline_keyboard' => [
        [['text' => '✉️ ارسال کردم (ارسال رسید)', 'callback_data' => 'wal:receipt']],
    ]]);
}

/** Exact copy of ui.wallet_kb() labels. */
function wallet_kb(): array {
    return ['inline_keyboard' => [
        [['text' => '➕ شارژ موجودی', 'callback_data' => 'wal:addcredit']],
        [['text' => '📜 رسیدهای من', 'callback_data' => 'wal:receipts']],
        [['text' => '🎁 کد هدیه دارم', 'callback_data' => 'wal:gift']],
        [['text' => '🏠 بازگشت به منوی اصلی', 'callback_data' => 'm:home']],
    ]];
}



