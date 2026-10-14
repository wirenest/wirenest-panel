<?php
/**
 * tick.php — single-poll entrypoint for shared-host cron (cPanel).
 * Cron: curl https://your-domain/marzbot/core/tick.php?key=SECRET
 * One getUpdates cycle (short poll) + cron housekeeping. Web-safe (no long loop).
 */
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));
require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

// minimal guard: secret key (matches cron URL)
$KEY = 'MrzTick2026x';
$given = $_GET['key'] ?? ($argv[1] ?? '');
if ($given !== $KEY) { http_response_code(403); exit('forbidden'); }

$stateFile = BASE_DIR . '/data/state.json';
$st = @json_decode((string)@file_get_contents($stateFile), true);
$offset = (int)($st['offset'] ?? 0);

// single short-poll getUpdates (timeout=2)
$ch = curl_init('https://api.telegram.org/bot' . BOT_TOKEN . '/getUpdates');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => json_encode([
        'offset' => $offset,
        'timeout' => 2,
        'allowed_updates' => ['message', 'callback_query'],
    ]),
    CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    CURLOPT_TIMEOUT => 15,
]);
$res = curl_exec($ch);
curl_close($ch);
$json = json_decode((string)$res, true);

if (empty($json['ok'])) {
    bot_log('tick getUpdates failed: ' . substr((string)$res, 0, 120));
    exit('poll-fail');
}

$n = 0;
foreach ($json['result'] ?? [] as $u) {
    $offset = $u['update_id'] + 1;
    $n++;
    try { handle_update($u); }
    catch (Throwable $e) { bot_log('update error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine()); }
}
file_put_contents($stateFile, json_encode(['offset' => $offset]));

// housekeeping once per tick (cron.php is idempotent)
try { require BASE_DIR . '/core/cron.php'; } catch (Throwable $e) { bot_log('cron error: ' . $e->getMessage()); }

bot_log('tick ok (updates=' . $n . ')');
echo 'ok:' . $n;
