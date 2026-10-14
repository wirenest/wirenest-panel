<?php
/**
 * worker.php — bounded polling loop for shared-host cron (cPanel).
 * Runs for ~50 seconds then exits (cron every minute, no overlap).
 */
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));
require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

$lockFile = BASE_DIR . '/data/worker.lock';
$fp = fopen($lockFile, 'c');
if (!flock($fp, LOCK_EX | LOCK_NB)) { exit(0); } // another worker running — exit silently

bot_log('worker tick started');

$start = time();
$offset = 0;
$lastCron = 0;
$gotAny = 0;

// restore offset from state file
$stateFile = BASE_DIR . '/data/state.json';
if (file_exists($stateFile)) {
    $st = @json_decode((string)file_get_contents($stateFile), true);
    $offset = (int)($st['offset'] ?? 0);
}

while (time() - $start < 50) {
    if (time() - $lastCron >= 60) {
        $lastCron = time();
        try { require BASE_DIR . '/core/cron.php'; } catch (Throwable $e) { bot_log('cron error: ' . $e->getMessage()); }
    }

    $ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/getUpdates');
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode([
            'offset' => $offset,
            'timeout' => 10,
            'allowed_updates' => ['message', 'callback_query'],
        ]),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_TIMEOUT => 15,
    ]);
    $res = curl_exec($ch);
    $curlErr = curl_error($ch);
    curl_close($ch);
    $json = json_decode((string)$res, true);

    if (empty($json['ok'])) {
        if ($curlErr) bot_log('getUpdates curl error: ' . $curlErr);
        else bot_log('getUpdates failed: ' . substr((string)$res, 0, 120));
        sleep(2);
        continue;
    }

    foreach ($json['result'] ?? [] as $u) {
        $offset = $u['update_id'] + 1;
        $gotAny++;
        try {
            handle_update($u);
        } catch (Throwable $e) {
            bot_log('update error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
        }
    }
}

// persist offset
file_put_contents($stateFile, json_encode(['offset' => $offset]));
bot_log('worker tick done (updates=' . $gotAny . ')');
flock($fp, LOCK_UN);
fclose($fp);
