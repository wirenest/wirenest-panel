<?php
/**
 * admin/receipts.php — کپی مو‌به‌موی پایتون:
 * صف رسیدها (main.py 1949-1965)، دکمه‌های بررسی (ui.py 471-476)،
 * rcok/rcno (main.py 2878-2891)، rcfix (1928-1931)، my receipts.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/flows/wallet.php';

/** Exact copy of ui.receipts_kb() — the notification kb sent to admins on new receipt. */
function receipts_kb(int $rid): array {
    return ['inline_keyboard' => [[
        ['text' => '✅ تایید', 'callback_data' => "rcok:$rid"],
        ['text' => '❌ رد', 'callback_data' => "rcno:$rid"],
    ]]];
}

/** Exact copy of ui.receipt_review_kb() — the queue review kb (4 buttons incl. edit-amount). */
function receipt_review_kb(int $rid): array {
    return ['inline_keyboard' => [
        [['text' => '⚡ تایید با همان مبلغ', 'callback_data' => "rcok:$rid"],
         ['text' => '✏️ ویرایش مبلغ و تایید', 'callback_data' => "rcfix:$rid"]],
        [['text' => '❌ رد درخواست', 'callback_data' => "rcno:$rid"]],
    ]];
}

/** Exact copy of adm:receipts queue (main.py 1949-1965). */
function admin_receipts_queue(int $chatId): void {
    $recs = db()->query("SELECT id, tg_id, amount, ref_text FROM receipts WHERE status='pending' ORDER BY id")->fetchAll();
    if (!$recs) {
        send_or_edit($chatId, '🧾 در انتظار تاییدی نیست.');
        return;
    }
    foreach ($recs as $r) {
        send_or_edit($chatId,
            "#{$r['id']} از {$r['tg_id']} — " . fmt_price((int)$r['amount']) . "\n"
            . '<code>' . htmlspecialchars((string)$r['ref_text']) . '</code>',
            receipt_review_kb((int)$r['id']));
    }
}

/** Exact copy of rcok/rcno (main.py 2878-2891): claim → balance → notify → resume pending buy. */
function handle_receipt_review(int $chatId, string $data): void {
    $rid = (int)explode(':', $data)[1];
    $approve = str_starts_with($data, 'rcok');
    $st = db()->prepare('SELECT * FROM receipts WHERE id=?');
    $st->execute([$rid]);
    $rec = $st->fetch();
    if (!$rec || $rec['status'] !== 'pending') { send_or_edit($chatId, 'قبلا پردازش شده'); return; }
    // claim (single-flight): only first admin wins
    $u = db()->prepare("UPDATE receipts SET status=? WHERE id=? AND status='pending'");
    $u->execute([$approve ? 'approved' : 'rejected', $rid]);
    if ($u->rowCount() === 0) { send_or_edit($chatId, 'قبلا پردازش شده'); return; }

    if ($approve) {
        add_balance((int)$rec['tg_id'], (int)$rec['amount']);
        tg_send((int)$rec['tg_id'], '✅ پرداخت ' . fmt_price((int)$rec['amount']) . ' تایید و به موجودی‌ات اضافه شد.');
        // Reza rule: اگر کاربر در فلو خرید حجم اضافه بود — تکمیل خودکار حجم اضافه با موجودی شارژشده
        $xst = st_all((int)$rec['tg_id']);
        if (($xst['xp_kind'] ?? '') === 'extragb' && !empty($xst['xp_gb'])) {
            st_pop((int)$rec['tg_id']);
            // مبلغ کل خرید از کیف پول (رسید فقط کسری را شارژ کرده) — spend قبل از اعمال روی پنل
            $xprice = (int)($xst['xp_price'] ?? 0);
            if ($xprice > 0 && !spend_balance((int)$rec['tg_id'], $xprice)) {
                tg_send((int)$rec['tg_id'], '⚠️ موجودی برای تکمیل خرید حجم اضافه کافی نشد — مبلغ در کیف پولت باقی ماند. دوباره تلاش کن.');
                return;
            }
            complete_extra_gb((int)$rec['tg_id'], (int)$xst['xp_gb'], (int)$xst['pid'], (int)($xst['xp'] ?? 0), $xprice);
            return;
        }
        // resume pending purchase invoice (topup was for a buy) — main.py 2892-2897
        if (str_starts_with((string)($rec['ref_text'] ?? ''), 'topup')) {
            $pb = db()->prepare("SELECT * FROM pending_buys WHERE tg_id=? ORDER BY id DESC LIMIT 1");
            $pb->execute([(int)$rec['tg_id']]);
            $b = $pb->fetch();
            if ($b) {
                $bal2 = get_balance((int)$rec['tg_id']);
                $pl = $b['pid'] ? db()->prepare('SELECT * FROM panel_plans WHERE id=?') : null;
                if ($pl) { $pl->execute([(int)$b['pid']]); $prow = $pl->fetch(); }
                if (!empty($prow) && $bal2 >= (float)$prow['price']) {
                    st_set((int)$rec['tg_id'], ['buy_plan' => ['pid' => (int)$prow['id'], 'gb' => (float)$prow['volume_gb'],
                                                              'price' => (int)$prow['price'], 'orig_price' => (int)$prow['price']]]);
                    tg_send((int)$rec['tg_id'],
                        "✅ موجودی کافی شد. برای پرداخت و ساخت آنی پنل بزن:",
                        ['inline_keyboard' => [[['text' => "✅ پرداخت از موجودی کیف پول (" . number_format((float)$prow['price']) . " تومان)",
                                                 'callback_data' => 'paybalplan:' . $prow['id']]]]]);
                }
            }
        }
    } else {
        tg_send((int)$rec['tg_id'], '❌ رسید شما رد شد. برای بررسی با پشتیبانی در تماس باش.');
    }
}

