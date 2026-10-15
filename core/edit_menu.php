<?php
/**
 * edit_menu.php — کپی _edit_menu پایتون (main.py 1585-1600):
 * پیام جاری (همان پیامی که دکمه روی آن است) ویرایش می‌شود؛ اگر ویرایش ممکن نبود
 * اول edit_reply_markup، بعد ویرایش متن بدون کیبورد، و در نهایت fallback ارسال پیام جدید.
 */

/** ویرایش درجا با fallback هوشمند (اصلاح باگ رضا: بروزرسانیِ محتوای بدون تغییر، دکمه‌ها را حذف می‌کرد).
 *  سناریو: متن+کیبورد عیناً همان قبلی است → تلگرام «message is not modified» می‌دهد → باید همون پیام با دکمه‌ها دست‌نخورده بماند. */
function edit_menu(int $chatId, int $msgId, string $text, ?array $kb = null): void {
    if ($msgId) {
        $params = ['chat_id' => $chatId, 'message_id' => $msgId, 'text' => $text, 'parse_mode' => 'HTML'];
        if ($kb) $params['reply_markup'] = $kb;
        $r = tg('editMessageText', $params);
        if (($r['ok'] ?? false) === true) return;
        $desc = (string)($r['description'] ?? '');
        // محتوا عیناً همان قبلی است — پیام (با دکمه‌هایش) سر جایش می‌ماند
        if (str_contains($desc, 'message is not modified')) return;
        // فالبک ۲: فقط کیبورد عوض شود
        if ($kb) {
            $r2 = tg('editMessageReplyMarkup', ['chat_id' => $chatId, 'message_id' => $msgId, 'reply_markup' => $kb]);
            if (($r2['ok'] ?? false) === true) return;
            if (str_contains((string)($r2['description'] ?? ''), 'message is not modified')) return;
        }
        // فالبک ۳: ویرایش مجدد متن (با کیبورد) — اگر باز نشد، بدون کیبورد
        $r3 = tg('editMessageText', $params);
        if (($r3['ok'] ?? false) !== true) {
            tg('editMessageText', ['chat_id' => $chatId, 'message_id' => $msgId, 'text' => $text, 'parse_mode' => 'HTML']);
        }
        return;
    }
    tg_send($chatId, $text, $kb);
}

/** helper: msgId را از callback استخراج کن. */
function cb_msg_id(array $cq): int {
    return (int)($cq['message']['message_id'] ?? 0);
}


/** آیدی پیام callback جاری (null اگر از پیام متنی آمده). */
function ctx_msg_id(): ?int {
    global $CB_MSG_ID;
    return $CB_MSG_ID;
}
function ctx_msg_id_set(?int $id): void {
    global $CB_MSG_ID;
    $CB_MSG_ID = $id;
}

/** ارسال هوشمند: اگر داخل callback هستیم همان پیام را ویرایش کن، وگرنه پیام جدید. */
function send_or_edit(int $chatId, string $text, ?array $kb = null): void {
    $mid = ctx_msg_id();
    if ($mid) edit_menu($chatId, $mid, $text, $kb);
    else tg_send($chatId, $text, $kb);
}