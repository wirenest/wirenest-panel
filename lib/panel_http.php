<?php
/** lib/panel_http.php — Pure PHP cURL implementation of Panel API.
 *  Parity with panel.py and panel_bridge.py actions.
 *  Chrome UA required: WAF (Cloudflare) blocks libcurl default UA with 403.
 */
function panel_http_request(string $method, string $baseUrl, string $path, array $data = [], ?string $token = null) {
    $url = rtrim($baseUrl, '/') . $path;
    $ch = curl_init($url);
    $headers = [
        'Accept: application/json',
        'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ];
    if ($token) $headers[] = "Authorization: " . base64_decode('QmVhcmVyIA==') . $token;
    
    $opts = [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CUSTOMREQUEST => strtoupper($method),
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_TIMEOUT => 25,
        CURLOPT_SSL_VERIFYPEER => false,
    ];
    if ($method !== 'GET' && !empty($data)) {
        if (isset($data['__raw_body'])) {
             $opts[CURLOPT_POSTFIELDS] = $data['__raw_body'];
             $headers[] = 'Content-Type: application/json';
             $opts[CURLOPT_HTTPHEADER] = $headers;
        } else {
             $opts[CURLOPT_POSTFIELDS] = http_build_query($data);
             $headers[] = 'Content-Type: application/x-www-form-urlencoded';
             $opts[CURLOPT_HTTPHEADER] = $headers;
        }
    }
    curl_setopt_array($ch, $opts);
    $res = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return ['code' => $code, 'body' => $res, 'json' => @json_decode($res, true)];
}

function panel_http_auth(array $p): ?string {
    $ptype = $p['ptype'] ?? 'marzban';
    $paths = ($ptype === 'sanaei') ? ['/api/admin/token', '/api/admins/token', '/login'] : 
             (($ptype === 'pasarguard') ? ['/api/admin/token', '/api/admins/token', '/api/admins/login'] : 
             ['/api/admin/token', '/login']);

    foreach ($paths as $pth) {
        $r = panel_http_request('POST', $p['base_url'], $pth, ['username' => $p['username'], 'password' => $p['password']]);
        if ($r['code'] === 200 && !empty($r['json'])) {
            $j = $r['json'];
            return $j['access_token'] ?? $j['token'] ?? ($j['data']['token'] ?? null);
        }
    }
    return null;
}

function panel_http_call(array $p, string $action, array $args = []) {
    $token = panel_http_auth($p);
    if (!$token) return ['ok' => false, 'error' => 'auth failed'];

    switch ($action) {
        case 'ping':
            $r = panel_http_request('GET', $p['base_url'], '/api/admin/system', [], $token);
            if ($r['code'] === 200) return ['ok' => true, 'msg' => (($p['ptype'] ?? 'marzban') . ' OK ' . ($r['json']['version'] ?? ''))];
            return ['ok' => true, 'msg' => (($p['ptype'] ?? 'marzban') . ' auth-ok')];
        
        case 'list_roles':
            foreach (['/api/admin-roles/simple', '/api/admin-roles'] as $pth) {
                $r = panel_http_request('GET', $p['base_url'], $pth, [], $token);
                if ($r['code'] === 200 && !empty($r['json'])) {
                    $roles = $r['json']['roles'] ?? (is_array($r['json']) ? $r['json'] : []);
                    $out = [];
                    foreach ($roles as $x) if (isset($x['id'])) $out[] = ['id' => (int)$x['id'], 'name' => (string)($x['name'] ?? "role {$x['id']}"), 'is_owner' => !empty($x['is_owner'])];
                    return ['ok' => true, 'roles' => $out];
                }
            }
            return ['ok' => true, 'roles' => []];

        case 'list_admins':
            foreach (['/api/admins', '/api/admin/users'] as $pth) {
                $r = panel_http_request('GET', $p['base_url'], $pth, [], $token);
                if ($r['code'] === 200 && !empty($r['json'])) {
                    $j = $r['json'];
                    if (is_numeric(key($j))) return ['ok' => true, 'data' => $j];
                    foreach (['admins', 'items', 'data'] as $k) if (isset($j[$k])) return ['ok' => true, 'data' => $j[$k]];
                }
            }
            return ['ok' => true, 'data' => []];

        case 'delete_admin':
            $u = $args['username'] ?? '';
            foreach (["/api/admin/$u", "/api/admins/$u"] as $pth) {
                $r = panel_http_request('DELETE', $p['base_url'], $pth, [], $token);
                if ($r['code'] < 400) return ['ok' => true];
            }
            return ['ok' => false];

        case 'modify_admin_data_limit':
            $u = $args['username'] ?? '';
            $limit = (int)($args['data_limit'] ?? 0);
            foreach (["PUT:/api/admin/$u", "PATCH:/api/admin/$u", "PUT:/api/admins/$u"] as $mpath) {
                list($m, $pth) = explode(':', $mpath);
                $r = panel_http_request($m, $p['base_url'], $pth, ['__raw_body' => json_encode(['data_limit' => $limit])], $token);
                if ($r['code'] < 300) return ['ok' => true];
            }
            return ['ok' => false];

        case 'modify_admin_status':
            $u = $args['username'] ?? '';
            $status = $args['status'] ?? 'active';
            foreach (["PUT:/api/admin/$u", "PATCH:/api/admin/$u", "PUT:/api/admins/$u"] as $mpath) {
                list($m, $pth) = explode(':', $mpath);
                $r = panel_http_request($m, $p['base_url'], $pth, ['__raw_body' => json_encode(['status' => $status])], $token);
                if ($r['code'] < 300) return ['ok' => true];
            }
            return ['ok' => false];

        case 'create_admin':
            $body = [
                'username' => $args['username'] ?? '',
                'password' => $args['password'] ?? '',
                // حجم: gigabytes → bytes (data_limit) — یا data_limit مستقیم اگر bytes داده شده باشد
                'data_limit' => (int)round(((float)($args['volume_gb'] ?? 0)) * 1024 * 1024 * 1024)
                             ?: (int)($args['data_limit'] ?? 0),
            ];
            if (($p['ptype'] ?? '') === 'pasarguard') {
                $body['role_id'] = (int)($args['role_id'] ?? $p['role_id'] ?? 3);
                if (!empty($args['telegram_id'])) $body['telegram_id'] = (int)$args['telegram_id'];
                foreach (['/api/admin', '/api/admins/user'] as $pth) {
                    $r = panel_http_request('POST', $p['base_url'], $pth, ['__raw_body' => json_encode($body)], $token);
                    if ($r['code'] < 300) { $res = $r['json'] ?: []; $res['password_used'] = $body['password']; return ['ok' => true, 'data' => $res]; }
                }
            } else {
                foreach (['/api/admin/user', '/api/admins'] as $pth) {
                    $r = panel_http_request('POST', $p['base_url'], $pth, ['__raw_body' => json_encode($body)], $token);
                    if ($r['code'] < 300) { $res = $r['json'] ?: []; $res['password_used'] = $body['password']; return ['ok' => true, 'data' => $res]; }
                }
            }
            return ['ok' => false, 'error' => "create failed"];

        default:
            return ['ok' => false, 'error' => "unsupported action: $action"];
    }
}
