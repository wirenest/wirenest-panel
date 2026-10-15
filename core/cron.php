<?php
/**
 * cron.php — کپی مو‌به‌موی پایتون:
 * cron_check_agents (main.py 4475-4567): هشدار یک‌بار در آستانه + کد تخفیف شخصی ۲۴ ساعته + حذف خودکار exhausted
 * cron expire tests (main.py 4410-4440): حذف پنل تست + پیام ⌛️
 * expire_stale_pending_buys(24) (main.py 4390).
 */

// ---- 0) expire stale pending_buys (main.py 4390) ----
db()->exec("DELETE FROM pending_buys WHERE created_at <= datetime('now', '-24 hours')");

// ---- 1) test expiry sweep (main.py 4408-4441 parity — DB-based) ----
$expiredTests = db()->query("SELECT * FROM agent_panels WHERE is_test=1 AND status='active'
                             AND expires_at IS NOT NULL AND expires_at <= datetime('now')")->fetchAll();
$panelsCfg = (array)(get_setting('panels', []) ?: []);
foreach ($expiredTests as $rec) {
    foreach ($panelsCfg as $pc) {
        if (($pc['base_url'] ?? '') === ($rec['panel_name'] ?? '')) {
            $p = panel_client((string)$rec['panel_name'], (string)($rec['panel_type'] ?: 'pasarguard'));
            if ($p) panel_bridge_call($p, 'delete_admin', ['username' => (string)$rec['panel_username']]); // پایتون: try/except pass
            break;
        }
    }
    db()->prepare("UPDATE agent_panels SET status='expired' WHERE id=?")->execute([(int)$rec['id']]);
    tg_send((int)$rec['tg_id'],
        '⌛️ سرویس تست «' . $rec['panel_username'] . '» منقضی شد (' . substr((string)$rec['expires_at'], 0, 10) . ").
"
        . 'برای ادامه می‌تونی سرویس اصلی رو از «🔐 خرید اشتراک» بگیری.');
    bot_log('test expired -> uid=' . $rec['tg_id'] . ' user=' . $rec['panel_username']);
}

// ---- 2) cron_check_agents — quota warn once + personal discount + auto-remove (main.py 4475-4567) ----
$warnPct = (int)(get_setting('quota_warn_pct', 80) ?: 80);
$warnDisc = (int)(get_setting('quota_warn_discount_pct', 10) ?: 10);
$warnTpl = (string)(get_setting('quota_warn_text', '') ?: (
    "سلام {name} عزیز 👋\n\n"
    . "⚠️ شما {pct}٪ از سرویس `{user}` رو مصرف کردی.\n"
    . "🎁 یه کد تخفیف {disc}٪ اختصاصی برات ساختم — تا ۲۴ ساعت مهلت داری:\n"
    . 'برای افزایش حجم با تخفیف، کد تخفیف: <code>{code}</code>'));
$removeTpl = (string)(get_setting('autoremove_text', '') ?: (
    "🗑 سهمیه پنل {user} تمام شد و پنل به‌صورت خودکار حذف شد.\n"
    . 'برای ادامه، حجم اضافه خریداری کن.'));
$warnedMap = (array)(get_setting('quota_warned', []) ?: []);

$st = db()->query("SELECT id, tg_id, panel_username, panel_name, panel_type, quota_gb, status
                   FROM agent_panels WHERE status='active' AND is_test=0 LIMIT 300");
foreach ($st->fetchAll() as $ap) {
    if (isset($warnedMap[(string)$ap['id']]) && $warnedMap[(string)$ap['id']]) continue; // already warned

    $p = panel_client($ap['panel_name'], $ap['panel_type'] ?: null);
    if (!$p) continue;

    $res = panel_bridge_call($p, 'get_admin_info', ['username' => $ap['panel_username']]);
    if (!$res || empty($res['ok']) || empty($res['data'])) continue;
    $u = $res['data'];
    $used = (float)($u['used_traffic'] ?? 0);
    $total = (float)($u['usage_limit'] ?? 0);
    if ($total <= 0) continue;
    $pct = ($used / $total) * 100.0;

    if ($warnPct <= $pct && $pct < 100) {
        // warn exactly ONCE (main.py 4528-4553) + personal one-time discount 24h
        $code = 'WARN' . (((int)$ap['tg_id']) % 100000) . strtoupper(bin2hex(random_bytes(2)));
        db()->prepare("INSERT INTO discount_codes(code, kind, value, max_uses, used, active, expires_at)
                       VALUES(?, 'percent', ?, 1, 0, 1, datetime('now', '+24 hours'))")
           ->execute([$code, $warnDisc]);
        $name = '';
        $uq = db()->prepare('SELECT username FROM users WHERE tg_id=?');
        $uq->execute([(int)$ap['tg_id']]);
        $row = $uq->fetch();
        $name = $row['username'] ?: 'کاربر';
        $msg = str_replace(
            ['{name}', '{user}', '{pct}', '{disc}', '{code}'],
            [$name, (string)$ap['panel_username'], (string)(int)$pct, (string)$warnDisc, $code],
            $warnTpl);
        tg_send((int)$ap['tg_id'], $msg,
            ['inline_keyboard' => [[['text' => '➕ خرید حجم اضافه', 'callback_data' => 'apgb:' . $ap['id']]]]]);
        $warnedMap[(string)$ap['id']] = 1;
        set_setting('quota_warned', $warnedMap);
        bot_log("quota warn uid={$ap['tg_id']} pct=" . (int)$pct . " code=$code");
    } elseif ($pct >= 100) {
        // exhausted (main.py 4554-4564): notice + status + delete admin
        $msg = str_replace('{user}', (string)$ap['panel_username'], $removeTpl);
        tg_send((int)$ap['tg_id'], $msg);
        db()->prepare("UPDATE agent_panels SET status='exhausted' WHERE id=?")->execute([(int)$ap['id']]);
        panel_bridge_call($p, 'delete_admin', ['username' => $ap['panel_username']]);
        bot_log("panel exhausted uid={$ap['tg_id']} user={$ap['panel_username']}");
    }
}