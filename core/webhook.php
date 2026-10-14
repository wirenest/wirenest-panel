<?php
/**
 * webhook.php — Telegram webhook entrypoint (shared hosting / no cron).
 * Set the webhook to: https://<domain>/core/webhook.php?key=<WEBHOOK_KEY>
 * WEBHOOK_KEY comes from .env; if missing, any key is rejected.
 */
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));
require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

$SECRET = $_ENV['WEBHOOK_KEY'] ?? (getenv('WEBHOOK_KEY') ?: '');
if ($SECRET === '' || ($_GET['key'] ?? '') !== $SECRET) { http_response_code(403); exit; }

$raw = file_get_contents('php://input');
$update = json_decode($raw, true);
if (!is_array($update)) { http_response_code(200); exit('ok'); }

try {
    handle_update($update);
} catch (Throwable $e) {
    bot_log('webhook update error: ' . $e->getMessage() . ' @ ' . $e->getFile() . ':' . $e->getLine());
}

// housekeeping piggyback (max 1/min)
$lastFile = BASE_DIR . '/data/.last_cron';
$now = time();
if (!file_exists($lastFile) || ($now - (int)file_get_contents($lastFile)) >= 60) {
    file_put_contents($lastFile, (string)$now);
    try { require BASE_DIR . '/core/cron.php'; } catch (Throwable $e) { bot_log('cron error: ' . $e->getMessage()); }
}

http_response_code(200);
echo 'ok';
