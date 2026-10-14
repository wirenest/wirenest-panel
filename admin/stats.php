<?php
/**
 * admin/misc.php — آمار (کپی مو‌به‌موی build_full_stats main.py 1463-1546):
 * کاربران/خریدار/موجودی کل/فروش فعال/نرخ تبدیل/میانگین/ماهانه/تمدید/پنل‌ها/درگاه‌ها
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';

/** Exact copy of python build_full_stats() — Faoxima-style comprehensive stats. */
function build_full_stats(): string {
    $users = db()->query('SELECT COALESCE(balance,0) b FROM users')->fetchAll();
    $totalUsers = count($users);
    $totalBal = array_sum(array_map(fn($u) => (int)$u['b'], $users));

    $buys = db()->query('SELECT tg_id, price, status, tariff_id, panel_username, created_at FROM purchases')->fetchAll();
    $recs = db()->query("SELECT amount, status, ref_text FROM receipts WHERE status='approved'")->fetchAll();

    $totalSales = count($buys);
    $activeSales = 0; $sumSales = 0; $sumActive = 0;
    $buyersSet = [];
    foreach ($buys as $b) {
        if (($b['status'] ?? '') === 'active') $activeSales++;
        $sumSales += (int)($b['price'] ?? 0);
        if (($b['status'] ?? '') === 'active') $sumActive += (int)($b['price'] ?? 0);
        $buyersSet[(int)$b['tg_id']] = true;
    }
    $buyers = count($buyersSet);
    $conv = $totalUsers ? ($buyers / $totalUsers * 100) : 0.0;
    $avgBuy = $totalSales ? ($sumSales / $totalSales) : 0;

    // monthly revenue estimate: last 30 days (like-for-like local datetime strings)
    $since = date('Y-m-d H:i:s', strtotime('-30 days'));
    $mSales = 0;
    foreach ($buys as $b) {
        if ((string)($b['created_at'] ?? '') >= $since) $mSales += (int)($b['price'] ?? 0);
    }

    // renew share: same user + same tariff repeated
    $perUser = [];
    foreach ($buys as $b) {
        $k = $b['tg_id'] . ':' . $b['tariff_id'];
        $perUser[$k] = ($perUser[$k] ?? 0) + 1;
    }
    $renews = 0;
    foreach ($perUser as $v) if ($v > 1) $renews += $v - 1;
    $renewPct = $totalSales ? ($renews / $totalSales * 100) : 0.0;

    $panels = get_setting('panels', []) ?: [];

    // approved payments by gateway (ref_text prefix)
    $gwStat = [];
    foreach ($recs as $r) {
        $ref = (string)($r['ref_text'] ?? '');
        if (str_starts_with($ref, 'topup')) $gw = 'wallet';
        elseif (str_starts_with($ref, 'buy:')) $gw = 'buy';
        else $gw = 'other';
        $gwStat[$gw]['n'] = ($gwStat[$gw]['n'] ?? 0) + 1;
        $gwStat[$gw]['sum'] = ($gwStat[$gw]['sum'] ?? 0) + (int)($r['amount'] ?? 0);
    }
    $gwLabels = ['card' => '💳 کارت به کارت', 'wallet' => '🏦 شارژ کیف پول',
                 'buy' => '🛒 خرید مستقیم', 'other' => '📄 سایر'];
    $gwLines = [];
    foreach ($gwStat as $g => $stt) {
        $gwLines[] = "\n📌 نام درگاه : " . ($gwLabels[$g] ?? $g) . "\n"
            . " - تعداد پرداخت موفق : {$stt['n']}\n"
            . " - جمع پرداختی ها : " . number_format((float)$stt['sum']);
    }

    $L = [];
    $L[] = '📊 آمار کلی ربات';
    $L[] = '━━━━━━━━━━━━━━━━━━';
    $L[] = "👥 تعداد کل کاربران: {$totalUsers} نفر";
    $L[] = "💳 کاربران دارای خرید: {$buyers} نفر";
    $L[] = '💰 موجودی کل کاربران: ' . number_format((float)$totalBal) . ' تومان';
    $L[] = '';
    $L[] = "🧾 تعداد کل فروش: {$totalSales} عدد";
    $L[] = "🧾 تعداد کل فروش سرویس های فعال: {$activeSales} عدد";
    $L[] = '💵 جمع کل فروش : ' . number_format((float)$sumSales) . ' تومان';
    $L[] = '💵 جمع کل فروش سرویس های فعال: ' . number_format((float)$sumActive) . ' تومان';
    $L[] = '📈 نرخ تبدیل به مشتری: ' . number_format($conv, 2) . '٪';
    $L[] = '💳 میانگین خرید هر مشتری: ' . number_format($avgBuy, 0) . ' تومان';
    $L[] = '📅 درآمد پیش‌بینی‌شده ماهانه: ' . number_format((float)$mSales) . ' تومان';
    $L[] = '📊 درصد تمدید از فروش: ' . number_format($renewPct, 2) . '٪';
    $L[] = '';
    $L[] = '🧩 تعداد پنل‌ها: ' . count($panels) . ' عدد';
    if ($gwLines) {
        $L[] = '';
        foreach ($gwLines as $gl) $L[] = $gl;
    }
    return implode("\n", $L);
}

function admin_stats(int $chatId): void {
    // کپی adm:stats (main.py 1834-1845): تایم پینگ + متن کامل
    $t0 = microtime(true);
    try {
        $txt = build_full_stats();
    } catch (Throwable $e) {
        $txt = '⚠️ خطا در آمار: ' . mb_substr((string)$e->getMessage(), 0, 150);
    }
    $pingMs = (int)((microtime(true) - $t0) * 1000);
    $txt .= "\n📡 پینگ ربات: {$pingMs} میلی‌ثانیه";
    send_or_edit($chatId, $txt, ['inline_keyboard' => [
        [['text' => '◀️ بازگشت به پنل مدیریت', 'callback_data' => 'adm:back']],
    ]]);
}