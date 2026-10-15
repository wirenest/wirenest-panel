<?php
if (!defined('BASE_DIR')) define('BASE_DIR', dirname(__DIR__));
/** live_panel_test.php — real panel ping via bridge */
require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/lib/panel_api.php';

$p = panel_client();
if (!$p) { echo "no panel configured\n"; exit; }
echo 'panel: ' . $p['base_url'] . ' type=' . $p['ptype'] . PHP_EOL;
echo 'pw len: ' . strlen($p['password']) . PHP_EOL;
$r = panel_ping($p);
echo 'ping: ' . json_encode($r, JSON_UNESCAPED_UNICODE) . PHP_EOL;

$roles = panel_list_roles($p);
echo 'roles: ' . count($roles) . PHP_EOL;
foreach (array_slice($roles, 0, 5) as $rr) {
    echo '  - #' . ($rr['id'] ?? '?') . ' ' . ($rr['name'] ?? '?') . (empty($rr['is_owner']) ? '' : ' (owner)') . PHP_EOL;
}
echo 'LIVE PANEL TEST DONE' . PHP_EOL;