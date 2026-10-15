<?php
/**
 * features.php — قابلیت‌های پنل (کپی main.py 2459-2492 + FEATURE_ITEMS 54-61).
 */
const FEATURE_ITEMS = [
    ['buy',   '🛒 خرید'],
    ['topup', '💰 شارژ موجودی'],
    ['manage', '👤 مدیریت سرویس'],
    ['gift',  '🎁 هدیه/کد تخفیف'],
    ['guide', '📡 راهنمای اتصال'],
    ['faq',   '❓ سوالات متداول'],
];

/** adm:features — لیست قابلیت‌ها با وضعیت ✅/⛔️ (کپی main.py 2459-2471). */
function admin_features_home(int $chatId): void {
    $feats = (array)(get_setting('features', []) ?: []);
    $rows = [];
    $items = FEATURE_ITEMS;
    for ($i = 0; $i < count($items); $i += 2) {
        $line = [];
        foreach (array_slice($items, $i, 2) as [$k, $label]) {
            $on = ($feats[$k] ?? true) ? '✅' : '⛔️';
            $line[] = ['text' => "$on $label", 'callback_data' => "feat:$k"];
        }
        $rows[] = $line;
    }
    $rows[] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId, '🛠 <b>قابلیت‌های پنل</b>', ['inline_keyboard' => $rows]);
}

/** feat:<key> — toggle + رندر دوباره لیست (کپی main.py 2474-2492). */
function admin_feature_toggle(int $chatId, string $key): void {
    $feats = (array)(get_setting('features', []) ?: []);
    $feats[$key] = !($feats[$key] ?? true);
    set_setting('features', $feats);
    admin_features_home($chatId);
}