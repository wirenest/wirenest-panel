<?php
/**
 * extra_gb.php — خرید حجم اضافه (کپی دقیق main.py 4119-4190).
 */
function handle_agent_gb(int $chatId, string $text): void {
    $st = st_all($chatId);
    st_pop($chatId);
    $pid = (int)($st['pid'] ?? 0);
    $xp = (int)($st['xp'] ?? 0);
    $xmin = (int)($st['xmin'] ?? 1);

    // Reza rule: گارد دوم — اگر سرویس هدف تست است، فلو را ببند
    $svc = db()->prepare('SELECT is_test FROM agent_panels WHERE id=? AND tg_id=?');
    $svc->execute([(int)($st['pid'] ?? 0), $chatId]);
    if ($svc && !empty($svc->fetchColumn())) {
        st_pop($chatId);
        send_or_edit($chatId, '⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.');
        return;
    }

    if (!preg_match('/(\d+)/', str_replace(',', '', $text), $m)) {
        send_or_edit($chatId, 'عدد معتبر بفرست.');
        return;
    }
    $gb = (int)$m[1];
    if ($gb < $xmin) {
        st_set($chatId, $st); // restore for retry (main.py keeps asking)
        send_or_edit($chatId, "⚖️ حداقل خرید حجم اضافه {$xmin} گیگ است. عدد بزرگ‌تری بفرست:");
        return;
    }
    $price = $gb * $xp;
    $bal = (int)get_balance($chatId);
    $deficit = max($price - $bal, 0);
    // Reza rule: قبل از پرداخت، فاکتور با موجودی/تفاضل + تایید/لغو نمایش داده می‌شود
    st_set($chatId, ['await' => 'idle', 'xp_kind' => 'extragb', 'xp_gb' => $gb,
                     'xp_price' => $price, 'xp' => $xp, 'pid' => $pid, 'xg_deficit' => $deficit]);
    $kb = ['inline_keyboard' => [
        [['text' => '✅ تایید فاکتور', 'callback_data' => "xgpay:$pid:$gb:$price"]],
        [['text' => '❌ لغو فاکتور', 'callback_data' => 'xgcancel']],
    ]];
    send_or_edit($chatId,
        "🧾 <b>فاکتور حجم اضافه</b>

"
        . "📦 حجم درخواستی: {$gb} گیگ
"
        . '💰 مبلغ فاکتور: ' . number_format($price) . " تومان
"
        . '💵 موجودی کیف پول: ' . fmt_price($bal) . "
"
        . ($deficit > 0
            ? '💳 قابل پرداخت (تفاضل): ' . fmt_price($deficit)
            : '✅ پوشش کامل از موجودی کیف پول'),
        $kb);
}

/** ✅ تایید فاکتور حجم اضافه → تفاضل = کارت به کارت | بدون تفاضل = کسر از کیف پول. */
function extra_gb_invoice_confirm(int $chatId, int $pid, int $gb, int $price): void {
    $st = st_all($chatId);
    if ((string)($st['xp_kind'] ?? '') !== 'extragb' || (int)($st['xp_gb'] ?? 0) !== $gb || (int)($st['xp_price'] ?? 0) !== $price) {
        send_or_edit($chatId, '⌛️ فاکتور منقضی شد — دوباره از صفحهٔ سرویس شروع کن.');
        return;
    }
    $bal = (int)get_balance($chatId);
    $deficit = max($price - $bal, 0);
    st_set($chatId, ['await' => 'wallet_card', 'amount' => $deficit]);
    if ($deficit > 0) {
        wallet_card_sent($chatId); // کارت به کارت با مبلغ تفاضلی
    } else {
        if (!spend_balance($chatId, $price)) {
            send_or_edit($chatId, '❌ خطا در کسر موجودی.');
            return;
        }
        complete_extra_gb($chatId, $gb, $pid, (int)($st['xp'] ?? 0), $price);
    }
}

/** ❌ لغو فاکتور حجم اضافه. */
function extra_gb_invoice_cancel(int $chatId): void {
    st_pop($chatId);
    send_or_edit($chatId, '❌ فاکتور لغو شد.', main_menu_kb(is_admin($chatId)));
}

/** پس از تایید رسید/شارژ، تکمیل خرید حجم اضافه (استخراج‌شده از handle_agent_gb). */
function complete_extra_gb(int $chatId, int $gb, int $pid, int $xp, int $price): void {
    $q = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $q->execute([$pid, $chatId]);
    $s = $q->fetch();
    if (!$s) {
        add_balance($chatId, $price); // refund
        send_or_edit($chatId, 'پنل یافت نشد.');
        return;
    }
    // Reza rule: اکانت تست حجم اضافه ندارد
    if (!empty($s['is_test'])) {
        add_balance($chatId, $price); // refund
        send_or_edit($chatId, '⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.');
        return;
    }
    $p = panel_client($s['panel_name'], $s['panel_type'] ?: null);
    $curLimit = 0;
    if ($p) {
        // پایتون cur_limit را از list_admins می‌گیرد (main.py 4151-4157)
        $res = panel_bridge_call($p, 'list_admins', []);
        foreach ((array)($res['data'] ?? []) as $a) {
            if (($a['username'] ?? '') === $s['panel_username']) {
                $curLimit = (int)($a['data_limit'] ?? 0);
                break;
            }
        }
    }
    $newLimit = $curLimit + $gb * (1024 ** 3);
    $panelOk = false;
    if ($p) {
        $res2 = panel_bridge_call($p, 'modify_admin_data_limit', [
            'username' => $s['panel_username'],
            'data_limit' => $newLimit,
        ]);
        $panelOk = !empty($res2['ok']);
    }
    if (!$panelOk) {
        add_balance($chatId, $price); // refund (main.py 4172)
        send_or_edit($chatId, '❌ افزایش سهمیه روی پنل ناموفق بود. مبلغ برگشت خورد.');
        return;
    }
    db()->prepare('UPDATE agent_panels SET quota_gb = quota_gb + ? WHERE id=?')->execute([$gb, $pid]);
    // user topped up volume -> allow the next threshold warning cycle again (main.py 4179-4185)
    $wmap = (array)(get_setting('quota_warned', []) ?: []);
    if (!empty($wmap[(string)$pid])) {
        unset($wmap[(string)$pid]);
        set_setting('quota_warned', $wmap);
    }
    report_purchase($chatId, (string)$s['panel_username'], "{$gb} گیگ حجم اضافه", $price, 'افزایش', panel_login_url((string)$s['panel_name']));

    send_or_edit($chatId,
        "✅ {$gb} گیگ به سرویس اضافه شد!\n"
        . '📦 سهمیه جدید: ' . round($newLimit / (1024 ** 3)) . " گیگ\n"
        . '💵 کسر شده: ' . number_format($price) . ' تومان — موجودی جدید: ' . fmt_price(get_balance($chatId)),
        main_menu_kb(is_admin($chatId)));
}
