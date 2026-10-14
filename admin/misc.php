<?php
/**
 * admin/misc.php — stats, tickets, discounts, guide topics, faq
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';

function admin_tickets(int $chatId): void {
    // کپی main.py 2792-2802: لیست تیکت‌های باز + دکمه بستن
    $rows = db()->query("SELECT * FROM tickets WHERE status='open' ORDER BY id DESC LIMIT 10")->fetchAll();
    $kb = ['inline_keyboard' => []];
    foreach ($rows as $t) {
        $preview = mb_substr((string)$t['message'], 0, 28);
        $kb['inline_keyboard'][] = [['text' => "#{$t['id']} — {$preview}…", 'callback_data' => "um:{$t['tg_id']}"]];
        $kb['inline_keyboard'][] = [['text' => "✅ بستن تیکت #{$t['id']}", 'callback_data' => "tkclose:{$t['id']}"]];
    }
    $kb['inline_keyboard'][] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:users']];
    $txt = $rows
        ? "🎫 <b>تیکت‌های باز:</b> " . count($rows) . "\nروی تیکت بزن تا پروفایل کاربر باز شود:"
        : '🎫 <b>تیکت‌های باز:</b> هیچ';
    send_or_edit($chatId, $txt, $kb);
}

function admin_ticket_close(int $chatId, int $tid): void {
    // کپی main.py 2805-2810: بستن + نتیجه
    $st = db()->prepare('SELECT * FROM tickets WHERE id=?');
    $st->execute([$tid]);
    $t = $st->fetch();
    if ($t) {
        db()->prepare("UPDATE tickets SET status='closed' WHERE id=?")->execute([$tid]);
        send_or_edit($chatId, 'تیکت بسته شد ✅');
    }
}


function admin_guide_home(int $chatId): void {
    // پاریتی main.py 2521-2527: مدیریت راهنما روی guide_topics
    $topics = db()->query('SELECT * FROM guide_topics ORDER BY id')->fetchAll();
    $kb = ['inline_keyboard' => []];
    foreach ($topics as $t) {
        $kb['inline_keyboard'][] = [
            ['text' => "✏️ {$t['title']}", 'callback_data' => "helpedit:{$t['id']}"],
            ['text' => "🗑 {$t['title']}", 'callback_data' => "helpdel:{$t['id']}"],
        ];
    }
    $kb['inline_keyboard'][] = [['text' => '➕ افزودن راهنما', 'callback_data' => 'helpadd']];
    $kb['inline_keyboard'][] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId, "📚 مدیریت راهنما:\n✏️ = ویرایش متن | 🗑 = حذف", $kb);
}


/** helpadd — افزودن آموزش (کپی main.py 1906-1910). */
function admin_help_add(int $chatId): void {
    st_set($chatId, ['await' => 'helpadd_title']);
    send_or_edit($chatId, '📚 عنوان آموزش را بفرست:');
}

/** helpedit:<id> — ویرایش متن آموزش (کپی main.py 1877-1892). */
function admin_help_edit(int $chatId, int $tid): void {
    $st = db()->prepare('SELECT * FROM guide_topics WHERE id=?');
    $st->execute([$tid]);
    $t = $st->fetch();
    if (!$t) { send_or_edit($chatId, 'آموزش یافت نشد'); return; }
    st_set($chatId, ['await' => 'helpedit_body:' . $tid]);
    $cur = (string)$t['content'];
    if (mb_strlen($cur) > 2500) { $cur = mb_substr($cur, 0, 2500); }
    send_or_edit($chatId,
        "✏️ ویرایش آموزش «{$t['title']}»\n\n📄 متن فعلی:\n{$cur}\n\n✍️ متن جدید را بفرست:",
        ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]]);
}

/** helpdel:<id> — حذف آموزش (کپی main.py 1912-1927). */
function admin_help_delete(int $chatId, int $tid): void {
    db()->prepare('DELETE FROM guide_topics WHERE id=?')->execute([$tid]);
    admin_guide_home($chatId);
}

/** helpadd_title state (کپی main.py 3811-3813). */
function admin_help_title_apply(int $chatId, string $text): void {
    st_set($chatId, ['await' => 'helpadd_body', 'htitle' => trim($text)]);
    send_or_edit($chatId, '📚 توضیحات آموزش را بفرست (متن/لینک/فیلم):');
}

/** helpadd_body state (کپی main.py 3815-3825). */
function admin_help_body_apply(int $chatId, string $text): void {
    $title = (string)st_get($chatId, 'htitle', 'آموزش');
    st_pop($chatId);
    db()->prepare('INSERT INTO guide_topics(title, content) VALUES(?,?)')->execute([$title, $text]);
    send_or_edit($chatId, "✅ آموزش «{$title}» اضافه شد.");
}

/** helpedit_body:<id> state (کپی main.py 3802-3810). */
function admin_help_body_edit(int $chatId, string $await, string $text): void {
    $tid = (int)substr($await, strlen('helpedit_body:'));
    st_pop($chatId);
    db()->prepare('UPDATE guide_topics SET content=? WHERE id=?')->execute([$text, $tid]);
    $st = db()->prepare('SELECT title FROM guide_topics WHERE id=?');
    $st->execute([$tid]);
    $t = $st->fetch();
    send_or_edit($chatId, '✅ آموزش «' . ($t['title'] ?? '?') . '» به‌روزرسانی شد.');
}
