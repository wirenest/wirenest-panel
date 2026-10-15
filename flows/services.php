<?php
/**
 * flows/services.php — «🛍 سرویس های من» landing + per-service home (کپی مو‌به‌موی ui.py)
 * services_screen: text+kb — service_home: status/usage/toggle/creds/login-url.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';

/** panel_name → base_url از تنظیمات پنل‌ها (برای لینک ورود وب). */
function service_panel_base(string $panelName): string {
    $panels = get_setting('panels', []) ?: [];
    foreach ($panels as $pname => $cfg) {
        if (strcasecmp((string)$pname, $panelName) === 0) {
            return (string)($cfg['base_url'] ?? '');
        }
    }
    return $panelName; // fallback: خود اسم (رفتار قبلی)
}

/** Exact copy of ui.services_screen() (main.py 813-821). */
function services_home(int $chatId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE tg_id=? ORDER BY id DESC');
    $st->execute([$chatId]);
    $rows = $st->fetchAll();
    if (!$rows) {
        send_or_edit($chatId,
            "🛡 فعلاً سرویسی نداری. از «🔐 خرید اشتراک» یک سرویس تهیه کن 🛒",
            main_menu_kb(is_admin($chatId)));
        return;
    }
    $kb = ['inline_keyboard' => []];
    foreach ($rows as $r) {
        $kb['inline_keyboard'][] = [['text' => '🛡 ' . $r['panel_username'], 'callback_data' => 'svc:' . $r['id']]];
    }
    $kb['inline_keyboard'][] = [['text' => '➡️ منوی اصلی', 'callback_data' => 'm:home']];
    $text = "🔖 <b>مدیریت سرویس</b>\n\n"
          . "🪂 سرویسی که می‌خواهید مدیریت کنید را از لیست زیر انتخاب کنید.\n\n"
          . "🪂 بعد از انتخاب: مشخصات، حجم اضافه، رمز، روشن/خاموش و ورود به پنل وب در دسترس است.";
    send_or_edit($chatId, $text, $kb);
}

/** Exact copy of ui.service_home() (main.py 824-856): live status via panel. */
function service_screen(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $st->execute([$svcId, $chatId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'یافت نشد'); return; }

    $statusActive = true; $usedGb = null;
    $totalGb = $s['quota_gb'] !== null ? (float)$s['quota_gb'] : null;
    $p = panel_client($s['panel_name'], $s['panel_type'] ?: null);
    if ($p) {
        // پایتون وضعیت را از list_admins می‌خواند (get_admin_info برای ادمین null برمی‌گرداند)
        $res = panel_bridge_call($p, 'list_admins', []);
        $mine = null;
        foreach ((array)($res['data'] ?? []) as $a) {
            if (($a['username'] ?? '') === $s['panel_username']) { $mine = $a; break; }
        }
        if ($mine) {
            $usedGb = round((float)($mine['used_traffic'] ?? 0) / (1024 ** 3), 2);
            $limB = (float)($mine['data_limit'] ?? 0);
            if ($limB) $totalGb = round($limB / (1024 ** 3), 2);
            $statusActive = (($mine['status'] ?? 'active') === 'active');
        }
    }

    if ($totalGb !== null && $totalGb >= 999999) {
        // نامحدود (پنل limit=0 یا سهمیهٔ ثبت‌شدهٔ بی‌نهایت)
        $usage = $usedGb !== null
            ? "📊 حجم مصرفی: {$usedGb} گیگ — سهمیه: نامحدود ∞"
            : '📊 سهمیه: نامحدود ∞';
    } elseif ($usedGb !== null && $totalGb) {
        $usage = "📊 حجم مصرفی: {$usedGb} از {$totalGb} گیگ";
    } else {
        $usage = '📦 سهمیه: ' . ($s['quota_gb'] ?? 0) . ' گیگ';
    }
    $url = panel_login_url(service_panel_base((string)$s['panel_name'])); // base_url پنل از تنظیمات
    $text = "🛡 <b>سرویس شما:</b> <code>{$s['panel_username']}</code>\n"
          . ($statusActive ? '🟢 وضعیت: روشن و فعال' : '🔴 وضعیت: خاموش') . "\n"
          . "$usage\n"
          . "🌐 آدرس ورود: <code>$url</code>";
    // Reza rule: اکانت‌های تست (is_test=1) دکمهٔ خرید حجم اضافه ندارند
    $kbRows = [];
    if (empty($s['is_test'])) {
        $kbRows[] = [['text' => '💳 خرید حجم اضافه', 'callback_data' => "apgb:$svcId"]];
    }
    $kbRows[] = [['text' => '🔑 اطلاعات ورود', 'callback_data' => "apcreds:$svcId"], ['text' => '🌐 ورود به پنل وب ↗️', 'url' => $url]];
    $kbRows[] = [['text' => '🔐 تغییر رمز پنل', 'callback_data' => "apchpw:$svcId"]];
    $kbRows[] = [['text' => $statusActive ? '🔴 خاموش کردن سرویس' : '🟢 روشن کردن سرویس', 'callback_data' => "aptoggle:$svcId"]];
    $kbRows[] = [['text' => '➡️ بازگشت به لیست', 'callback_data' => 'm:services']];
    $kb = ['inline_keyboard' => $kbRows];
    send_or_edit($chatId, $text, $kb);
}

