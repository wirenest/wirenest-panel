<?php
/**
 * admin/panels.php — additions: toggle + edit (opencode audit findings 3-4)
 * toggle: فعال/غیرفعال کردن پنل؛ edit: ویزارد ویرایش آدرس/یوزر/پسورد
 */

/** pnl:toggle:<name> — فعال/غیرفعال (پایتون: toggle_lbl در ui.py 367). */
function admin_panel_toggle(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    $panels[$name]['active'] = empty($panels[$name]['active']);
    set_setting('panels', $panels);
    $new = !empty($panels[$name]['active']);
    send_or_edit($chatId, $new ? "🟢 پنل «{$name}» فعال شد." : "🔴 پنل «{$name}» غیرفعال شد.");
    admin_panel_view($chatId, $name);
}

/** pnl:edit:<name> — منوی ویرایش فیلدها (نام/آدرس/یوزر/پسورد). */
function admin_panel_edit_start(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    send_or_edit($chatId, "✏️ چه چیزی از پنل «{$name}» ویرایش بشه؟",
        ['inline_keyboard' => [
            [['text' => '📛 نام پنل', 'callback_data' => "pnledit:name:$name"]],
            [['text' => '🔗 آدرس پنل', 'callback_data' => "pnledit:url:$name"]],
            [['text' => '👤 یوزر ادمین', 'callback_data' => "pnledit:user:$name"], ['text' => '🔑 پسورد ادمین', 'callback_data' => "pnledit:pass:$name"]],
            [['text' => '◀️ بازگشت', 'callback_data' => "pnl:view:$name"]],
        ]]);
}

/** wal:gift — ورود کد هدیه توسط کاربر (کپی main.py 1361-1366). */
function start_gift_redeem(int $chatId): void {
    st_set($chatId, ['await' => 'gift_redeem']);
    send_or_edit($chatId, '🎁 کد هدیه را بفرست (یا /cancel برای انصراف):');
}
