<?php
/**
 * admin/users.php — کپی مو‌به‌موی پایتون:
 * adm:users منو (main.py 2590-2602)، finduser (1852-1854, 3609+)،
 * کارت پروفایل _user_profile_card، user_manage_kb (ui.py 456-468)،
 * um: actions (2631-2679): addbal/subbal/off/on/ban/msg/orders/pays + umrepl.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';

/** Exact copy of adm:users menu (main.py 2590-2602). */
function admin_users_home(int $chatId): void {
    $n = (int)db()->query('SELECT COUNT(*) c FROM users')->fetch()['c'];
    send_or_edit($chatId,
        "👥 <b>مدیریت کاربران</b>\n\nتعداد کاربران: $n\n\nیکی از گزینه‌های زیر را انتخاب کن:",
        ['inline_keyboard' => [
            [['text' => '👤 جستجو کاربر', 'callback_data' => 'adm:finduser'],
             ['text' => '🛍 جستجو سفارش', 'callback_data' => 'adm:search']],
            [['text' => '💰 شارژ همگانی', 'callback_data' => 'adm:massbal'],
             ['text' => '📉 کسر همگانی', 'callback_data' => 'adm:masssub']],
            [['text' => '📣 پیام همگانی', 'callback_data' => 'adm:bcast']],
            [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']],
        ]]);
}

/** Exact copy of finduser prompt (main.py 1852-1854). */
function admin_finduser_start(int $chatId): void {
    st_set($chatId, ['await' => 'finduser']);
    send_or_edit($chatId, '🔍 آیدی عددی کاربر را بفرست:');
}

/** adm:search — جستجو سفارش (کپی main.py 2585-2590). */
function admin_findorder_start(int $chatId): void {
    st_set($chatId, ['await' => 'search_order']);
    send_or_edit($chatId, '👁‍🗨 برای مشاهده سفارشات کاربر، آیدی عددی یا نام کاربری کانفیگ را ارسال کنید:');
}

/** search_order state (کپی main.py 3586-3603): id/username → آخرین ۵ سفارش. */
function admin_search_order_apply(int $chatId, string $text): void {
    st_pop($chatId);
    $q = trim($text);
    if ($q === '') { send_or_edit($chatId, '❌ آیدی یا نام کاربری را بفرست:'); return; }
    // جستجو بین سرویس‌های پنلی ثبت‌شده: آیدی عددی دقیق یا شامل نام کاربری
    $st = db()->prepare('SELECT * FROM agent_panels WHERE tg_id = ? OR panel_username LIKE ? ORDER BY id DESC LIMIT 20');
    $st->execute([ctype_digit($q) ? (int)$q : -1, '%' . $q . '%']);
    $rows = $st->fetchAll();
    if (!$rows) {
        send_or_edit($chatId, 'سفارشی یافت نشد', ['inline_keyboard' => [[['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']]]]);
        return;
    }
    if (count($rows) === 1) {
        admin_svc_view($chatId, (int)$rows[0]['id']);
        return;
    }
    // چند سرویس: جدول انتخاب (کپی قالب اسکرین‌شات: نام کاربری | وضعیت سرویس | عملیات)
    $kb = ['inline_keyboard' => []];
    foreach ($rows as $r) {
        $stat = ($r['status'] ?? '') === 'active' ? 'active' : 'Unsuccessful';
        $kb['inline_keyboard'][] = [
            ['text' => "👤 {$r['panel_username']}", 'callback_data' => 'svcnoop'],
            ['text' => "📊 {$stat}", 'callback_data' => 'svcnoop'],
            ['text' => '🔍 مشاهده اطلاعات', 'callback_data' => "svcview:{$r['id']}"],
        ];
    }
    $kb['inline_keyboard'][] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId,
        "⚠️ بیشتر از یک سرویس یافت شد — از لیست زیر سرویس صحیح را انتخاب کنید:\n\n"
        . "👤 نام کاربری | 📊 وضعیت سرویس | ⚙️ عملیات",
        $kb);
}

