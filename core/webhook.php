<?php
/**
 * webhook.php – Telegram webhook entrypoint.
 */
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));

if (!function_exists('load_env')) {
    function load_env($path) {
        if (!file_exists($path)) return;
        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        foreach ($lines as $line) {
            $line = trim($line);
            if ($line === '' || strpos($line, '#') === 0) continue;
            if (strpos($line, '=') === false) continue;
            list($k, $v) = explode('=', $line, 2);
            $_ENV[trim($k)] = trim($v);
            putenv(trim($k) . '=' . trim($v));
        }
    }
}
load_env(BASE_DIR . '/.env');

require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

$expected_key = $_ENV['WEBHOOK_KEY'] ?? (getenv('WEBHOOK_KEY') ?: '');
$provided_key = $_GET['key'] ?? ($_SERVER['HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN'] ?? '');
if ($expected_key === '' || $provided_key !== $expected_key) {
    http_response_code(403);
    exit('Forbidden');
}

$raw = file_get_contents('php://input');
$update = json_decode($raw, true);
if (!is_array($update)) {
    http_response_code(200);
    exit('ok');
}

try {
    handle_update($update);
} catch (Throwable $e) {
    if (function_exists('bot_log')) {
        bot_log('webhook update error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
    }
}

$cron_file = BASE_DIR . '/data/.last_cron';
$now = time();
if (!file_exists($cron_file) || ($now - (int)@file_get_contents($cron_file)) >= 60) {
    @file_put_contents($cron_file, (string)$now);
    try {
        if (file_exists(BASE_DIR . '/core/cron.php')) {
            require BASE_DIR . '/core/cron.php';
        }
    } catch (Throwable $e) {
        if (function_exists('bot_log')) bot_log('cron error: ' . $e->getMessage());
    }
}

http_response_code(200);
echo 'ok';
