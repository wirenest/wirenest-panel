<?php
/**
 * admin/bcast.php — کپی مو‌به‌موی پایتون:
 * adm:bcast منو (main.py 1968-1975)، bcast2 (2692-2699)، bcast2_text (3315-3326)،
 * bcastbtn (2701-2714)، bcastgo ضداسپم (2716-2790): دستهٔ ۱۵، مکث 2.5s، فاصله 0.25s، پین.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';

/** adm:bcast — کپی main.py 1968-1975. */
function bcast_home(int $chatId): void {
    send_or_edit($chatId, "📣 <b>پیام همگانی</b>\nبه کدام گروه ارسال شود؟", ['inline_keyboard' => [
        [['text' => '👥 همه کاربران', 'callback_data' => 'bcast2:all'],
         ['text' => '🛒 خریدارها', 'callback_data' => 'bcast2:buyers']],
        [['text' => '🚫 خرید نداشته‌ها', 'callback_data' => 'bcast2:nonbuyers']],
        [['text' => '◀️ بازگشت', 'callback_data' => 'adm:users']],
    ]]);
}

/** bcast2:<aud> — کپی main.py 2692-2699. */
function bcast_audience_pick(int $chatId, string $aud): void {
    st_set($chatId, ['await' => 'bcast2_text', 'bcast_aud' => $aud]);
    $lbl = ['all' => 'همه کاربران', 'buyers' => 'خریدارها', 'nonbuyers' => 'خرید نداشته‌ها'][$aud] ?? $aud;
    send_or_edit($chatId, "📣 متن پیام همگانی برای «{$lbl}» را بفرست:");
}

/** bcast2_text state — کپی main.py 3315-3326. */
function bcast_text_received(int $chatId, string $text): void {
    st_set($chatId, ['await' => 'bcast2_btn', 'bcast_text' => $text]);
    send_or_edit($chatId, '📣 زیر پیام همگانی چه دکمه‌ای بگذارم؟', ['inline_keyboard' => [
        [['text' => '🔐 خرید اشتراک', 'callback_data' => 'bcastbtn:buy'],
         ['text' => '🧪 دریافت تست', 'callback_data' => 'bcastbtn:test']],
        [['text' => '☎️ پیام به پشتیبانی', 'callback_data' => 'bcastbtn:support'],
         ['text' => '📚 آموزش', 'callback_data' => 'bcastbtn:help']],
        [['text' => '📤 ارسال بدون دکمه', 'callback_data' => 'bcastbtn:none']],
    ]]);
}

/** bcastbtn:<b> — کپی main.py 2701-2714. */
function bcast_btn_pick(int $chatId, string $b): void {
    $st = st_all($chatId);
    if (($st['await'] ?? '') !== 'bcast2_btn') { send_or_edit($chatId, 'پیام یافت نشد — دوباره شروع کن'); return; }
    st_set($chatId, ['bcast_btn' => $b]);
    send_or_edit($chatId, '📌 این پیام برای کاربر پین شود؟', ['inline_keyboard' => [
        [['text' => '📌 بله، پین شود', 'callback_data' => 'bcastgo:yes'],
         ['text' => '🚫 خیر', 'callback_data' => 'bcastgo:no']],
    ]]);
}

/** bcastgo:<yes|no> — کپی main.py 2716-2790 (همگام، ضداسپم). */
function bcast_run(int $chatId, bool $pin): void {
    $st = st_all($chatId);
    if (!isset($st['bcast_text'])) { send_or_edit($chatId, 'پیام یافت نشد'); return; }
    $text = (string)$st['bcast_text'];
    $aud = (string)($st['bcast_aud'] ?? 'all');
    $btn = (string)($st['bcast_btn'] ?? 'none');
    st_pop($chatId);

    // audience (main.py 2725-2728)
    if ($aud === 'buyers') {
        $ids = db()->query('SELECT DISTINCT tg_id FROM purchases')->fetchAll(PDO::FETCH_COLUMN);
    } elseif ($aud === 'nonbuyers') {
        $ids = db()->query('SELECT tg_id FROM users WHERE is_banned=0 AND tg_id NOT IN (SELECT DISTINCT tg_id FROM purchases)')->fetchAll(PDO::FETCH_COLUMN);
    } else {
        $ids = db()->query('SELECT tg_id FROM users')->fetchAll(PDO::FETCH_COLUMN);
    }
    $users = array_map('intval', $ids);

    $audLbl = ['all' => 'همه کاربران', 'buyers' => 'خریدارها', 'nonbuyers' => 'خرید نداشته‌ها'][$aud] ?? $aud;
    // BTN_KB exact (main.py 2730-2735) — callback_data مانند پایتون
    $btnKb = [
        'buy'     => ['inline_keyboard' => [[['text' => '🔐 خرید اشتراک', 'callback_data' => 'm:buy']]]],
        'test'    => ['inline_keyboard' => [[['text' => '🧪 دریافت تست', 'callback_data' => 'm:test']]]],
        'support' => ['inline_keyboard' => [[['text' => '☎️ پیام به پشتیبانی', 'callback_data' => 'm:support']]]],
        'help'    => ['inline_keyboard' => [[['text' => '📚 آموزش', 'callback_data' => 'm:help']]]],
    ];
    $kb = $btnKb[$btn] ?? null;

    $total = count($users);
    if (!$total) { send_or_edit($chatId, "✅ ارسال تمام شد: 0 نفر ($audLbl)"); return; }
    $prog = send_or_edit($chatId, "📣 در حال ارسال به $total نفر ($audLbl)…\nارسال: 0");
    $progId = (int)($prog['result']['message_id'] ?? 0);
    $bcastEdit = function (string $txt) use ($chatId, $progId): void {
        if ($progId) tg('editMessageText', ['chat_id' => $chatId, 'message_id' => $progId, 'text' => $txt]);
        else send_or_edit($chatId, $txt);
    };

    // ضداسپم (Reza rule = پایتون): BATCH=15، مکث 2.5s، فاصله 0.25s، retry بعد 429
    $sent = 0; $failed = 0; $i = 0;
    $BATCH = 15;
    foreach ($users as $uid) {
        usleep(250000); // python parity 0.25s gap per message (main.py 2782) — also unblocks getUpdates between sends
        $resp = tg_send($uid, $text, $kb);
        $ok = (bool)($resp['ok'] ?? false);
        $mid = (int)($resp['result']['message_id'] ?? 0);
        if ($ok) { $sent++; }
        else {
            usleep(300000); // کوتاه بعد خطا (پایتون: retry_after ساده‌سازی شد)
            $resp = tg_send($uid, $text, $kb);
            $ok = (bool)($resp['ok'] ?? false);
            $mid = (int)($resp['result']['message_id'] ?? 0);
            if ($ok) $sent++; else $failed++;
        }
        if ($pin && $ok && $mid) {
            // پین (main.py 2747-2755)
            tg('pinChatMessage', ['chat_id' => $uid, 'message_id' => $mid, 'disable_notification' => true]);
        }
        $i++;
        if ($i % $BATCH === 0) {
            $bcastEdit("📣 در حال ارسال به $total نفر ($audLbl)…\nارسال: $sent | خطا: $failed");
            sleep(2); // مکث بین دسته‌ها (2.5 در پایتون)
        } else {
            usleep(250000); // فاصله هر پیام 0.25s
        }
    }
    $failTxt = $failed ? " | ناموفق: $failed" : '';
    $pinTxt = $pin ? ' — پیام پین شد 📌' : '';
    $bcastEdit("✅ ارسال تمام شد: $sent نفر ($audLbl)$failTxt$pinTxt");
}