/** svcview:<id> — order card (Reza template, python override). */
function admin_svc_view(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=?');
    $st->execute([$svcId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'سرویس یافت نشد'); return; }
    // آخرین خریدِ همین سرویس (یوزرنیم پنل)
    $pst = db()->prepare('SELECT * FROM purchases WHERE panel_username=? ORDER BY id DESC LIMIT 1');
    $pst->execute([(string)$s['panel_username']]);
    $pur = $pst->fetch();
    // شماره سفارش: ۸ کاراکتر اول md5 یوزرنیم (پایدار)
    $orderNo = substr(md5((string)$s['panel_username']), 0, 8);
    // موقعیت سرویس: نام نمایشی پنل از تنظیمات
    $loc = (string)$s['panel_name'];
    foreach (get_setting('panels', []) as $pn => $pd) {
        if (($pd['base_url'] ?? '') === $loc) { $loc = $pn; break; }
    }
    $price = $pur ? (int)$pur['price'] : 0;
    $dur = '—';
    if ($pur && $pur['months']) $dur = ((int)$pur['months'] * 30) . ' روزه';
    $prod = $s['is_test'] ? '🧪 سرویس تست' : '—';
    if ($pur) {
        $prod = '🇩🇪 نگهداری حساب | یک‌ماهه | ' . number_format($price) . ' تومان ⚡';
    }
    $created = jdate((string)$s['created_at']);
    send_or_edit($chatId,
        "🛒 شماره سفارش : <code>{$orderNo}</code>\n"
        . "🛒 وضعیت سفارش در ربات : {$s['status']}\n"
        . "🧑 شناسه کاربر : <code>{$s['tg_id']}</code>\n"
        . "👤 نام کاربری اشتراک : <code>{$s['panel_username']}</code>\n"
        . "📍 موقعیت سرویس : {$loc}\n"
        . "🛍 نام محصول : {$prod}\n"
        . "💰 قیمت پرداختی سرویس : " . number_format($price) . " تومان\n"
        . "⚜️ حجم سرویس خریداری شده : " . fmt_gb($s['quota_gb']) . " گیگابایت\n"
        . "⏳ زمان سرویس خریداری شده : {$dur}\n"
        . "📅 تاریخ خرید : {$created}",
        ['inline_keyboard' => [
            [['text' => '♻️ بروزرسانی', 'callback_data' => "svcview:{$s['id']}"]],
            [['text' => '❌ حذف سفارش', 'callback_data' => "svcordel:{$s['id']}"], ['text' => '❌ حذف سفارش و بازگشت مبلغ', 'callback_data' => "svcrefund:{$s['id']}"]],
            [['text' => '🗑 حذف کامل سرویس', 'callback_data' => "svcfulldel:{$s['id']}"]],
            [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']],
        ]]);
}

/** svcordel:<id> — حذف فقط رکورد سفارش. */
function admin_svc_orderdel(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=?');
    $st->execute([$svcId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'سرویس یافت نشد'); return; }
    db()->prepare('DELETE FROM purchases WHERE panel_username=?')->execute([(string)$s['panel_username']]);
    send_or_edit($chatId, '✅ سفارش حذف شد (سرویس پنل دست‌نخورده ماند).', ['inline_keyboard' => [[['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']]]]);
}

/** svcrefund:<id> — حذف سفارش + بازگشت مبلغ به کیف کاربر. */
function admin_svc_refund(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=?');
    $st->execute([$svcId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'سرویس یافت نشد'); return; }
    $pst = db()->prepare("SELECT * FROM purchases WHERE panel_username=? AND status='active' ORDER BY id DESC LIMIT 1");
    $pst->execute([(string)$s['panel_username']]);
    $pur = $pst->fetch();
    if ($pur) {
        db()->prepare('UPDATE users SET balance = balance + ? WHERE tg_id=?')->execute([(int)$pur['price'], (int)$s['tg_id']]);
        db()->prepare('DELETE FROM purchases WHERE id=?')->execute([(int)$pur['id']]);
        tg_send((int)$s['tg_id'], '💳 مبلغ ' . number_format((int)$pur['price']) . ' تومان به کیف پولت برگشت داده شد.');
    }
    db()->prepare('DELETE FROM agent_panels WHERE id=?')->execute([$svcId]);
    send_or_edit($chatId, '✅ سفارش حذف و مبلغ به کیف کاربر برگشت داده شد.', ['inline_keyboard' => [[['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']]]]);
}

/** svcfulldel:<id> — حذف کامل: پنل + DB. */
function admin_svc_fulldel(int $chatId, int $svcId): void {
    $st = db()->prepare('SELECT * FROM agent_panels WHERE id=?');
    $st->execute([$svcId]);
    $s = $st->fetch();
    if (!$s) { send_or_edit($chatId, 'سرویس یافت نشد'); return; }
    $panel = panel_client((string)$s['panel_name'], (string)($s['panel_type'] ?: 'pasarguard'));
    if ($panel) panel_bridge_call($panel, 'delete_admin', ['username' => (string)$s['panel_username']]);
    db()->prepare('DELETE FROM agent_panels WHERE id=?')->execute([$svcId]);
    db()->prepare('DELETE FROM purchases WHERE panel_username=?')->execute([(string)$s['panel_username']]);
    send_or_edit($chatId, '✅ سرویس کامل حذف شد (پنل + ربات).');
}
/** finduser state apply (main.py 3609+): id → open profile card. */
function admin_finduser_apply(int $chatId, string $text): void {
    st_pop($chatId);
    $uid = ctype_digit(trim($text)) ? (int)trim($text) : 0;
    if (!$uid) {
        st_set($chatId, ['await' => 'finduser']);
        send_or_edit($chatId, '❌ آیدی عددی معتبر بفرست:');
        return;
    }
    admin_user_card($chatId, $uid);
}

/** جلو-کد معرف: f"{tg_id % 36**12:0<12}"[:12] (main.py). */
function user_ref_code(int $tgId): string {
    $code = (string)($tgId % (36 ** 12));
    return str_pad(substr($code, 0, 12), 12, '0');
}

/** Exact copy of _user_profile_card (main.py). */
function admin_user_card(int $chatId, int $tg): void {
    $st = db()->prepare('SELECT * FROM users WHERE tg_id=?');
    $st->execute([$tg]);
    $u = $st->fetch();
    if (!$u) { send_or_edit($chatId, 'کاربر یافت نشد'); return; }

    $buys = db()->prepare('SELECT price, created_at FROM purchases WHERE tg_id=?');
    $buys->execute([$tg]);
    $buys = $buys->fetchAll();
    $recs = db()->prepare('SELECT amount, status FROM receipts WHERE tg_id=?');
    $recs->execute([$tg]);
    $recs = $recs->fetchAll();
    $pq = db()->prepare('SELECT COUNT(*) c FROM agent_panels WHERE tg_id=?');
    $pq->execute([$tg]);
    $panelsN = (int)$pq->fetch()['c'];

    $now = time();
    $hBuys = []; $mBuys = [];
    foreach ($buys as $b) {
        $ts = strtotime((string)$b['created_at']);
        if ($ts === false) continue;
        $age = $now - $ts;
        if ($age <= 3600) $hBuys[] = $b;
        if ($age <= 30 * 86400) $mBuys[] = $b;
    }
    $nBuys = count($buys);
    $sumPaid = 0;
    foreach ($recs as $r) if (($r['status'] ?? '') === 'approved') $sumPaid += (int)($r['amount'] ?? 0);
    $sumBuys = array_sum(array_map(fn($b) => (int)($b['price'] ?? 0), $buys));
    $sumH = array_sum(array_map(fn($b) => (int)($b['price'] ?? 0), $hBuys));
    $sumM = array_sum(array_map(fn($b) => (int)($b['price'] ?? 0), $mBuys));
    $code = user_ref_code($tg);

    $txt = "👀 <b>اطلاعات کاربر:</b>\n\n"
        . "🔗 <b>اطلاعات کاربری کاربر</b>\n"
        . "⭕️ وضعیت کاربر : " . ($u['is_banned'] ? 'Banned' : 'Active') . "\n"
        . '⭕️ نام کاربری کاربر : @' . ($u['username'] ?: 'NOT_USERNAME') . "\n"
        . "⭕️ آیدی عددی کاربر : <code>{$u['tg_id']}</code>\n"
        . "⭕️ کد معرف کاربر : <code>$code</code>\n"
        . '⭕️ زمان عضویت کاربر : ' . jdate($u['created_at']) . "\n\n"
        . "⭕️ تعداد زیرمجموعه کاربر : 0\n\n"
        . "💎 <b>گزارشات مالی</b>\n"
        . '🔰 موجودی کاربر : ' . ($u['balance'] ?: 0) . "\n"
        . "🔰 تعداد خرید کل کاربر : $nBuys\n"
        . "🔰 مبلغ کل پرداختی  : $sumPaid\n"
        . "🔰 جمع کل خرید : $sumBuys\n"
        . '🔰 تعداد فروش یک ساعت گذشته : ' . count($hBuys) . " عدد\n"
        . "🔰 مجموع فروش یک ساعت گذشته : $sumH تومان\n"
        . '🔰 تعداد فروش یک ماه گذشته : ' . count($mBuys) . " عدد\n"
        . "🔰 مجموع فروش یک ماه گذشته : $sumM تومان\n\n"
        . "🛡 تعداد پنل‌های فعال کاربر : $panelsN";

    send_or_edit($chatId, $txt, user_manage_kb($u));
}

/** Exact copy of ui.user_manage_kb() (ui.py 456-468). */
function user_manage_kb(array $u): array {
    $tg = (int)$u['tg_id'];
    $ban = $u['is_banned'] ? '🔓 رفع مسدودی' : '🔒 مسدود کردن';
    return ['inline_keyboard' => [
        [['text' => '👆 افزایش موجودی', 'callback_data' => "um:addbal:$tg"],
         ['text' => '👇 کاهش موجودی', 'callback_data' => "um:subbal:$tg"]],
        [['text' => '💡 خاموش کردن اکانت', 'callback_data' => "um:off:$tg"],
         ['text' => '💡 روشن کردن اکانت', 'callback_data' => "um:on:$tg"]],
        [['text' => '🛍 سفارشات کاربر', 'callback_data' => "um:orders:$tg"],
         ['text' => '💰 پرداختی‌های کاربر', 'callback_data' => "um:pays:$tg"]],
        [['text' => $ban, 'callback_data' => "um:ban:$tg"]],
        [['text' => '✉️ ارسال پیام به کاربر', 'callback_data' => "um:msg:$tg"]],
        [['text' => '♻️ بروزرسانی', 'callback_data' => "um:info:$tg"]],
    ]];
}

/** um: actions router — کپی main.py 2631-2679. */
function admin_user_action(int $chatId, string $data): void {
    $parts = explode(':', $data);
    if (count($parts) === 2) { $act = 'info'; $tg = (int)$parts[1]; }
    else { $act = $parts[1]; $tg = (int)$parts[2]; }

    $st = db()->prepare('SELECT * FROM users WHERE tg_id=?');
    $st->execute([$tg]);
    $u = $st->fetch();
    if (!$u) { send_or_edit($chatId, 'کاربر یافت نشد'); return; }

    if ($act === 'info') { admin_user_card($chatId, $tg); return; }
    if ($act === 'addbal' || $act === 'subbal') {
        st_set($chatId, ['await' => "um:$act", 'target' => $tg]);
        send_or_edit($chatId, 'مبلغ را به تومان بفرست:');
        return;
    }
    if ($act === 'off' || $act === 'on' || $act === 'ban') {
        // پاریتی پایتون (main.py 2641-2648): پس از تاگل، کارت پروفایل درجا رفرش می‌شود
        if ($act === 'off') { db()->prepare('UPDATE users SET is_banned=1 WHERE tg_id=?')->execute([$tg]); }
        elseif ($act === 'on') { db()->prepare('UPDATE users SET is_banned=0 WHERE tg_id=?')->execute([$tg]); }
        else { db()->prepare('UPDATE users SET is_banned=? WHERE tg_id=?')->execute([$u['is_banned'] ? 0 : 1, $tg]); }
        admin_user_card($chatId, $tg);
        return;
    }
    if ($act === 'msg') {
        st_set($chatId, ['await' => 'um:msg_pending', 'target' => $tg]);
        send_or_edit($chatId, '❓ آیا کاربر بتواند به این پیام جواب بدهد؟',
            ['inline_keyboard' => [[
                ['text' => '✅ بله', 'callback_data' => "umrepl:yes:$tg"],
                ['text' => '❌ خیر', 'callback_data' => "umrepl:no:$tg"],
            ]]]);
        return;
    }
    if ($act === 'orders') {
        // فرمان رضا: «دکمه سفارشات هم باید مثل جستجوی سفارش باشه» — لیست سرویس‌های پنلی کاربر با جدول ۳ ستونه
        $q = db()->prepare('SELECT id, panel_username, status FROM agent_panels WHERE tg_id=? ORDER BY id DESC LIMIT 20');
        $q->execute([$tg]);
        $rows = $q->fetchAll();
        if (!$rows) {
        send_or_edit($chatId, 'سفارشی یافت نشد', ['inline_keyboard' => [[['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']]]]);
        return;
    }
        if (count($rows) === 1) {
            admin_svc_view($chatId, (int)$rows[0]['id']);
            return;
        }
        $kb = ['inline_keyboard' => []];
        foreach ($rows as $r) {
            $stat = ($r['status'] ?? '') === 'active' ? 'active' : 'Unsuccessful';
            $kb['inline_keyboard'][] = [
                ['text' => "👤 {$r['panel_username']}", 'callback_data' => 'svcnoop'],
                ['text' => "📊 {$stat}", 'callback_data' => 'svcnoop'],
                ['text' => '🔍 مشاهده اطلاعات', 'callback_data' => "svcview:{$r['id']}"],
            ];
        }
        send_or_edit($chatId,
            "⚠️ سفارشات کاربر — از لیست زیر سرویس موردنظر را انتخاب کنید:\n\n"
            . "👤 نام کاربری | 📊 وضعیت سرویس | ⚙️ عملیات",
            $kb);
        return;
    }
    if ($act === 'pays') {
        $q = db()->prepare('SELECT id, amount, status FROM receipts WHERE tg_id=? ORDER BY id DESC LIMIT 15');
        $q->execute([$tg]);
        $rows = $q->fetchAll();
        $txt = implode("\n", array_map(fn($r) => "💳 #{$r['id']} — " . fmt_price((int)$r['amount']) . " — {$r['status']}", $rows));
        $tot = db()->prepare("SELECT COALESCE(SUM(amount),0) s FROM receipts WHERE tg_id=? AND status='approved'");
        $tot->execute([$tg]);
        $total = (int)$tot->fetch()['s'];
        send_or_edit($chatId, ($txt ?: 'پرداختی نیست') . "\n\n💰 جمع پرداخت‌های تاییدشده: " . fmt_price($total));
        return;
    }
}

/** umrepl:<yes|no>:<tg> (main.py 2682-2690). */
function admin_umrepl(int $chatId, string $data): void {
    $parts = explode(':', $data); // umrepl, yes/no, tg
    $st = st_all($chatId);
    if (($st['await'] ?? '') !== 'um:msg_pending') { send_or_edit($chatId, 'جلسه منقضی شد'); return; }
    st_set($chatId, ['allow_reply' => ($parts[1] === 'yes') ? 1 : 0, 'await' => 'um:msg']);
    send_or_edit($chatId, '✉️ متن پیام برای کاربر را بفرست:');
}

/** um:msg apply (پایتون main.py 3865-3874 parity): پیام با دکمهٔ پاسخ در صورت اجازه. */
function admin_um_msg_apply(int $chatId, string $text): void {
    $st = st_all($chatId);
    st_pop($chatId);
    $tg = (int)($st['target'] ?? 0);
    if (!$tg) { send_or_edit($chatId, 'هدف نامعتبر.'); return; }
    $allowReply = !empty($st['allow_reply']);
    $kb = $allowReply
        ? ['inline_keyboard' => [[['text' => '✉️ پاسخ', 'callback_data' => "um:msg:$tg"]]]]
        : null;
    $ok = tg_send($tg, "📨 پیام از پشتیبانی:

" . $text, $kb);
    if (!empty($ok['ok'])) {
        send_or_edit($chatId, '✅ پیام ارسال شد.' . ($allowReply ? ' (کاربر می‌تواند پاسخ دهد)' : ''));
    } else {
        send_or_edit($chatId, '❌ ارسال نشد (احتمالا کاربر ربات را استارت نکرده).');
    }
}

/** um:addbal / um:subbal apply (main.py 2643-2645 parity). */
function admin_um_bal_apply(int $chatId, string $text): void {
    $await = (string)st_get($chatId, 'await', '');
    $tg = (int)st_get($chatId, 'target', 0); // پایتون target را قبل از pop می‌خواند (main.py 3853)
    st_pop($chatId);
    if (!preg_match('/(\d+)/', str_replace(',', '', $text), $m2)) {
        send_or_edit($chatId, 'عدد معتبر بفرست.');
        return;
    }
    $val = (int)$m2[1];
    if (!$tg) { send_or_edit($chatId, '❌ عدد معتبر بفرست:'); return; }
    if ($await === 'um:addbal') {
        add_balance($tg, $val);
        send_or_edit($chatId, '✅ انجام شد — موجودی جدید کاربر ' . $tg . ': ' . fmt_price(get_balance($tg)));
    } else {
        db()->prepare('UPDATE users SET balance = MAX(0, balance - ?) WHERE tg_id=?')->execute([$val, $tg]);
        send_or_edit($chatId, '✅ انجام شد — موجودی جدید کاربر ' . $tg . ': ' . fmt_price(get_balance($tg)));
    }
}

/** شارژ/کسر همگانی (main.py 1856-1859, 2625-2628). */
function admin_massbal_start(int $chatId, string $kind): void {
    st_set($chatId, ['await' => $kind === 'add' ? 'massbal' : 'mass_sub']);
    if ($kind === 'add') send_or_edit($chatId, '👥 مبلغ شارژ همگانی را به تومان بفرست (به همه کاربران اضافه می‌شود):');
    else send_or_edit($chatId, '📉 مبلغ کسر همگانی را به تومان بفرست (از موجودی همه کاربران کم می‌شود):');
}

function admin_massbal_apply(int $chatId, string $text): void {
    $await = (string)st_get($chatId, 'await', '');
    st_pop($chatId);
    $val = (int)preg_replace('/[^\d]/', '', $text);
    if (!$val) { send_or_edit($chatId, '❌ عدد معتبر بفرست:'); return; }
    if ($await === 'massbal') {
        db()->prepare('UPDATE users SET balance = balance + ?')->execute([$val]);
        send_or_edit($chatId, '✅ شارژ همگانی انجام شد.');
    } else {
        db()->prepare('UPDATE users SET balance = MAX(0, balance - ?)')->execute([$val]);
        send_or_edit($chatId, '✅ کسر همگانی انجام شد.');
    }
}