/** Exact copy of rcfix (main.py 1928-1931): admin edits amount then approves. */
function receipt_fix_start(int $chatId, int $rid): void {
    st_set($chatId, ['await' => "rcfix:$rid"]);
    send_or_edit($chatId, '✏️ مبلغ صحیح رسید را به تومان بفرست (تایید با این مبلغ انجام می‌شود):');
}

/** Apply rcfix amount: set amount + approve (main.py 3237 handles the await). */
function receipt_fix_apply(int $chatId, string $text): void {
    $rid = (int)substr((string)st_get($chatId, 'await', ''), 6);
    st_pop($chatId);
    $clean = (int)preg_replace('/[^\d]/', '', str_replace(',', '', $text));
    if (!$clean) { send_or_edit($chatId, '❌ فقط عدد بفرست:'); st_set($chatId, ['await' => "rcfix:$rid"]); return; }
    db()->prepare('UPDATE receipts SET amount=? WHERE id=?')->execute([$clean, $rid]);
    handle_receipt_review($chatId, "rcok:$rid");
}

/** My receipts screen — python parity (چک worked-before state). */
function my_receipts(int $chatId): void {
    $st = db()->prepare('SELECT id, amount, status, created_at FROM receipts WHERE tg_id=? ORDER BY id DESC LIMIT 10');
    $st->execute([$chatId]);
    $rows = $st->fetchAll();
    if (!$rows) { send_or_edit($chatId, 'هنوز رسیدی ثبت نکردی.'); return; }
    $statusMap = ['pending' => '⏳ در انتظار', 'approved' => '✅ تایید شده', 'rejected' => '❌ رد شده', 'deleted' => '🗑 حذف'];
    $txt = "📄 آخرین رسیدها:\n\n";
    foreach ($rows as $r) {
        $txt .= "#{$r['id']} — " . fmt_price((int)$r['amount']) . ' — ' . ($statusMap[$r['status']] ?? $r['status'])
              . ' — ' . jdate($r['created_at']) . "\n";
    }
    send_or_edit($chatId, $txt);
}
