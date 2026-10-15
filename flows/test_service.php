<?php
/**
 * Test service flow (کپی دقیق پایتون start_test_service + _deliver_test main.py 1107-1190).
 */
function handle_test_start(int $chatId): void {
    $limit = (int)(get_setting('test_limit', 1) ?: 1);
    // count existing test panels for this user
    $st = db()->prepare("SELECT COUNT(*) FROM agent_panels WHERE tg_id=? AND is_test=1");
    $st->execute([$chatId]);
    $count = (int)$st->fetchColumn();

    if ($count >= $limit) {
        send_or_edit($chatId,
            "🧪 شما قبلاً سرویس تست گرفته‌اید!\n"
            . "از بخش «🛍 سرویس های من» می‌تونی مدیریتش کنی.",
            main_menu_kb(is_admin($chatId)));
        return;
    }

    $panels = get_setting('panels', []) ?: [];
    if (!$panels) { tg_send($chatId, '❌ فعلاً پنلی متصل نیست.'); return; }

    // test pool: ACTIVE panels flagged is_test_panel with size/duration (کپی main.py 1123-1134)
    $sel = get_setting('selected_panel');
    $pool = [];
    foreach ($panels as $name => $d) {
        if (!empty($d['is_test_panel']) && !empty($d['test_gb']) && !empty($d['test_days'])
            && !empty($d['active'] ?? ($name === $sel))) {
            $pool[$name] = $d;
        }
    }

    if (!$pool) {
        tg_send($chatId, '⛔️ فعلاً سرویس تست فعال نیست — بعداً دوباره امتحان کن.', main_menu_kb(is_admin($chatId)));
        return;
    }
    if (count($pool) > 1) {
        // چند پنل تست‌دار: کاربر انتخاب می‌کند (کپی main.py 1135-1141)
        $rows = [];
        foreach ($pool as $name => $d) {
            $rows[] = [['text' => sprintf('🧪 %s — %s گیگ / %s روز', $name, (string)(float)$d['test_gb'], (int)$d['test_days']),
                        'callback_data' => 'testpick:' . $name]];
        }
        send_or_edit($chatId, '🧪 از کدام پنل سرویس تست می‌خواهی؟', ['inline_keyboard' => $rows]);
        return;
    }
    $name = array_key_first($pool);
    $d = $pool[$name];

    tg_send($chatId, "⏳ در حال ساخت سرویس تست شما...");

    $p = panel_client($d['base_url'] ?? '', $d['ptype'] ?? 'pasarguard');
    if (!$p) { tg_send($chatId, '❌ خطا در اتصال به پنل — با پشتیبانی تماس بگیر.'); return; }

    $gb = (float)($d['test_gb'] ?? 0.5);
    $days = (int)($d['test_days'] ?? 1);
    $uname = 'test' . substr((string)$chatId, -5);
    $pw = strong_password();

    // Check taken
    $adminsRes = panel_bridge_call($p, 'list_admins', []);
    if ($adminsRes && !empty($adminsRes['ok']) && is_array($adminsRes['data'])) {
        $taken = array_map(fn($a) => strtolower($a['username'] ?? ''), $adminsRes['data']);
        $n = 1;
        $candidate = $uname;
        while (in_array(strtolower($candidate), $taken, true)) {
            $n++;
            $candidate = $uname . $n;
        }
        $uname = $candidate;
    }

    $createRes = panel_bridge_call($p, 'create_admin', [
        'username' => $uname,
        'password' => $pw,
        'volume_gb' => $gb,
        'telegram_id' => $chatId
    ]);

    // فالبک: اگر آیدی تلگرام کاربر روی پنل به ادمین دیگری تعلق دارد (409 UNIQUE)، بدون telegram_id بساز
    if (!$createRes || empty($createRes['ok'])) {
        $createRes = panel_bridge_call($p, 'create_admin', [
            'username' => $uname,
            'password' => $pw,
            'volume_gb' => $gb,
        ]);
    }

    if (!$createRes || empty($createRes['ok'])) {
        tg_send($chatId, '❌ خطا در ساخت پنل تست — با پشتیبانی تماس بگیر.');
        return;
    }

    if (!empty($createRes['data']['password_used'])) {
        $pw = $createRes['data']['password_used'];
    }

    $expires = date('Y-m-d H:i:s', time() + $days * 86400);

    // Save to agent_panels with is_test=1
    db()->prepare("INSERT INTO agent_panels(tg_id, panel_username, panel_password, panel_name, panel_type, quota_gb, expires_at, status, is_test, created_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?, 'active', 1, datetime('now'))")
        ->execute([$chatId, $uname, panel_encrypt_pw($pw), $d['base_url'] ?? '', $d['ptype'] ?? 'pasarguard', $gb, $expires]);

    report_purchase($chatId, $uname, "سرویس تست {$gb} گیگ", 0, 'تست', panel_login_url((string)($d['base_url'] ?? '')));

    tg_send($chatId,
        "🧪 <b>سرویس تست شما آماده شد!</b>\n\n"
        . "🌐 آدرس ورود: <code>" . htmlspecialchars(panel_login_url((string)($d['base_url'] ?? ''))) . "</code>\n"
        . "👤 نام کاربری: <code>$uname</code>\n"
        . "🔑 رمز عبور: <code>$pw</code>\n"
        . "📦 حجم: {$gb} گیگابایت\n"
        . "📅 اعتبار: {$days} روز\n\n"
        . "✨ بعد از تست، سرویس اصلی رو از «🔐 خرید اشتراک» بگیر!",
        ['inline_keyboard' => [[['text' => '🛍 سرویس های من', 'callback_data' => 'm:services']]]]);
}


