<?php
/**
 * webhook.php – Telegram webhook entrypoint.
 */
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));

// Load DotEnv manually or use environment
if (!function_exists('load_env')) {
    function load_env() {
        if (!file_exists()) return;
         = file(, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
        foreach ( as ) {
            if (strpos(trim(), '#') === 0) continue;
            if (strpos(, '=') === false) continue;
            list(, ) = explode('=', , 2);
            [trim()] = trim();
            putenv(trim() . "=" . trim());
        }
    }
}
load_env(BASE_DIR . '/.env');

require_once BASE_DIR . '/core/handlers.php';
require_once BASE_DIR . '/admin/callbacks.php';

 = ['WEBHOOK_KEY'] ?? (getenv('WEBHOOK_KEY') ?: '');
if ( === '' || (['key'] ?? '') !== ) { 
    http_response_code(403); 
    exit('Forbidden'); 
}

 = file_get_contents('php://input');
 = json_decode(, true);
if (!is_array()) { 
    http_response_code(200); 
    exit('ok'); 
}

try {
    handle_update();
} catch (Throwable ) {
    if (function_exists('bot_log')) {
        bot_log('webhook update error: ' . ->getMessage() . ' @ ' . ->getFile() . ':' . ->getLine());
    }
}

// housekeeping piggyback (max 1/min)
 = BASE_DIR . '/data/.last_cron';
 = time();
if (!file_exists() || ( - (int)@file_get_contents()) >= 60) {
    @file_put_contents(, (string));
    try { 
        if (file_exists(BASE_DIR . '/core/cron.php')) {
            require BASE_DIR . '/core/cron.php'; 
        }
    } catch (Throwable ) { 
        if (function_exists('bot_log')) bot_log('cron error: ' . ->getMessage()); 
    }
}

http_response_code(200);
echo 'ok';
