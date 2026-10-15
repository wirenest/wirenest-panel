<?php
/**
 * admin/discounts.php — کد تخفیف و کد هدیه (کپی مو‌به‌موی main.py 2097-2144, 3740-3780):
 * لیست با دکمه حذف، فلو dsc_code→dsc_value، فلو gift_code→gift_amount، okdel.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';

/** adm:discounts — کپی main.py 2097-2107. */
function admin_discounts_home(int $chatId): void {
    $codes = db()->query('SELECT * FROM discount_codes ORDER BY id DESC')->fetchAll();
    $rows = [];
    foreach ($codes as $c) {
        $kind = $c['kind'] === 'percent' ? '٪' : 'ت';
        $limit = $c['max_uses'] ?: '∞';
        $rows[] = [['text' => "🗑 {$c['code']} ({$c['value']}{$kind} — {$c['used']}/$limit)", 'callback_data' => "okdel:discount:{$c['id']}"]];
    }
    $rows[] = [['text' => '➕ افزودن کد تخفیف', 'callback_data' => 'dsc:add']];
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId, "🏷️ <b>کدهای تخفیف</b>\n🗑 = حذف", ['inline_keyboard' => $rows]);
}

/** adm:gifts — کپی main.py 2118-2127. */
function admin_gifts_home(int $chatId): void {
    $codes = db()->query('SELECT * FROM gift_codes ORDER BY id DESC')->fetchAll();
    $rows = [];
    foreach ($codes as $c) {
        $limit = $c['max_uses'] ?: '∞';
        $rows[] = [['text' => "🗑 {$c['code']} (" . fmt_price((int)$c['amount']) . " — {$c['used']}/$limit)", 'callback_data' => "okdel:gift:{$c['id']}"]];
    }
    $rows[] = [['text' => '➕ افزودن کد هدیه', 'callback_data' => 'gift:add']];
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId, "🎁 <b>کدهای هدیه</b>\n🗑 = حذف", ['inline_keyboard' => $rows]);
}

/** dsc:add / gift:add — کپی main.py 2109-2115, 2129-2135. */
function admin_code_add_start(int $chatId, string $type): void {
    st_set($chatId, ['await' => $type === 'dsc' ? 'dsc_code' : 'gift_code']);
    if ($type === 'dsc') send_or_edit($chatId, '🏷 کد تخفیف (لاتین، بدون فاصله):');
    else send_or_edit($chatId, '🎁 کد هدیه (لاتین، بدون فاصله):');
}

/** okdel:discount:<id> / okdel:gift:<id> — کپی main.py 2138-2144 + gift delete. */
function admin_code_delete(int $chatId, string $data): void {
    $parts = explode(':', $data);
    $type = $parts[1];
    $id = (int)$parts[2];
    if ($type === 'discount') {
        db()->prepare('DELETE FROM discount_codes WHERE id=?')->execute([$id]);
        send_or_edit($chatId, 'کد تخفیف حذف شد');
    } else {
        db()->prepare('DELETE FROM gift_codes WHERE id=?')->execute([$id]);
        send_or_edit($chatId, 'کد هدیه حذف شد');
    }
}

/** dsc_code state — کپی main.py 3740-3745. */
function admin_dsc_code_apply(int $chatId, string $text): void {
    $code = str_replace(' ', '', trim($text));
    if (!$code || !preg_match('/^[A-Za-z0-9_\-]{3,32}$/', $code)) {
        send_or_edit($chatId, 'کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر:');
        return;
    }
    st_set($chatId, ['await' => 'dsc_value', 'dcode' => $code]);
    send_or_edit($chatId, "💰 مقدار تخفیف را بفرست:\nدرصد: مثلا 20\nمبلغ ثابت تومان: مثلا 50000\n(برای تعیین نوع، پسوند بزن: 20% یا 50000t)");
}

/** dsc_value state — کپی main.py 3747-3765. */
function admin_dsc_value_apply(int $chatId, string $text): void {
    $v = trim($text);
    $kind = 'percent'; $val = 0;
    if (preg_match('/^(\d+)\s*%$/', $v, $m)) {
        $kind = 'percent'; $val = (int)$m[1];
    } elseif (preg_match('/^(\d+)\s*t$/i', $v, $m)) {
        $kind = 'fixed'; $val = (int)$m[1];
    } elseif (preg_match('/^\d+$/', $v)) {
        $kind = 'fixed'; $val = (int)$v;
    } else {
        send_or_edit($chatId, 'فرمت: 20% یا 50000t یا 50000');
        return;
    }
    $code = (string)st_get($chatId, 'dcode', '');
    st_pop($chatId);
    db()->prepare('INSERT OR REPLACE INTO discount_codes(code, kind, value, used) VALUES(?,?,?,0)')
       ->execute([$code, $kind, $val]);
    $suffix = $kind === 'percent' ? '%' : ' تومان';
    send_or_edit($chatId, "✅ کد تخفیف «{$code}» ساخته شد ({$val}{$suffix}).");
}

/** gift_code state — کپی main.py 3767-3772. */
function admin_gift_code_apply(int $chatId, string $text): void {
    $code = str_replace(' ', '', trim($text));
    if (!$code || !preg_match('/^[A-Za-z0-9_\-]{3,32}$/', $code)) {
        send_or_edit($chatId, 'کد نامعتبر — لاتین/عدد ۳ تا ۳۲ کاراکتر:');
        return;
    }
    st_set($chatId, ['await' => 'gift_amount', 'gcode' => $code]);
    send_or_edit($chatId, '💰 مبلغ هدیه (تومان) را بفرست:');
}

/** gift_amount state — کپی main.py 3774-3780. */
function admin_gift_amount_apply(int $chatId, string $text): void {
    if (!preg_match('/\d+/', str_replace(',', '', $text), $m)) {
        send_or_edit($chatId, 'عدد بفرست.');
        return;
    }
    $code = (string)st_get($chatId, 'gcode', '');
    st_pop($chatId);
    db()->prepare('INSERT OR REPLACE INTO gift_codes(code, amount, used) VALUES(?,?,0)')
       ->execute([$code, (int)$m[0]]);
    send_or_edit($chatId, "✅ کد هدیه «{$code}» ساخته شد.");
}