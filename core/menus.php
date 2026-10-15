<?php
/**
 * menus.php — keyboards & screens (1:1 با ui.py پایتون)
 * چیدمان منوی اصلی (دستور رضا):
 *   🧪 سرویس تست      🔐 خرید اشتراک
 *   🛍 سرویس های من   🏦 کیف پول + شارژ
 *   📡 راهنمای اتصال  📋 شرایط و توضیحات
 *   ☎️ پشتیبانی       ❓ سوالات متداول
 *   👨‍💼 پنل مدیریت     (فقط ادمین)
 */

function LBL(): array {
    return [
        'test'       => '🧪 سرویس تست',
        'buy'        => '🔐 خرید اشتراک',
        'services'   => '🛍 سرویس های من',
        'wallet'     => '🏦 کیف پول + شارژ',
        'guide'      => '📡 راهنمای اتصال',
        'conditions' => '📋 شرایط و توضیحات',
        'support'    => '☎️ پشتیبانی',
        'faq'        => '❓ سوالات متداول',
        'admin'      => '👨‍💼 پنل مدیریت',
    ];
}

function features(): array {
    return get_setting('features', []) ?: [];
}
function feat_on(string $key, bool $def = false): bool {
    $f = features();
    return array_key_exists($key, $f) ? (bool)$f[$key] : $def;
}

function reply_btn(string $text, array $opts = []): array {
    return array_merge(['text' => $text], $opts);
}

/** Reply main menu — چیدمان ثابت + گیت قابلیت‌ها (مثل main_menu در ui.py) */
function main_menu_kb(bool $isAdmin = false): array {
    $L = LBL();
    $rows = [
        [$L['test'], $L['buy']],
        [$L['services'], $L['wallet']],
        [$L['guide'], $L['conditions']],
        [$L['support'], $L['faq']],
    ];
    if ($isAdmin) $rows[] = [$L['admin']];
    return ['keyboard' => $rows, 'resize_keyboard' => true];
}

/** Remove keyboard (screen transitions in python used edit+new kb; reply mode keeps menu) */
function main_menu_force(int $chatId): array {
    return tg_send($chatId, '🏠', main_menu_kb(is_admin($chatId)));
}

/** Admin panel keyboard (پنل مدیریت) — main entries */
function admin_menu_kb(): array {
    // کپی دقیق ui.admin_main_kb() (ui.py 169-180)
    return ['inline_keyboard' => [
        [['text' => '📊 آمار', 'callback_data' => 'adm:stats'], ['text' => '📦 مدیریت پنل‌ها', 'callback_data' => 'adm:panels']],
        [['text' => '👥 مدیریت کاربران', 'callback_data' => 'adm:users'], ['text' => '🧾 صف رسیدها', 'callback_data' => 'adm:receipts']],
        [['text' => '🛠 قابلیت‌های پنل', 'callback_data' => 'adm:features']],
        [['text' => '🏷 کد تخفیف', 'callback_data' => 'adm:discounts'], ['text' => '🎁 کد هدیه', 'callback_data' => 'adm:gifts']],
        [['text' => '📚 مدیریت آموزش', 'callback_data' => 'adm:helps'], ['text' => '⚙️ تنظیمات', 'callback_data' => 'adm:settings']],
        [['text' => '🔌 خاموش/روشن', 'callback_data' => 'adm:power']],
    ]];
}

/** Support screen kb — کپی ui.support_kb() (✉️ ارسال پیام به پشتیبانی + بازگشت) */
function support_kb(): array {
    return ['inline_keyboard' => [
        [['text' => '✉️ ارسال پیام به پشتیبانی', 'callback_data' => 'm:tkt']],
        [['text' => '🏠 بازگشت به منوی اصلی', 'callback_data' => 'm:home']],
    ]];
}

