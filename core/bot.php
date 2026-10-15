<?php
/**
 * WireNest PHP — Telegram Sales Bot (migration from Python PTB 21.10)
 * Same structure & features as the Python original.
 * Architecture: long-polling daemon (PHP CLI) + SQLite + PasarGuard API via cURL.
 *
 * Files:
 *   bot.php          — bootstrap, .env, PDO init, helper functions (this file)
 *   handlers.php     — update router: messages, callbacks, states
 *   menus.php        — main menu, admin kb, service screens (same layout as ui.py)
 *   flows.php        — buy / wallet / receipts / tickets / broadcast flows
 *   panel_api.php    — PasarGuard panel API client (login, roles, create admin, ping)
 *   cron.php         — test-expiry + quota warning sweep (called every minute)
 */

declare(strict_types=1);
date_default_timezone_set('Asia/Tehran'); // ساعت رسمی ربات: تهران (فرمان رضا)

mb_internal_encoding('UTF-8');

// ---------- .env ----------
$_ENV = [];
$envFile = BASE_DIR . '/.env';
if (file_exists($envFile)) {
    foreach (file($envFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        [$k, $v] = array_pad(explode('=', $line, 2), 2, '');
        $_ENV[trim($k)] = trim(trim($v), "\"'"); // strip quotes
    }
}

if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__)); // project root (wirenest-php/)
define('BOT_TOKEN', $_ENV['BOT_TOKEN'] ?? '');
define('DB_PATH', $_ENV['DB_PATH'] ?? (BASE_DIR . '/data/bot.sqlite'));
define('LOG_FILE', BASE_DIR . '/logs/bot.log');

if (!BOT_TOKEN) { fwrite(STDERR, "BOT_TOKEN missing\n"); exit(1); }

// ---------- DB (SQLite, same schema as Python bot) ----------
$db = new PDO('sqlite:' . DB_PATH);
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$db->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
$db->exec('PRAGMA journal_mode=WAL');
$db->exec('PRAGMA busy_timeout=30000');

function db(): PDO { global $db; return $db; }

/** Init schema (idempotent) - REAL schema, mirrors the migrated python DB exactly.
 *  Fresh installs get every table the code needs; existing DBs untouched (IF NOT EXISTS). */
function db_init(): void {
    db()->exec("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)");
    db()->exec("CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER NOT NULL DEFAULT 0,
        is_banned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        ref_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        tariff_id INTEGER,
        panel_username TEXT,
        months INTEGER,
        volume_gb REAL,
        price INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS agent_panels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        panel_username TEXT NOT NULL,
        panel_password TEXT NOT NULL,
        panel_name TEXT,
        panel_type TEXT,
        quota_gb REAL NOT NULL,
        expires_at TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        is_test INTEGER NOT NULL DEFAULT 0)");
    db()->exec("CREATE TABLE IF NOT EXISTS tariffs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        months INTEGER NOT NULL,
        volume_gb REAL NOT NULL,
        price INTEGER NOT NULL,
        user_limit INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        sort INTEGER NOT NULL DEFAULT 0)");
    db()->exec("CREATE TABLE IF NOT EXISTS panel_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        panel_name TEXT NOT NULL,
        volume_gb REAL NOT NULL,
        price INTEGER NOT NULL,
        active INTEGER DEFAULT 1)");
    db()->exec("CREATE TABLE IF NOT EXISTS gift_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        amount INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 0,
        used INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1)");
    db()->exec("CREATE TABLE IF NOT EXISTS gift_redemptions (
        gift_id INTEGER NOT NULL,
        tg_id INTEGER NOT NULL,
        redeemed_at TEXT DEFAULT (datetime('now','localtime')),
        PRIMARY KEY (gift_id, tg_id))");
    db()->exec("CREATE TABLE IF NOT EXISTS discount_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL DEFAULT 'percent',
        value INTEGER NOT NULL,
        max_uses INTEGER DEFAULT 0,
        used INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        expires_at TEXT)");
    db()->exec("CREATE TABLE IF NOT EXISTS channels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id TEXT NOT NULL,
        title TEXT)");
    db()->exec("CREATE TABLE IF NOT EXISTS agent_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        message TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS help_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now','localtime')))");
    db()->exec("CREATE TABLE IF NOT EXISTS guide_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        sort INTEGER DEFAULT 0)");
    db()->exec("CREATE TABLE IF NOT EXISTS manual_panels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        url TEXT DEFAULT '',
        username TEXT DEFAULT '',
        password TEXT DEFAULT '',
        status TEXT DEFAULT 'available',
        buyer_id INTEGER)");

    // Seed default texts if empty (Reza: متون پیش‌فرض)
    require_once __DIR__ . '/../lib/defaults.php';
    $cnt = db()->query("SELECT COUNT(*) FROM guide_topics")->fetchColumn();
    if ($cnt == 0 && function_exists('default_guide_topics')) {
        foreach (default_guide_topics() as $gt) {
            db()->prepare("INSERT INTO guide_topics(title, content) VALUES(?,?)")->execute([$gt['title'], $gt['content']]);
        }
    }
    if (get_setting('faq_text', '') === '' && function_exists('default_faq_text')) {
        set_setting('faq_text', default_faq_text());
    }

        db()->exec("CREATE TABLE IF NOT EXISTS pending_buys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'plan',
        pid INTEGER,
        pname TEXT,
        gb REAL,
        price INTEGER NOT NULL,
        discount_json TEXT,
        created_at TEXT DEFAULT (datetime('now','localtime')))");
}

