<?php
/**
 * flows/buy.php — خرید پلن/تعرفه (کپی مو‌به‌موی main.py):
 * buyplan→confirmplan→paybalplan (239-351, 560-606) | buy→confirm→paybal (264-284, 376-409, 583-606)
 * + buy_custom_username (3911-4009) با /skip و اعتبارسنجی ۴-۱۶ کاراکتر
 * + wallet_receipt (4030-4054) + buy_receipt_ref (4063-4111) با گارد TXID ترون.
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';
require_once BASE_DIR . '/core/handlers.php'; // get_balance, spend_balance, add_balance, report_purchase

/** plan label — python: f"{vol:g} گیگ — {price:,} تومان" */
function plan_label(array $pl): string {
    $volStr = fmt_gb($pl['volume_gb']);
    return $volStr . ' گیگ — ' . number_format((float)$pl['price']) . ' تومان';
}

function handle_buy_callback(int $chatId, string $data): void {
    // ---- buyplan:<pid> → پیش‌فاکتور ساده (main.py 239-262) ----
    if (str_starts_with($data, 'buyplan:')) {
        $pid = (int)substr($data, 8);
        $st = db()->prepare('SELECT * FROM panel_plans WHERE id=?');
        $st->execute([$pid]);
        $pl = $st->fetch();
        if (!$pl || !$pl['active']) { send_or_edit($chatId, 'پلن در دسترس نیست'); return; }
        send_or_edit($chatId,
            "📇 پیش فاکتور شما:\n\n" . htmlspecialchars(plan_label($pl)) . "\n\n"
            . "⚠️ توجه: خرید پنل غیرقابل استرداد است. لطفاً قبل از پرداخت از انتخاب خود مطمئن شوید.\n\n"
            . "برای ادامه، تایید کن:",
            ['inline_keyboard' => [
                [['text' => '✅ متوجه شدم، خرید را نهایی کن', 'callback_data' => "confirmplan:$pid"]],
                [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
            ]]);
        return;
    }

    // ---- buy:<tid> → پیش‌فاکتور تعرفه (main.py 264-284) ----
    if (str_starts_with($data, 'buy:') && !str_starts_with($data, 'buyplan:')) {
        $tid = (int)substr($data, 4);
        $st = db()->prepare('SELECT * FROM tariffs WHERE id=?');
        $st->execute([$tid]);
        $t = $st->fetch();
        if (!$t || !$t['is_active']) { send_or_edit($chatId, 'تعرفه در دسترس نیست'); return; }
        $warn = (string)(get_setting('nonrefund_text', '') ?: '⚠️ توجه: خرید پنل غیرقابل استرداد است. لطفاً قبل از پرداخت از انتخاب خود مطمئن شوید.');
        send_or_edit($chatId,
            "📇 پیش فاکتور شما:\n\n" . htmlspecialchars((string)$t['title']) . "\n\n"
            . htmlspecialchars($warn) . "\n\n"
            . "برای ادامه، تایید کن:",
            ['inline_keyboard' => [
                [['text' => '✅ متوجه شدم، خرید را نهایی کن', 'callback_data' => "confirm:$tid"]],
                [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
            ]]);
        return;
    }

    // ---- confirmplan:<pid> (main.py 306-351) ----
    if (str_starts_with($data, 'confirmplan:')) {
        $pid = (int)substr($data, 12);
        $st = db()->prepare('SELECT * FROM panel_plans WHERE id=?');
        $st->execute([$pid]);
        $pl = $st->fetch();
        if (!$pl || !$pl['active']) { send_or_edit($chatId, 'پلن در دسترس نیست'); return; }
        $bal = get_balance($chatId);
        if ($bal >= (float)$pl['price']) {
            st_set($chatId, ['buy_plan' => ['pid' => $pid, 'gb' => (float)$pl['volume_gb'],
                                            'price' => (int)$pl['price'], 'orig_price' => (int)$pl['price']]]);
            send_or_edit($chatId,
                "📇 پیش فاکتور شما:\n\n" . plan_label($pl) . "\n\n"
                . "💵 موجودی کیف پول شما: " . fmt_price($bal) . "\n\n"
                . "✅ موجودی کافی است. برای پرداخت و ساخت آنی روی دکمه زیر بزنید:",
                ['inline_keyboard' => [
                    [['text' => "✅ پرداخت از موجودی کیف پول (" . number_format((float)$pl['price']) . " تومان)", 'callback_data' => "paybalplan:$pid"]],
                    [['text' => '🏷 کد تخفیف دارم', 'callback_data' => "apdc:$pid"]],
                    [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
                ]]);
            return;
        }
        st_set($chatId, ['await' => 'topup_amount',
                         'buy_plan' => ['pid' => $pid, 'gb' => (float)$pl['volume_gb'],
                                        'price' => (int)$pl['price'], 'orig_price' => (int)$pl['price']]]);
        db()->prepare('INSERT INTO pending_buys(tg_id,kind,pid,pname,gb,price) VALUES(?,?,?,?,?,?)')
           ->execute([$chatId, 'plan', $pid, (string)$pl['panel_name'], (float)$pl['volume_gb'], (int)$pl['price']]);
        send_or_edit($chatId,
            "📇 پیش فاکتور شما:\n\n" . plan_label($pl) . "\n\n"
            . "💵 موجودی کیف پول شما: " . fmt_price($bal) . "\n\n"
            . "❌ <b>موجودی کیف پولت کافی نیست!</b>\n"
            . "اول کیف پولت را شارژ کن (حداقل " . fmt_price((float)$pl['price'] - $bal) . ").",
            ['inline_keyboard' => [
                [['text' => '💳 شارژ کیف پول', 'callback_data' => 'wal:addcredit']],
                [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
            ]]);
        return;
    }

    // ---- confirm:<tid> تعرفه (main.py 352-386) ----
    if (str_starts_with($data, 'confirm:')) {
        $tid = (int)substr($data, 8);
        $st = db()->prepare('SELECT * FROM tariffs WHERE id=?');
        $st->execute([$tid]);
        $t = $st->fetch();
        if (!$t || !$t['is_active']) { send_or_edit($chatId, 'تعرفه در دسترس نیست'); return; }
        $bal = get_balance($chatId);
        if ($bal < (float)$t['price']) {
            st_set($chatId, ['await' => 'topup_amount', 'back_tariff' => $tid]);
            db()->prepare('INSERT INTO pending_buys(tg_id,kind,pid,pname,gb,price) VALUES(?,?,?,?,?,?)')
               ->execute([$chatId, 'tariff', $tid, (string)$t['title'], (float)$t['volume_gb'], (int)$t['price']]);
            send_or_edit($chatId,
                "📇 پیش فاکتور شما:\n\n" . htmlspecialchars((string)$t['title']) . "\n\n"
                . "💵 موجودی کیف پول شما: " . fmt_price($bal) . "\n\n"
                . "❌ <b>موجودی کیف پولت کافی نیست!</b>\n"
                . "اول کیف پولت را شارژ کن (حداقل " . fmt_price((float)$t['price'] - $bal) . ").",
                ['inline_keyboard' => [
                    [['text' => '💳 شارژ کیف پول', 'callback_data' => 'wal:addcredit']],
                    [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
                ]]);
            return;
        }
        st_set($chatId, ['buy_tariff' => $tid]);
        send_or_edit($chatId,
            "📇 پیش فاکتور شما:\n\n" . htmlspecialchars((string)$t['title']) . "\n\n"
            . "💵 موجودی کیف پول شما: " . fmt_price($bal) . "\n\n"
            . "✅ موجودی کافی است. برای پرداخت و ساخت آنی روی دکمه زیر بزنید:",
            ['inline_keyboard' => [
                [['text' => "✅ پرداخت از موجودی کیف پول (" . number_format((float)$t['price']) . " تومان)", 'callback_data' => "paybal:$tid"]],
                [['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']],
            ]]);
        return;
    }

    // ---- cancelbuy (main.py 291-295) ----
    if ($data === 'cancelbuy') {
        st_pop($chatId);
        tg_send($chatId, '❌ خرید لغو شد.');
        return;
    }

    // ---- apdc:<pid> کد تخفیف (main.py 296-304) ----
    if (str_starts_with($data, 'apdc:')) {
        $pid = (int)substr($data, 5);
        $bp = st_get($chatId, 'buy_plan', []);
        if (($bp['pid'] ?? null) !== $pid) { send_or_edit($chatId, 'جلسه خرید منقضی شد'); return; }
        st_set($chatId, ['await' => 'buy_discount_code']);
        send_or_edit($chatId, "🏷 کد تخفیف را بفرست (یا /cancel برای انصراف):");
        return;
    }

    // ---- paybalplan:<pid> (main.py 560-583) → درخواست یوزرنیم دلخواه ----
    if (str_starts_with($data, 'paybalplan:')) {
        $pid = (int)substr($data, 11);
        $st = db()->prepare('SELECT * FROM panel_plans WHERE id=?');
        $st->execute([$pid]);
        $pl = $st->fetch();
        if (!$pl) { send_or_edit($chatId, 'پلن نامعتبر'); return; }
        $bal = get_balance($chatId);
        $bp = st_get($chatId, 'buy_plan', []);
        $payPrice = (int)$pl['price'];
        if (($bp['pid'] ?? null) === $pid && (int)($bp['price'] ?? 0) > 0 && (int)$bp['price'] < (int)$pl['price']) {
            $payPrice = (int)$bp['price']; // discounted price restored
        }
        if ($bal < $payPrice) { send_or_edit($chatId, 'موجودی کافی نیست'); return; }
        // کپی main.py 572-581: ASK CUSTOM USERNAME (پرداخت بعد از انتخاب یوزرنیم انجام می‌شود)
        st_set($chatId, ['await' => 'buy_custom_username', 'pid' => $pid,
                         'buy_plan' => $bp ?: ['pid' => $pid, 'price' => $payPrice, 'orig_price' => (int)$pl['price']]]);
        send_or_edit($chatId,
            "👤 <b>انتخاب نام کاربری</b>\n\n"
            . "پلن: " . fmt_gb($pl['volume_gb']) . " گیگ — " . number_format($payPrice) . " تومان\n\n"
            . "لطفاً نام کاربری (Username) دلخواه خود را برای ادمین پنل بفرست\n"
            . "(یا /skip برای ساخت خودکار):",
            ['inline_keyboard' => [[['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']]]]);
        return;
    }

    // ---- paybal:<tid> تعرفه (main.py 583-606) ----
    if (str_starts_with($data, 'paybal:')) {
        $tid = (int)substr($data, 7);
        $st = db()->prepare('SELECT * FROM tariffs WHERE id=?');
        $st->execute([$tid]);
        $t = $st->fetch();
        if (!$t) { send_or_edit($chatId, 'تعرفه نامعتبر'); return; }
        $bal = get_balance($chatId);
        if ($bal < (float)$t['price']) { send_or_edit($chatId, 'موجودی کافی نیست'); return; }
        st_set($chatId, ['await' => 'buy_custom_username', 'tid' => $tid]);
        send_or_edit($chatId,
            "👤 <b>انتخاب نام کاربری</b>\n\n"
            . "تعرفه: " . htmlspecialchars((string)$t['title']) . "\n\n"
            . "لطفاً نام کاربری (Username) دلخواه خود را برای ادمین پنل بفرست\n"
            . "(یا /skip برای ساخت خودکار):",
            ['inline_keyboard' => [[['text' => '❌ انصراف', 'callback_data' => 'cancelbuy']]]]);
        return;
    }
}

/**
 * buy_custom_username — کپی کامل main.py 3911-4009:
 * /skip یا یوزرنیم ۴-۱۶ کاراکتر → چک رزرو روی پنل → کسر موجودی (با تخفیف) → ساخت → تحویل exact
 */
function handle_buy_custom_username(int $chatId, string $text): void {
    if ($text === '🏠 بازگشت به منوی اصلی') {
        st_pop($chatId);
        send_or_edit($chatId, '🏠 بازگشتید!', main_menu_kb(is_admin($chatId)));
        return;
    }
    // single-flight claim (main.py 3915-3918)
    $st = st_all($chatId);
    st_pop($chatId);

    $pid = (int)($st['pid'] ?? 0);
    $tid = (int)($st['tid'] ?? 0);
    if ($pid) {
        $q = db()->prepare('SELECT * FROM panel_plans WHERE id=?'); $q->execute([$pid]);
        $item = $q->fetch();
        $pname = $item ? (string)$item['panel_name'] : null;
    } else {
        $q = db()->prepare('SELECT * FROM tariffs WHERE id=?'); $q->execute([$tid]);
        $item = $q->fetch();
        $pname = null; // default selected panel for global tariffs
    }
    if (!$item) { st_pop($chatId); send_or_edit($chatId, 'آیتم نامعتبر.'); return; }

    // username validation (main.py 3935-3941): 4-16 chars, letter start
    if (mb_strtolower($text) === '/skip') {
        $uname = gen_username('ag');
    } else {
        $uname = trim($text);
        if (!preg_match('/^[a-zA-Z][a-zA-Z0-9_]{3,15}$/', $uname)) {
            st_set($chatId, $st); // restore for retry
            send_or_edit($chatId, '❌ نام کاربری نامعتبر! (فقط حروف و اعداد، شروع با حرف، ۴ تا ۱۶ کاراکتر)');
            return;
        }
    }

    // panel selection (main.py 3944-3949)
    $panels = get_setting('panels', []) ?: [];
    if ($pname && isset($panels[$pname])) {
        $d = $panels[$pname];
    } else {
        $sel = (string)get_setting('selected_panel', '');
        $d = $panels[$sel] ?? (reset($panels) ?: null);
    }
    if (!$d) { st_set($chatId, $st); send_or_edit($chatId, '❌ پنل یافت نشد.'); return; }
    $p = panel_client($d['base_url'] ?? null, $d['ptype'] ?? null);
    if (!$p) { st_set($chatId, $st); send_or_edit($chatId, '❌ خطا در اتصال به پنل.'); return; }

    // username availability check (main.py 3960-3967)
    $res = panel_bridge_call($p, 'list_admins', []);
    if (!empty($res['ok']) && is_array($res['data'])) {
        foreach ($res['data'] as $a) {
            if (mb_strtolower((string)($a['username'] ?? '')) === mb_strtolower($uname)) {
                st_set($chatId, $st);
                send_or_edit($chatId, "❌ نام کاربری <code>" . htmlspecialchars($uname) . "</code> قبلاً در پنل رزرو شده. یکی دیگه بفرست:");
                return;
            }
        }
    }

    // spend balance honoring discount (main.py 3969-3983)
    $payAmount = (int)$item['price'];
    $bp2 = (array)($st['buy_plan'] ?? []);
    if (($bp2['pid'] ?? null) === $pid && (int)($bp2['price'] ?? 0) > 0 && (int)$bp2['price'] < (int)$item['price']) {
        $payAmount = (int)$bp2['price'];
    }
    if (!spend_balance($chatId, $payAmount)) {
        st_pop($chatId);
        send_or_edit($chatId, '❌ موجودی کافی نیست.');
        return;
    }
    // consume discount exactly once (main.py 3977-3983)
    $disc = (array)($bp2['discount'] ?? []);
    if (!empty($disc['did']) && !empty($disc['code'])) {
        try { db()->prepare('UPDATE discount_codes SET used=used+1 WHERE id=?')->execute([(int)$disc['did']]); } catch (Throwable $e) {}
    }

    // CREATE (main.py 3986-3993): refund + restore state on failure
    $pwd = strong_password();
    $res = panel_create_admin($p, $uname, $pwd, (float)$item['volume_gb'], $chatId);
    if (empty($res['ok'])) {
        add_balance($chatId, $payAmount);
        if (!empty($disc['did'])) {
            try { db()->prepare('UPDATE discount_codes SET used = MAX(0, used - 1) WHERE id=?')->execute([(int)$disc['did']]); } catch (Throwable $e) {}
        }
        st_set($chatId, $st);
        send_or_edit($chatId, '❌ خطا در ساخت پنل. مبلغ برگشت خورد. دوباره تلاش کن.');
        return;
    }

    st_pop($chatId);
    db()->prepare('INSERT INTO purchases(tg_id,tariff_id,panel_username,volume_gb,price,status) VALUES(?,?,?,?,?,?)')
       ->execute([$chatId, $tid ?: -1, $uname, (float)$item['volume_gb'], (int)$item['price'], 'active']);
    db()->prepare('DELETE FROM pending_buys WHERE tg_id=?')->execute([$chatId]);
    db()->prepare('INSERT INTO agent_panels(tg_id,panel_username,panel_password,panel_name,panel_type,quota_gb) VALUES(?,?,?,?,?,?)')
       ->execute([$chatId, $uname, $pwd, $p['base_url'], $p['ptype'] ?? 'pasarguard', (float)$item['volume_gb']]);

    // deliver text exact (main.py 4000-4007) — آدرس از panel_login_url (با/بدون /dashboard عیناً)
    $url = panel_login_url((string)$p['base_url']);
    // فرمت حجم: 100 → «100» / 0.5 → «0.5» (rtrim قبلی «100» را به «1» خراب می‌کرد!)
    $quotaStr = (floor((float)$item['volume_gb']) == (float)$item['volume_gb'])
        ? (string)(int)(float)$item['volume_gb']
        : rtrim(rtrim(number_format((float)$item['volume_gb'], 2, '.', ''), '0'), '.');
    report_purchase($chatId, $uname, fmt_gb((float)$item['volume_gb']) . ' گیگ — ' . number_format((int)$item['price']) . ' تومان', (int)$payAmount, 'خرید', $url);

    send_or_edit($chatId,
        "✅ <b>خرید و ساخت پنل با موفقیت انجام شد!</b>\n\n"
        . "🌐 آدرس ورود: <code>" . htmlspecialchars($url) . "</code>\n"
        . "👤 نام کاربری: <code>" . htmlspecialchars($uname) . "</code>\n"
        . "🔑 رمز عبور: <code>" . htmlspecialchars($pwd) . "</code>\n\n"
        . "📦 سهمیه: {$quotaStr} گیگ\n"
        . "💵 کسر شده از کیف پول: " . fmt_price($payAmount),
        main_menu_kb(is_admin($chatId)));
}

/** buy_discount_code state — کد تخفیف اعمال شود روی buy_plan.price (پایتون parity). */
function handle_buy_discount_code(int $chatId, string $text): void {
    $st = st_all($chatId);
    st_pop($chatId);
    $code = trim($text);
    // parity with gift_codes validation: max_uses + expiry enforced at entry (audit fix)
    $d = db()->prepare("SELECT * FROM discount_codes WHERE code=? AND active=1
                        AND (max_uses=0 OR used < max_uses)
                        AND (expires_at IS NULL OR expires_at = '' OR expires_at > datetime('now','localtime'))");
    $d->execute([$code]);
    $dc = $d->fetch();
    if (!$dc) {
        st_set($chatId, $st);
        send_or_edit($chatId, '❌ کد تخفیف نامعتبر است. دوباره بفرست یا /cancel:');
        return;
    }
    $bp = (array)($st['buy_plan'] ?? []);
    $price = (int)($bp['orig_price'] ?? $bp['price'] ?? 0);
    if ((string)$dc['kind'] === 'percent') {
        $newPrice = (int)round($price * (1 - ((float)$dc['value'] / 100)));
    } else {
        $newPrice = max(0, $price - (int)$dc['value']);
    }
    $bp['price'] = $newPrice;
    $bp['discount'] = ['did' => (int)$dc['id'], 'code' => $code];
    $st['buy_plan'] = $bp;
    st_set($chatId, $st);
    send_or_edit($chatId, "✅ کد تخفیف اعمال شد: " . fmt_price($newPrice));
}

/** wallet_receipt state — کد پیگیری متنی (main.py 4030-4054). */
function handle_wallet_receipt_text(int $chatId, string $text): void {
    $amount = (int)st_get($chatId, 'amount', 0);
    if (!$amount) {
        st_pop($chatId);
        st_set($chatId, ['await' => 'topup_amount']);
        send_or_edit($chatId, '❌ مبلغ شارژ مشخص نیست. اول مبلغ را بفرست (مثلاً: 100000).');
        return;
    }
    // Reza rule: سشن حجم اضافه (xp_kind=extragb) باید بعد از ثبت رسید زنده بماند تا در تایید، تکمیل خودکار انجام شود
    $keepXp = [];
    if ((string)st_get($chatId, 'xp_kind', '') === 'extragb') {
        $keepXp = ['xp_kind' => 'extragb', 'xp_gb' => st_get($chatId, 'xp_gb'),
                   'xp_price' => st_get($chatId, 'xp_price'), 'xp' => st_get($chatId, 'xp'),
                   'pid' => st_get($chatId, 'pid'), 'await' => 'idle'];
    }
    st_pop($chatId);
    if ($keepXp) st_set($chatId, $keepXp);
    // Reza rule: TXID replay guard — a tron TXID (>=20 chars) may only ever be submitted once (parity main.py 4093-4097)
    $ref = trim($text);
    if (mb_strlen($ref) >= 20 && receipt_ref_exists($ref)) {
        send_or_edit($chatId, '⛔️ این TXID قبلاً ثبت شده است — هر تراکنش فقط یک‌بار قابل استفاده است.');
        return;
    }
    $rid = create_receipt($chatId, $amount, 'topup | ' . mb_substr($text, 0, 200));
    send_or_edit($chatId, '✅ رسید شارژ ثبت شد و در انتظار تایید ادمین است.', main_menu_kb(is_admin($chatId)));
    notify_admins(
        "💳 رسید شارژ کیف پول #$rid\nاز: <a href='tg://user?id=$chatId'>$chatId</a>\n"
        . 'مبلغ: ' . fmt_price($amount) . "\nکد/پیگیری: <code>" . htmlspecialchars(mb_substr($text, 0, 200)) . '</code>',
        receipt_review_kb($rid));
}