/** Panel manage entry: list panels + per-panel test button (🔍 تست اتصال) */
function panels_list_kb(array $panels): array {
    $rows = [];
    foreach ($panels as $name => $d) {
        $rows[] = [['text' => "🌐 $name", 'callback_data' => "pnl:view:" . $name],
                   ['text' => '🔍 تست اتصال', 'callback_data' => "pnl:ping:" . $name]];
    }
    $rows[] = [['text' => '➕ افزودن پنل جدید', 'callback_data' => 'pnl:add']];
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    return ['inline_keyboard' => $rows];
}

/** Services list screen (🛍 سرویس های من) */
function services_kb(array $services): array {
    $rows = [];
    foreach ($services as $s) {
        $rows[] = [['text' => '🛡 ' . $s['panel_username'], 'callback_data' => 'svc:' . $s['id']]];
    }
    $rows[] = [['text' => '➡️ منوی اصلی', 'callback_data' => 'm:home']];
    return ['inline_keyboard' => $rows];
}

/** Receipts queue buttons */

function tickets_kb(array $tickets): array {
    $rows = [];
    foreach ($tickets as $t) {
        $preview = mb_substr((string)$t['text'], 0, 30);
        $rows[] = [['text' => "🎫 #{$t['id']} $preview", 'callback_data' => "um:{$t['tg_id']}"],
                   ['text' => '✅', 'callback_data' => "tkclose:{$t['id']}"]];
    }
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    return ['inline_keyboard' => $rows];
}

/** Broadcast v2 step keyboards */
function bcast_target_kb(): array {
    return ['inline_keyboard' => [
        [['text' => '👥 همه کاربران', 'callback_data' => 'bcast2:all']],
        [['text' => '🛒 خریدارها', 'callback_data' => 'bcast2:buyers']],
        [['text' => '🚫 خرید نداشته‌ها', 'callback_data' => 'bcast2:nonbuyers']],
        [['text' => '❌ لغو', 'callback_data' => 'adm:back']],
    ]];
}
function bcast_btn_kb(): array {
    return ['inline_keyboard' => [
        [['text' => '🔐 خرید اشتراک', 'callback_data' => 'bcastbtn:buy']],
        [['text' => '🧪 دریافت تست', 'callback_data' => 'bcastbtn:test']],
        [['text' => '☎️ پیام به پشتیبانی', 'callback_data' => 'bcastbtn:support']],
        [['text' => '📚 آموزش', 'callback_data' => 'bcastbtn:help']],
        [['text' => '📤 ارسال بدون دکمه', 'callback_data' => 'bcastbtn:none']],
    ]];
}
function bcast_pin_kb(): array {
    return ['inline_keyboard' => [
        [['text' => '📌 بله، پین شود', 'callback_data' => 'bcastgo:yes'],
         ['text' => '🚫 خیر', 'callback_data' => 'bcastgo:no']],
    ]];
}

/** Shop buy screen rows (plans + tariffs) */
function buy_kb(array $plans, array $tariffs): array {
    $rows = [];
    foreach ($plans as $p) {
        // Bidi fix: اسم پنل ممکن است لاتین باشد (مثلا پنل1) — قطعهٔ فارسی «X گیگ — Y تومان» با LRI…PDI isolate
        // می‌شود تا در RTL/LTR ترکیبی، ترتیب کلمات نپرد (فرمان رضا: نوع نوشتاری دکمه‌ها درست شود).
        $rows[] = [[ 'text' => "📦 {$p['panel_name']} — \u{2066}" . fmt_gb($p['volume_gb']) . " گیگ\u{2069} — \u{2066}" . fmt_price((int)$p['price']) . "\u{2069}",
                     'callback_data' => "buyplan:{$p['id']}" ]];
    }
    foreach ($tariffs as $t) {
        $rows[] = [[ 'text' => "🏷 {$t['title']} — \u{2066}" . fmt_gb($t['volume_gb']) . " گیگ\u{2069} — \u{2066}" . fmt_price((int)$t['price']) . "\u{2069}",
                     'callback_data' => "buy:{$t['id']}" ]];
    }
    $rows[] = [['text' => '➡️ منوی اصلی', 'callback_data' => 'm:home']];
    return ['inline_keyboard' => $rows];
}