/** Exact copy of aptoggle handler (main.py 973-1030): روشن/خاموش کردن سرویس روی پنل + رندر دوباره صفحه درجا. */
function service_toggle(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $st->execute([$svcId, $chatId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'یافت نشد'); return; }
    $p = panel_client($s['panel_name'], $s['panel_type'] ?: null);
    if (!$p) { send_or_edit($chatId, 'پنل متصل نیست'); return; }
    // پایتون از list_admins وضعیت را پیدا می‌کند (main.py 979-991)
    $res = panel_bridge_call($p, 'list_admins', []);
    $mine = null;
    foreach ((array)($res['data'] ?? []) as $a) {
        if (($a['username'] ?? '') === $s['panel_username']) { $mine = $a; break; }
    }
    if (!$mine) { send_or_edit($chatId, 'وضعیت سرویس از پنل دریافت نشد'); return; }
    $cur = strtolower((string)($mine['status'] ?? 'active'));
    $newStatus = $cur === 'active' ? 'disabled' : 'active';
    $res2 = panel_bridge_call($p, 'modify_admin_status', ['username' => $s['panel_username'], 'status' => $newStatus]);
    if (empty($res2['ok'])) { send_or_edit($chatId, '❌ تغییر وضعیت ناموفق بود'); return; }
    // re-render the service home screen in place with the NEW status (main.py parity)
    service_screen($chatId, $svcId);
}

/** Exact copy of apgb flow start (main.py 1070-1089): خرید حجم اضافه — state agent_gb با قیمت/حداقل پنل. */
function service_extra_gb_start(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $st->execute([$svcId, $chatId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'یافت نشد'); return; }
    // Reza rule: اکانت تست حجم اضافه ندارد
    if (!empty($s['is_test'])) { send_or_edit($chatId, '⛔️ برای اکانت تست، خرید حجم اضافه فعال نیست.'); return; }
    $panels = (array)(get_setting('panels', []) ?: []);
    $d = $panels[(string)get_setting('selected_panel', '')] ?? null;
    if (!$d) {
        foreach ($panels as $v) { if (($v['base_url'] ?? '') === $s['panel_name']) { $d = $v; break; } }
    }
    if (!$d || empty($d['extra_gb_price'])) { send_or_edit($chatId, 'قیمت حجم اضافه هنوز توسط ادمین تنظیم نشده ❗️'); return; }
    $xp = (int)$d['extra_gb_price'];
    $xmin = (int)($d['extra_gb_min'] ?? 1);
    st_set($chatId, ['await' => 'agent_gb', 'pid' => $svcId, 'xp' => $xp, 'xmin' => $xmin]);
    send_or_edit($chatId,
        "📦 چند گیگ اضافه می‌خواهی؟\n\n"
        . '💰 قیمت حجم اضافه: ' . number_format($xp) . " تومان برای هر گیگ\n"
        . "⚖️ حداقل خرید: {$xmin} گیگ\n\n"
        . 'عدد بفرست (مثلاً 50):');
}

/** Exact copy of apcreds handler (main.py 1025-1033): resend login info. */
function service_login_info(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $st->execute([$svcId, $chatId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'یافت نشد.'); return; }
    $url = panel_login_url(service_panel_base((string)$s['panel_name'])); // base_url پنل از تنظیمات
    send_or_edit($chatId,
        "🔑 اطلاعات ورود پنل:\n\n🌐 آدرس: <code>$url</code>\n"
        . "👤 نام کاربری: <code>{$s['panel_username']}</code>\n"
        . '🔑 رمز عبور: <code>' . htmlspecialchars(panel_decrypt_pw((string)$s['panel_password'])) . '</code>',
        main_menu_kb(false));
}

function service_change_password_start(int $chatId, int $svcId): void {
    st_set($chatId, ['await' => "svcnewpass:$svcId"]);
    send_or_edit($chatId, 'رمز جدید رو بفرست (حداقل ۸ کاراکتر):');
}

function service_change_password_apply(int $chatId, string $text): void {
    $svcId = (int)substr((string)st_get($chatId, 'await', ''), 11);
    st_pop($chatId);
    if (mb_strlen($text) < 8) { send_or_edit($chatId, '❌ رمز حداقل ۸ کاراکتر باشه. دوباره از منوی سرویس شروع کن.'); return; }
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=? AND tg_id=?');
    $st->execute([$svcId, $chatId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'سرویس یافت نشد.'); return; }
    $p = panel_client($s['panel_name'], $s['panel_type'] ?: null);
    if (!$p) { send_or_edit($chatId, '❌ خطا در اتصال به پنل.'); return; }
    $res = panel_bridge_call($p, 'modify_admin_password', ['username' => $s['panel_username'], 'password' => $text]);
    if (empty($res['ok'])) { send_or_edit($chatId, '❌ تغییر رمز ناموفق: ' . ($res['error'] ?? '?')); return; }
    db()->prepare('UPDATE agent_panels SET panel_password=? WHERE id=?')->execute([panel_encrypt_pw($text), $svcId]);
    send_or_edit($chatId, '✅ رمز عوض شد!', main_menu_kb(false));
}