/** testpick:<name> — کاربر پنل تست را انتخاب کرد (کپی main.py 1142-1147). */
function handle_test_pick(int $chatId, string $name): void {
    $limit = (int)(get_setting('test_limit', 1) ?: 1);
    $st = db()->prepare("SELECT COUNT(*) FROM agent_panels WHERE tg_id=? AND is_test=1");
    $st->execute([$chatId]);
    if ((int)$st->fetchColumn() >= $limit) {
        send_or_edit($chatId, "🧪 شما قبلاً سرویس تست گرفته‌اید!");
        return;
    }
    $panels = get_setting('panels', []) ?: [];
    $d = $panels[$name] ?? null;
    if (!$d) { send_or_edit($chatId, '⛔️ این پنل دیگر در دسترس نیست.'); return; }
    // re-validate test eligibility at click time (panel may have changed between render and click)
    if (empty($d['is_test_panel']) || empty($d['test_gb']) || empty($d['test_days'])
        || empty($d['active'] ?? ($name === get_setting('selected_panel')))) {
        send_or_edit($chatId, '⛔️ سرویس تست این پنل غیرفعال شد.');
        return;
    }

    tg_send($chatId, "⏳ در حال ساخت سرویس تست شما...");

    $p = panel_client($d['base_url'] ?? '', $d['ptype'] ?? 'pasarguard');
    if (!$p) { tg_send($chatId, '❌ خطا در اتصال به پنل — با پشتیبانی تماس بگیر.'); return; }

    $gb = (float)($d['test_gb'] ?? 0.5);
    $days = (int)($d['test_days'] ?? 1);
    $uname = 'test' . substr((string)$chatId, -5);
    $pw = strong_password();

    $adminsRes = panel_bridge_call($p, 'list_admins', []);
    if ($adminsRes && !empty($adminsRes['ok']) && is_array($adminsRes['data'])) {
        $taken = array_map(fn($a) => strtolower($a['username'] ?? ''), $adminsRes['data']);
        $n = 1;
        $candidate = $uname;
        while (in_array(strtolower($candidate), $taken, true)) {
            $n++;
            $candidate = $uname . $n;
        }
        $uname = $candidate;
    }

    $createRes = panel_bridge_call($p, 'create_admin', [
        'username' => $uname,
        'password' => $pw,
        'volume_gb' => $gb,
        'telegram_id' => $chatId
    ]);
    if (!$createRes || empty($createRes['ok'])) {
        $createRes = panel_bridge_call($p, 'create_admin', [
            'username' => $uname,
            'password' => $pw,
            'volume_gb' => $gb,
        ]);
    }
    if (!$createRes || empty($createRes['ok'])) {
        tg_send($chatId, '❌ خطا در ساخت پنل تست — با پشتیبانی تماس بگیر.');
        return;
    }
    if (!empty($createRes['data']['password_used'])) {
        $pw = $createRes['data']['password_used'];
    }

    $expires = date('Y-m-d H:i:s', time() + $days * 86400);
    db()->prepare("INSERT INTO agent_panels(tg_id, panel_username, panel_password, panel_name, panel_type, quota_gb, expires_at, status, is_test, created_at)
                   VALUES(?, ?, ?, ?, ?, ?, ?, 'active', 1, datetime('now'))")
        ->execute([$chatId, $uname, panel_encrypt_pw($pw), $d['base_url'] ?? '', $d['ptype'] ?? 'pasarguard', $gb, $expires]);

    report_purchase($chatId, $uname, "سرویس تست {$gb} گیگ", 0, 'تست', panel_login_url((string)($d['base_url'] ?? '')));
    tg_send($chatId,
        "🧪 <b>سرویس تست شما آماده شد!</b>\n\n"
        . "🌐 آدرس ورود: <code>" . panel_login_url($d['base_url'] ?? '') . "</code>\n"
        . "👤 یوزرنیم: <code>{$uname}</code>\n"
        . "🔑 رمز: <code>{$pw}</code>\n\n"
        . "⚠️ این سرویس بعد از {$days} روز منقضی می‌شود.",
        main_menu_kb(is_admin($chatId)));
}