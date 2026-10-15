<?php
/**
 * daemon.php — long-polling loop (replaces python app.run_polling)
 * Usage: php daemon.php   (systemd service wirenest-php)
 */

if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__)); // project root (wirenest-php/)
require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

bot_log('daemon started (getUpdates loop)');

$offset = 0;
$lastCron = 0;

$ticks = 0;
while (true) {
    if (++$ticks % 100 === 0) {
        gc_collect_cycles();
        if (memory_get_usage(true) > 128 * 1024 * 1024) {
            bot_log('Memory limit exceeded (>128MB), exiting for clean systemd restart.');
            exit(0);
        }
    }
    // ---- cron tick every 60s (test expiry + quota warnings) ----
    if (time() - $lastCron >= 60) {
        $lastCron = time();
        try { require BASE_DIR . '/core/cron.php'; } catch (Throwable $e) { bot_log('cron error: ' . $e->getMessage()); }
    }

    // ---- getUpdates long poll ----
    $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/getUpdates');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode([
            'offset' => $offset,
            'timeout' => 25,
            'allowed_updates' => ['message', 'callback_query'],
        ]),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_TIMEOUT => 30,
    ]);
    $res = curl_exec($ch);
    curl_close($ch);
    $json = json_decode((string)$res, true);

    if (empty($json['ok'])) {
        bot_log('getUpdates failed: ' . substr((string)$res, 0, 120));
        sleep(3);
        continue;
    }

    foreach ($json['result'] ?? [] as $u) {
        $offset = $u['update_id'] + 1;
        try {
            handle_update($u);
        } catch (Throwable $e) {
            bot_log('update error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
        }
    }
}