// ---------- settings helpers (mirror db.py) ----------
/** همه تنظیمات */
function all_settings(): array {
    $rows = db()->query('SELECT key, value FROM settings')->fetchAll();
    $out = [];
    foreach ($rows as $r) {
        $v = json_decode((string)$r['value'], true);
        $out[$r['key']] = ($v === null && (string)$r['value'] !== 'null' && (string)$r['value'] !== '') ? $r['value'] : $v;
    }
    return $out;
}

function bot_enabled(): bool {
    return (bool)get_setting('bot_enabled', 1);
}

function get_setting(string $key, $default = null) {
    $st = db()->prepare('SELECT value FROM settings WHERE key=?');
    $st->execute([$key]);
    $row = $st->fetch();
    if ($row === false) return $default;
    $v = json_decode($row['value'], true);
    return $v === null && $row['value'] !== 'null' ? $row['value'] : $v;
}

function set_setting(string $key, $value): void {
    $st = db()->prepare("INSERT INTO settings(key,value) VALUES(?,?)
                          ON CONFLICT(key) DO UPDATE SET value=excluded.value");
    $st->execute([$key, json_encode($value, JSON_UNESCAPED_UNICODE)]);
}

/** Sync admin ids + INITIAL_ADMIN bootstrap (paritätisch mit main.py admin_ids()). */
function admin_ids(): array {
    $ids = get_setting('admin_ids', []) ?: [];
    // .env loader fills $_ENV (host CGI has no real env); getenv kept for systemd deploys
    $env = (isset($_ENV['INITIAL_ADMIN_ID']) && $_ENV['INITIAL_ADMIN_ID'] !== '') ? $_ENV['INITIAL_ADMIN_ID'] : (getenv('INITIAL_ADMIN_ID') ?: '');
    if ($env !== '' && !$ids) {
        $ids = [(int)$env];
        set_setting('admin_ids', $ids);
    }
    return $ids;
}
function is_admin(int $tg): bool { return in_array($tg, admin_ids(), true); }

// ---------- Telegram API ----------
function tg(string $method, array $data = []): array {
    $ch = curl_init("https://api.telegram.org/bot" . BOT_TOKEN . "/$method");
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($data, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_TIMEOUT => 35,
    ]);
    $res = curl_exec($ch);
    $err = curl_error($ch);
    curl_close($ch);
    if ($res === false) { bot_log("TG curl error: $err"); return ['ok' => false]; }
    $json = json_decode($res, true) ?: ['ok' => false];
    // anti-flood: honor RetryAfter (parity with python anti-flood batch logic)
    if (empty($json['ok']) && isset($json['parameters']['retry_after'])) {
        sleep((int)$json['parameters']['retry_after'] + 1);
        return tg($method, $data); // retry once after waiting
    }
    return $json;
}

function tg_send(int|string $chat, string $text, ?array $kb = null, array $extra = []): array {
    return tg('sendMessage', array_merge([
        'chat_id' => $chat,
        'text' => $text,
        'parse_mode' => 'HTML',
    ], $kb ? ['reply_markup' => json_encode($kb, JSON_UNESCAPED_UNICODE)] : [], $extra));
}

// ---------- helpers ----------
function fmt_price(int|float $p): string { return number_format((float)$p) . ' تومان'; }

function bot_log(string $msg): void {
    @file_put_contents(LOG_FILE, '[' . date('Y-m-d H:i:s') . "] $msg\n", FILE_APPEND);
}

/** Persian (Jalali) date — jdatetime parity. Uses jdate algorithm without ext. */
function jdate(?string $ts = null): string {
    $ts = $ts ?: date('Y-m-d H:i:s');
    $t = strtotime($ts);
    if ($t === false) return $ts;
    // Gregorian -> Jalali (standard algorithm)
    $gy = (int)date('Y', $t); $gm = (int)date('n', $t); $gd = (int)date('j', $t);
    $g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    $jy = ($gy <= 1600) ? 0 : 979;
    $gy -= ($gy <= 1600) ? 621 : 1600;
    $gy2 = ($gm > 2) ? $gy + 1 : $gy;
    $days = (365 * $gy) + ((int)(($gy2 + 3) / 4)) - ((int)(($gy2 + 99) / 100))
          + ((int)(($gy2 + 399) / 400)) - 80 + $gd + $g_d_m[$gm - 1];
    $jy += 33 * ((int)($days / 12053));
    $days %= 12053;
    $jy += 4 * ((int)($days / 1461));
    $days %= 1461;
    if ($days > 365) { $jy += (int)(($days - 1) / 365); $days = ($days - 1) % 365; }
    $jm = ($days < 186) ? 1 + (int)($days / 31) : 7 + (int)(($days - 186) / 30);
    $jd = 1 + (($days < 186) ? ($days % 31) : (($days - 186) % 30));
    return sprintf('%04d/%02d/%02d %02d:%02d', $jy, $jm, $jd, (int)date('H', $t), (int)date('i', $t));
}

/** Mask middle of a string with **** (report channel parity: first4+****+last2). */
function mask_mid(string $s): string {
    $l = mb_strlen($s);
    if ($l <= 6) return $s;
    return mb_substr($s, 0, 4) . '****' . mb_substr($s, -2);
}

db_init();
bot_log('=== PHP bot core loaded ===');

require_once BASE_DIR . '/core/edit_menu.php';

/** حجم خوانا: 100.0 → «100»، 0.5 → «0.5» (رشتهٔ «100» را خراب نمی‌کند). */
function fmt_gb($v): string {
    $f = (float)$v;
    return (floor($f) == $f) ? (string)(int)$f : rtrim(rtrim(number_format($f, 2, '.', ''), '0'), '.');
}