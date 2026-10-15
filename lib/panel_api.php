<?php
/**
 * panel_api.php — Panel bridge + encryption + API clients.
 * Upgraded to AES-256-GCM authenticated encryption (phpenc2:) while preserving phpenc: (CBC) decryption.
 */

if (!function_exists("panel_clean_base_url")) {
function panel_clean_base_url(string $url): string {
    foreach (['/dashboard', '/dashboard/'] as $frag) {
        if (str_ends_with($url, $frag)) $url = substr($url, 0, -strlen($frag));
    }
    $url = rtrim($url, '/');
    if (!preg_match('#^https?://#', $url)) $url = 'https://' . $url;
    return $url;
}
}

if (!function_exists("panel_login_url")) {
function panel_login_url(string $storedBase): string {
    // parity with python (main.py 901/1033/3050): web login = base_url + /dashboard
    return rtrim($storedBase, '/') . '/dashboard'; // نمایش = عین مقدار ذخیره‌شده (قانون رضا)
}
}

if (!function_exists("panel_client")) {
function panel_client(?string $baseUrl = null, ?string $ptype = null): ?array {
    $panels = get_setting('panels', []) ?: [];
    if (!is_array($panels) || empty($panels)) return null;
    if ($baseUrl !== null) {
        $data = null;
        foreach ($panels as $pn => $d) {
            if (($d['base_url'] ?? '') === $baseUrl || $pn === $baseUrl) { $data = $d; break; }
        }
        if ($data === null) {
            // requested id/base_url not found: اولین پنل فعال (فرمان رضا: پنل پنله) — بدون لاگ اضافه
            foreach ($panels as $pd) {
                if (!empty($pd['active'])) { $data = $pd; break; }
            }
            if ($data === null) $data = reset($panels);
        }
        if ($ptype) $data['ptype'] = $ptype;
    } else {
        $sel = (string)get_setting('selected_panel', '');
        if ($sel !== '' && isset($panels[$sel])) {
            $data = $panels[$sel];
        } else {
            // پنل «پیش‌فرض» مفهومی ندارد (فرمان رضا) — اولین پنل «فعال» ملاک است
            $data = null;
            foreach ($panels as $pd) {
                if (!empty($pd['active'])) { $data = $pd; break; }
            }
            if ($data === null) $data = reset($panels);
        }
    }
    $data['password'] = panel_decrypt_pw($data['password'] ?? '');
    $data['base_url'] = rtrim((string)$data['base_url'], '/');
    return $data;
}
}

if (!function_exists("panel_crypto_key")) {
function panel_crypto_key(): string {
    $envKey = $_ENV['PANEL_CRYPTO_KEY'] ?? '';
    if ($envKey) return $envKey;
    $kf = BASE_DIR . '/data/crypto.key';
    if (file_exists($kf)) return trim(file_get_contents($kf));
    $key = base64_encode(random_bytes(32));
    @file_put_contents($kf, $key);
    return $key;
}
}

