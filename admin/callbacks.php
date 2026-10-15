<?php
/**
 * admin/callbacks.php — the callback router: dispatches every inline button (parity با on_admin_cb/on_service_cb/... پایتون)
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';
require_once BASE_DIR . '/flows/buy.php';
require_once BASE_DIR . '/flows/wallet.php';
require_once BASE_DIR . '/flows/services.php';
require_once BASE_DIR . '/admin/receipts.php';
require_once BASE_DIR . '/admin/users.php';
require_once BASE_DIR . '/admin/bcast.php';
require_once BASE_DIR . '/admin/settings.php';
require_once BASE_DIR . '/admin/payments.php';
require_once BASE_DIR . '/admin/panels.php';
require_once BASE_DIR . '/admin/panel_extra.php';
require_once BASE_DIR . '/admin/misc.php';
require_once BASE_DIR . '/admin/stats.php';
require_once BASE_DIR . '/admin/discounts.php';
require_once BASE_DIR . '/admin/features.php';

function handle_callback(array $cq): void {
    $chatId = (int)$cq['from']['id'];
    $data = (string)($cq['data'] ?? '');
    $msgId = (int)($cq['message']['message_id'] ?? 0);
    ctx_msg_id_set($msgId);
    tg('answerCallbackQuery', ['callback_query_id' => $cq['id']]);

    $admin = is_admin($chatId);

    // --- public flows ---
    if (str_starts_with($data, 'buyplan:') || str_starts_with($data, 'confirmplan:')
        || str_starts_with($data, 'paybalplan:') || str_starts_with($data, 'apdc:')
        || str_starts_with($data, 'confirm:') || str_starts_with($data, 'paybal:')
        || (str_starts_with($data, 'buy:') && !str_starts_with($data, 'buyplan:'))
        || $data === 'cancelbuy') { handle_buy_callback($chatId, $data); return; }

    if ($data === 'm:home') { st_pop($chatId); send_or_edit($chatId, '🏠 منوی اصلی:', main_menu_kb($admin)); return; }
    if ($data === 'm:buy')  { show_buy_screen($chatId); return; }
    if ($data === 'm:services') { services_home($chatId); return; }
    if ($data === 'topup')  { start_topup($chatId); return; }
    if ($data === 'myreceipts') { my_receipts($chatId); return; }
    if ($data === 'm:tkt') { // ✉️ ارسال پیام — پایتون main.py 4270-4272: مستقیم پرامپت بده (صفحهٔ پشتیبانی دوباره باز نشود)
        st_set($chatId, ['await' => 'support_msg']);
        tg_send($chatId, '✍️ پیامت را بنویس (ارسال به پشتیبانی):');
        return;
    }
    if ($data === 'wal:addcredit') { wallet_add_credit($chatId); return; }
    if ($data === 'wal:receipts') { my_receipts($chatId); return; }
    if ($data === 'wal:receipt') {
        // python parity: «ارسال کردم» → منتظر کد پیگیری/عکس رسید (main.py 1238-1249)
        // فرمان رضا: پیام اطلاعات کارت/مبلغ باید پاک/جایگزین بشه — فقط پرامپت ارسال رسید بمونه
        st_set($chatId, ['await' => 'wallet_receipt']);
        send_or_edit($chatId, '✉️ کد پیگیری واریز را بفرست (یا عکس رسید):');
        return;
    }
    if ($data === 'cancelbuy') { st_pop($chatId); tg_send($chatId, '❌ خرید لغو شد.'); return; }

    // Reza rule: فاکتور حجم اضافه — تایید/لغو (مسیر عمومی کاربر)
    if (str_starts_with($data, 'xgpay:')) {
        require_once BASE_DIR . '/flows/extra_gb.php';
        [, $xpid, $xgb, $xprice] = array_pad(explode(':', $data), 4, 0);
        extra_gb_invoice_confirm($chatId, (int)$xpid, (int)$xgb, (int)$xprice);
        return;
    }
    if ($data === 'xgcancel') {
        require_once BASE_DIR . '/flows/extra_gb.php';
        extra_gb_invoice_cancel($chatId);
        return;
    }

    if (str_starts_with($data, 'guide:')) {
        // پاریتی main.py 1275-1285 + ui.guide_back_kb: guide:<id> → guide_topics.content + دکمه‌های بازگشت
        $gid = (int)substr($data, 6);
        $topic = db()->prepare('SELECT content FROM guide_topics WHERE id=? LIMIT 1');
        $topic->execute([$gid]);
        $t = $topic->fetch();
        send_or_edit($chatId, $t ? (string)$t['content'] : 'راهنمایی ثبت نشده.',
            ['inline_keyboard' => [
                [['text' => '◀️ بازگشت به لیست پلتفرم‌ها', 'callback_data' => 'm:help']],
                [['text' => '🏠 منوی اصلی', 'callback_data' => 'm:home']],
            ]]);
        return;
    }

    if (str_starts_with($data, 'apchpw:')) { service_change_password_start($chatId, (int)substr($data, 7)); return; }
    if (str_starts_with($data, 'svc:')) {
        $parts = explode(':', $data); // svc:<id> | svc:<id>:<action>
        $svcId = (int)$parts[1];
        if (count($parts) === 2) { service_screen($chatId, $svcId); return; }
        $act = $parts[2];
        if ($act === 'info') { service_login_info($chatId, $svcId); return; }
        if ($act === 'pass') { service_change_password_start($chatId, $svcId); return; }
        if ($act === 'ext')  { tg_send($chatId, 'برای حجم اضافه با پشتیبانی در تماس باش یا از 🔐 خرید اشتراک استفاده کن.'); return; }
        return;
    }

    // testpick — کاربر عادی پنل تست را انتخاب می‌کند (main.py: handler عمومی، قبل از admin gate)
    if (str_starts_with($data, 'testpick:')) { handle_test_pick($chatId, urldecode(substr($data, 9))); return; }

    // Reza rule: کاربر روی «✉️ پاسخ» پیام پشتیبانی می‌تواند جواب بدهد → تیکت جدید به ادمین‌ها (main.py gate نداشت؛ UX صحیح)
    if (!$admin && str_starts_with($data, 'um:msg:')) {
        $tgt = (int)substr($data, 7);
        if ($tgt === $chatId) {
            st_set($chatId, ['await' => 'support_msg']);
            send_or_edit($chatId, '✍️ پاسخت را بنویس (ارسال به پشتیبانی):');
        } else {
            tg_send($chatId, '⛔️ فقط ادمین.');
        }
        return;
    }

    // --- admin gate ---
    if (!$admin) { tg_send($chatId, '⛔️ فقط ادمین.'); return; }

    if ($data === 'wal:gift')  { start_gift_redeem($chatId); return; }
    if ($data === 'adm:general') { admin_general_home($chatId); return; }
    if ($data === 'adm:shopgeneral') { admin_shopgeneral_home($chatId); return; }
    if ($data === 'adm:power') { admin_power_home($chatId); return; }
    if (str_starts_with($data, 'pnl:edit:'))   { admin_panel_edit_start($chatId, urldecode(substr($data, 9))); return; }
    if (str_starts_with($data, 'pnl:toggle:')) { admin_panel_toggle($chatId, urldecode(substr($data, 11))); return; }
    if ($data === 'adm:back')  { st_pop($chatId); send_or_edit($chatId, '👨‍💼 پنل مدیریت:', admin_menu_kb()); return; }
    if ($data === 'adm:stats')   { admin_stats($chatId); return; }
    if ($data === 'adm:receipts'){ admin_receipts_queue($chatId); return; } // پایتون فقط صف رسیدها (main.py 1949-1965)
    if ($data === 'adm:users')   { admin_users_home($chatId); return; }
    if (str_starts_with($data, 'svcview:')) { admin_svc_view($chatId, (int)substr($data, 8)); return; }
    if (str_starts_with($data, 'svcordel:')) { admin_svc_orderdel($chatId, (int)substr($data, 9)); return; }
    if (str_starts_with($data, 'svcrefund:')) { admin_svc_refund($chatId, (int)substr($data, 10)); return; }
    if (str_starts_with($data, 'svcfulldel:')) { admin_svc_fulldel($chatId, (int)substr($data, 11)); return; }
    if ($data === 'svcnoop') { return; }
    if ($data === 'adm:finduser'){ admin_finduser_start($chatId); return; }
    if ($data === 'adm:search'){ admin_findorder_start($chatId); return; }
    if ($data === 'adm:massbal') { admin_massbal_start($chatId, 'add'); return; }
    if ($data === 'adm:masssub') { admin_massbal_start($chatId, 'sub'); return; }
    if (str_starts_with($data, 'umrepl:')) { admin_umrepl($chatId, $data); return; }
    if ($data === 'adm:tickets') { admin_tickets($chatId); return; }
    if ($data === 'adm:discounts'){ admin_discounts_home($chatId); return; }
    if ($data === 'adm:settings'){ admin_settings_home($chatId); return; }
    if ($data === 'adm:payments'){ admin_payments_home($chatId); return; }
    if (str_starts_with($data, 'paytoggle:')) {
        $pp = explode(':', $data); // paytoggle:key[:cfg]
        admin_pay_toggle($chatId, $pp[1], ($pp[2] ?? '') === 'cfg');
        return;
    }
    if (str_starts_with($data, 'paycfg:'))    { admin_pay_cfg($chatId, substr($data, 7)); return; }
    if (str_starts_with($data, 'payapi:'))    { admin_pay_api_start($chatId, substr($data, 7)); return; }
    if ($data === 'adm:gifts'){ admin_gifts_home($chatId); return; } // کپی main.py 2118-2127
    if ($data === 'adm:helps'){ admin_guide_home($chatId); return; }
    if ($data === 'adm:guides'){ admin_guide_home($chatId); return; }
    if ($data === 'adm:features'){ admin_features_home($chatId); return; }
    if ($data === 'adm:panels')  { admin_panels_home($chatId); return; }
    if ($data === 'adm:bcast')   { bcast_home($chatId); return; }

    // --- receipts ---
    if (str_starts_with($data, 'rcok:') || str_starts_with($data, 'rcno:')) { handle_receipt_review($chatId, $data); return; }
    if (str_starts_with($data, 'rcfix:')) { receipt_fix_start($chatId, (int)substr($data, 6)); return; }

    // --- tickets ---
    if (str_starts_with($data, 'tkclose:')) { admin_ticket_close($chatId, (int)substr($data, 8)); return; }

    // --- user profile & actions (کپی main.py 2631-2679) ---
    if (str_starts_with($data, 'um:')) { admin_user_action($chatId, $data); return; }

    // --- broadcast v2 ---
    if (str_starts_with($data, 'bcast2:')) { bcast_audience_pick($chatId, substr($data, 7)); return; }
    if (str_starts_with($data, 'bcastbtn:')) { bcast_btn_pick($chatId, substr($data, 9)); return; }
    if (str_starts_with($data, 'bcastgo:')) { bcast_run($chatId, substr($data, 8) === 'yes'); return; }

    // --- features toggle ---
    if (str_starts_with($data, 'feat:')) { admin_feature_toggle($chatId, substr($data, 5)); return; }

    // --- set:<key> settings prompt (کپی main.py on_settings_cb) ---
    if ($data === 'set:channels') { admin_channels_home($chatId); return; }
    if (str_starts_with($data, 'delchan:')) { admin_channel_delete($chatId, urldecode(substr($data, 8))); return; }
    if ($data === 'addchan') { admin_channel_add_start($chatId); return; }
    if ($data === 'set:force_join') {
        // تاگل فوری (کپی main.py 3106-3115)
        $cur = !empty(get_setting('force_join', false));
        set_setting('force_join', !$cur);
        admin_shopgeneral_home($chatId);
        return;
    }
    if (str_starts_with($data, 'set:')) { admin_set_prompt($chatId, substr($data, 4)); return; }
    if ($data === 'setcancel') { admin_set_cancel($chatId); return; }

    // --- dsc/gift codes add + delete ---
    if ($data === 'dsc:add' || $data === 'gift:add') { admin_code_add_start($chatId, substr($data, 0, 3)); return; }
    if (str_starts_with($data, 'okdel:discount:') || str_starts_with($data, 'okdel:gift:')) { admin_code_delete($chatId, $data); return; }

    // --- m:help — مدیریت آموزش entry (کپی main.py) ---
    if ($data === 'm:help') { show_guide($chatId); return; }

    // --- service extras: apcreds / aptoggle / apgb (کپی main.py 973-1085) ---
    if (str_starts_with($data, 'apcreds:')) { service_login_info($chatId, (int)substr($data, 8)); return; }
    if (str_starts_with($data, 'aptoggle:')) { service_toggle($chatId, (int)substr($data, 9)); return; }
    if (str_starts_with($data, 'apgb:'))    { service_extra_gb_start($chatId, (int)substr($data, 5)); return; }

    // --- panels ---
    if ($data === 'pnl:add') { admin_panel_add_start($chatId); return; }
    if (str_starts_with($data, 'pnl:view:')) { admin_panel_view($chatId, urldecode(substr($data, 9))); return; }
    if (str_starts_with($data, 'pnl:ping:')) { admin_panel_ping($chatId, urldecode(substr($data, 9))); return; }
    if (str_starts_with($data, 'pnl:testtoggle:')) { admin_panel_test_toggle($chatId, urldecode(substr($data, 15))); return; }
    if (str_starts_with($data, 'pnl:test:'))     { admin_panel_test_prompt($chatId, urldecode(substr($data, 9))); return; }
    if (str_starts_with($data, 'pnlrolepick:'))  { admin_panel_rolepick($chatId, urldecode(substr($data, 12))); return; }
    if (str_starts_with($data, 'pnlrole:')) {
        $parts = explode(':', $data); // pnlrole:<rid>:<name>
        admin_panel_role_set($chatId, (int)$parts[1], urldecode($parts[2])); return;
    }
    if (str_starts_with($data, 'pnl:stats:'))    { admin_panel_stats($chatId, urldecode(substr($data, 10))); return; }
    if (str_starts_with($data, 'pladd:'))        { admin_plan_add_prompt($chatId, urldecode(substr($data, 6))); return; }
    if (str_starts_with($data, 'pl:')) {
        $parts = explode(':', $data); // pl:<name>:<pid>
        admin_plan_view($chatId, urldecode($parts[1]), (int)$parts[2]); return;
    }
    if (str_starts_with($data, 'pled:')) {
        $parts = explode(':', $data); // pled:<pid>:<field>:<name>
        admin_plan_edit_prompt($chatId, (int)$parts[1], $parts[2], urldecode($parts[3])); return;
    }
    if (str_starts_with($data, 'pltog:')) {
        $parts = explode(':', $data); // pltog:<pid>:<name>
        admin_plan_toggle($chatId, (int)$parts[1], urldecode($parts[2])); return;
    }
    if (str_starts_with($data, 'okdel:plan:')) {
        $parts = explode(':', $data); // okdel:plan:<pid>:<name>
        admin_plan_delete($chatId, (int)$parts[2], urldecode($parts[3])); return;
    }
    if (str_starts_with($data, 'pnledit:')) {
        $parts = explode(':', $data); // pnledit:<field>:<name>
        admin_panel_field_edit($chatId, $parts[1], urldecode($parts[2])); return;
    }
    if (str_starts_with($data, 'askdel:pnl:')) { admin_panel_delete_confirm($chatId, urldecode(substr($data, 11))); return; }
    if (str_starts_with($data, 'okdel:pnl:')) { admin_panel_delete_apply($chatId, urldecode(substr($data, 10))); return; }

    // --- discount new ---
    if ($data === 'disc:new') { admin_code_add_start($chatId, 'dsc'); return; }
    if ($data === 'helpadd') { admin_help_add($chatId); return; }
    if (str_starts_with($data, 'helpedit:')) { admin_help_edit($chatId, (int)substr($data, 9)); return; }
    if (str_starts_with($data, 'helpdel:')) { admin_help_delete($chatId, (int)substr($data, 8)); return; }
    if (str_starts_with($data, 'guideadm:')) { admin_guide_home($chatId); return; }

    // --- power toggle (کپی main.py 2084-2094): admin_power_toggle + رفرش منو ---
    if (str_starts_with($data, 'pw:')) { admin_power_toggle($chatId, substr($data, 3)); return; } // admin_power_toggle خودش منو را رفرش می‌کند

    tg_send($chatId, 'دستور ناشناخته: ' . htmlspecialchars($data));
}