if (!function_exists("panel_decrypt_pw")) {
function panel_decrypt_pw(string $enc): string {
    if (!$enc) return '';
    $key = base64_decode(panel_crypto_key());
    if (str_starts_with($enc, 'phpenc2:')) {
        $raw = base64_decode(substr($enc, 8));
        if (strlen($raw) < 28) return '';
        $iv = substr($raw, 0, 12);
        $tag = substr($raw, 12, 16);
        $ct = substr($raw, 28);
        $dec = openssl_decrypt($ct, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
        return $dec !== false ? $dec : '';
    }
    if (str_starts_with($enc, 'phpenc:')) {
        $raw = base64_decode(substr($enc, 7));
        if (strlen($raw) < 16) return '';
        $iv = substr($raw, 0, 16);
        $ct = substr($raw, 16);
        $dec = openssl_decrypt($ct, 'aes-256-cbc', $key, OPENSSL_RAW_DATA, $iv);
        return $dec !== false ? $dec : '';
    }
    if (str_starts_with($enc, 'pyfer:')) {
        return substr($enc, 6);
    }
    // raw python Fernet token (no prefix, starts with gAAAA) — decrypt via python bridge fallback
    if (str_starts_with($enc, 'gAAAA')) {
        $py = $_ENV['PANEL_PY'] ?? '';
        if (!$py || !file_exists($py)) { foreach ([BASE_DIR . '/venv/bin/python', '/usr/bin/python3', '/usr/local/bin/python3'] as $c) if (file_exists($c)) { $py = $c; break; } }
        if ($py && file_exists($py)) {
            $tok = escapeshellarg($enc);
            $out = shell_exec("$py " . escapeshellarg(BASE_DIR . '/lib/fernet_decrypt.py') . " $tok 2>/dev/null");
            if (is_string($out) && trim($out) !== '' && !str_starts_with(trim($out), 'gAAAA')) return trim($out);
        }
        return '';
    }
    return $enc;
}
}

if (!function_exists("panel_encrypt_pw")) {
function panel_encrypt_pw(string $plain): string {
    if (!$plain) return '';
    $key = base64_decode(panel_crypto_key());
    $iv = random_bytes(12);
    $tag = '';
    $ct = openssl_encrypt($plain, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv, $tag);
    return 'phpenc2:' . base64_encode($iv . $tag . $ct);
}
}

if (!function_exists("panel_bridge_call")) {
require_once __DIR__ . "/panel_http.php";
function panel_bridge_call(array $panel, string $action, array $args = []): ?array {
    $res = panel_http_call($panel, $action, $args);
    if ($res && !empty($res["ok"])) return $res;

    $bridgeScript = BASE_DIR . '/lib/panel_bridge.py';
    // portable python lookup: env PY → known venvs → system python3
    $py = $_ENV['PANEL_PY'] ?? getenv('PANEL_PY') ?: '';
    if (!$py || !file_exists($py)) {
        foreach (['/root/marzban-bot/venv/bin/python', BASE_DIR . '/venv/bin/python'] as $cand) {
            if (@file_exists($cand)) { $py = $cand; break; }
        }
    }
    if (!$py || !file_exists($py)) $py = 'python3';

    // مسیر هاست (proc_open disabled): relay روی سرور اصلی (curl_cffi CF bypass)
    $relayUrl = $_ENV['PANEL_RELAY_URL'] ?? getenv('PANEL_RELAY_URL') ?: '';
    $relayKey = $_ENV['PANEL_RELAY_KEY'] ?? getenv('PANEL_RELAY_KEY') ?: '';
    if ($relayUrl !== '' && $relayKey !== '') {
        $ch2 = curl_init(rtrim($relayUrl, '/') . '/relay');
        curl_setopt_array($ch2, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST => true,
            CURLOPT_TIMEOUT => 45,
            CURLOPT_SSL_VERIFYPEER => false,
            CURLOPT_SSL_VERIFYHOST => 0,
            CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
            CURLOPT_POSTFIELDS => json_encode([
                'key' => $relayKey,
                'base_url' => $panel['base_url'] ?? '',
                'username' => $panel['username'] ?? '',
                'password' => panel_decrypt_pw($panel['password'] ?? ''),
                'ptype' => $panel['ptype'] ?? 'pasarguard',
                'action' => $action,
                'args' => array_merge($args, ['role_id' => $args['role_id'] ?? ($panel['role_id'] ?? 3)]),
            ], JSON_UNESCAPED_UNICODE),
        ]);
        $raw = curl_exec($ch2);
        $cerr = curl_error($ch2);
        curl_close($ch2);
        if ($raw !== false) {
            $jr = json_decode((string)$raw, true);
            if (is_array($jr)) return $jr;
        }
        bot_log("panel relay error action=$action: $cerr " . substr((string)$raw, 0, 120));
        // fall through to bridge attempt
    }
    if (!function_exists('proc_open')) {
        bot_log('panel bridge unavailable (proc_open disabled) action=' . $action);
        return ['ok' => false, 'error' => 'bridge unavailable', 'msg' => 'پل پنل در دسترس نیست'];
    }
    $payload = json_encode([
        'base_url' => $panel['base_url'] ?? '',
        'username' => $panel['username'] ?? '',
        'password' => $panel['password'] ?? '',
        'ptype' => $panel['ptype'] ?? 'marzban',
        'action' => $action,
        'args' => $args
    ], JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);

    $descriptors = [
        0 => ['pipe', 'r'],
        1 => ['pipe', 'w'],
        2 => ['pipe', 'w']
    ];
    $process = proc_open("$py $bridgeScript", $descriptors, $pipes);
    if (!is_resource($process)) return null;

    fwrite($pipes[0], $payload);
    fclose($pipes[0]);

    $stdout = stream_get_contents($pipes[1]);
    fclose($pipes[1]);
    $stderr = stream_get_contents($pipes[2]);
    fclose($pipes[2]);
    proc_close($process);

    if (!trim($stdout)) {
        bot_log("panel_bridge_call empty stdout for action=$action, stderr=$stderr");
        return null;
    }
    $res = json_decode(trim($stdout), true);
    if (!$res) {
        bot_log("panel_bridge_call json decode error: $stdout");
        return null;
    }
    return $res;
}
}

if (!function_exists("panel_ping")) {
function panel_ping(array $panel): array {
    $res = panel_bridge_call($panel, 'ping', []);
    if (!$res) return ['ok' => false, 'msg' => 'Bridge error'];
    return $res;
}
}
/** panel_create_admin — bridge create_admin (main.py 3991: create_admin(uname, pwd, volume_gb, telegram_id)). */
function panel_create_admin(array $p, string $uname, string $pwd, float $volGb, int $tgId): array {
    $res = panel_bridge_call($p, 'create_admin', [
        'username'    => $uname,
        'password'    => $pwd,
        'volume_gb'   => $volGb,
        'telegram_id' => $tgId,
    ]);
    if (!is_array($res)) return ['ok' => false, 'error' => 'bridge no response'];
    return $res;
}