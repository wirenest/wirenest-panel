<?php
/**
 * admin/panels.php — panel management: list, ping, add wizard, edit, roles
 */

require_once BASE_DIR . '/core/bot.php';
require_once BASE_DIR . '/core/menus.php';
require_once BASE_DIR . '/lib/panel_api.php';

function admin_panels_home(int $chatId): void {
    $panels = get_setting('panels', []) ?: [];
    $kb = ['inline_keyboard' => []];
    foreach ($panels as $name => $d) {
        $kb['inline_keyboard'][] = [
            ['text' => "🌐 $name", 'callback_data' => "pnl:view:" . $name],
            ['text' => '🔍 تست', 'callback_data' => "pnl:ping:" . $name],
        ];
    }
    $kb['inline_keyboard'][] = [['text' => '➕ افزودن پنل', 'callback_data' => 'pnl:add']];
    $kb['inline_keyboard'][] = [['text' => '◀️ بازگشت', 'callback_data' => 'adm:back']];
    send_or_edit($chatId, '🌐 پنل‌های متصل:', $kb);
}

function admin_panel_view(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    $d = $panels[$name];
    $sel = (string)get_setting('selected_panel', '');
    $active = $d['active'] ?? ($name === $sel);

    // plans of this panel
    $st = db()->prepare('SELECT * FROM panel_plans WHERE panel_name=? ORDER BY volume_gb');
    $st->execute([$name]);
    $plans = $st->fetchAll();

    $kb = ['inline_keyboard' => []];
    foreach ($plans as $pl) {
        $mark = !empty($pl['active']) ? '' : '❌ ';
        $kb['inline_keyboard'][] = [[
            'text' => $mark . sprintf('%g گیگ — %s ت', (float)$pl['volume_gb'], number_format((int)$pl['price'])),
            'callback_data' => "pl:$name:{$pl['id']}",
        ]];
    }
    $kb['inline_keyboard'][] = [['text' => '➕ افزودن پلن حجمی +', 'callback_data' => "pladd:$name"]];

    $xprice = (int)($d['extra_gb_price'] ?? 0);
    $xmin = (int)($d['extra_gb_min'] ?? 0);
    $roleId = (int)($d['role_id'] ?? 3);
    $roleLbl = [2 => '👑 مدیر کل', 3 => '👤 اپراتور', 5 => '🌐 CDN'][$roleId] ?? '👤 اپراتور';
    $xpLbl = $xprice ? number_format($xprice) . ' ت' : '— تنظیم نشده';
    $xmLbl = $xmin ? $xmin . ' گیگ' : '— تنظیم نشده';
    $testOn = !empty($d['is_test_panel']);

    $kb['inline_keyboard'][] = [['text' => "🛡 نقش مدیران: $roleLbl", 'callback_data' => "pnlrolepick:$name"]];
    $kb['inline_keyboard'][] = [
        ['text' => "💰 قیمت حجم: $xpLbl", 'callback_data' => "pnledit:extra_price:$name"],
        ['text' => "⚖️ حداقل حجم: $xmLbl", 'callback_data' => "pnledit:extra_min:$name"],
    ];
    $kb['inline_keyboard'][] = [['text' => '📊 آمار پنل', 'callback_data' => "pnl:stats:$name"]];
    $kb['inline_keyboard'][] = [['text' => '✏️ ویرایش نام پنل', 'callback_data' => "pnledit:name:$name"]];
    $kb['inline_keyboard'][] = [['text' => '✏️ ویرایش آدرس پنل', 'callback_data' => "pnledit:url:$name"]];
    $kb['inline_keyboard'][] = [
        ['text' => '✏️ ویرایش یوزر ادمین', 'callback_data' => "pnledit:user:$name"],
        ['text' => '✏️ ویرایش پسورد ادمین', 'callback_data' => "pnledit:pass:$name"],
    ];
    $kb['inline_keyboard'][] = [
        ['text' => $testOn ? '🧪 سرویس تست: ✅ روشن' : '🧪 سرویس تست: ⛔️ خاموش', 'callback_data' => "pnl:testtoggle:$name"],
        ['text' => '⚙️ حجم/مدت تست', 'callback_data' => "pnl:test:$name"],
    ];
    $kb['inline_keyboard'][] = [['text' => $active ? '🔴 غیرفعال کن' : '🟢 فعال کن', 'callback_data' => "pnl:toggle:$name"]];
    $kb['inline_keyboard'][] = [['text' => '🗑 حذف این پنل', 'callback_data' => "askdel:pnl:$name"]];
    $kb['inline_keyboard'][] = [['text' => '◀️ پنل‌ها', 'callback_data' => 'adm:panels']];

    $statusTxt = $active ? '🟢 فعال (قابل خرید)' : '🔴 غیرفعال';
    send_or_edit($chatId,
        "🛠 مدیریت پنل «{$name}» (" . ($d['ptype'] ?? 'pasarguard') . ")
"
        . "$statusTxt
"
        . "🔗 " . $d['base_url'] . "

"
        . "📦 پلن‌های حجمی این پنل:",
        $kb);
}

function admin_panel_ping(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    $d = $panels[$name];
    $d['password'] = panel_decrypt_pw($d['password'] ?? '');
    tg_send($chatId, "🔍 در حال تست $name ...");
    $r = panel_ping($d);
    // فقط وضعیت فارسی — متن فنی انگلیسی (auth-ok و...) نمایش داده نمی‌شه (قانون رضا: متون کاربری تمیز)
    send_or_edit($chatId, $r['ok'] ? "🟢 وصله — $name" : "🔴 قطعه — $name");
}

function admin_panel_add_start(int $chatId): void {
    // ترتیب جدید (فرمان رضا): اول اسم پنل (همونی که به کاربر نشون داده می‌شه) → آدرس → یوزر → پسورد
    st_set($chatId, ['await' => 'pnladd_name']);
    send_or_edit($chatId, "🏷 اسم پنل رو بفرست (همین اسم به کاربر نشون داده می‌شه، مثلاً: سرور1):");
}

function admin_panel_delete_confirm(int $chatId, string $name): void {
    st_set($chatId, ['await' => 'okdel:pnl:' . $name]);
    send_or_edit($chatId, "⚠️ «{$name}» برای همیشه حذف بشه؟ این عملیات غیرقابل‌بازگشته!",
        ['inline_keyboard' => [
            [['text' => '🔥 بله، حذف کن', 'callback_data' => "okdel:pnl:" . $name]],
            [['text' => '🚫 نه', 'callback_data' => 'adm:panels']],
        ]]);
}

function admin_panel_delete_apply(int $chatId, string $name): void {
    st_pop($chatId);
    $panels = get_setting('panels', []) ?: [];
    unset($panels[$name]);
    set_setting('panels', $panels);
    send_or_edit($chatId, "🗑 پنل «{$name}» حذف شد.", admin_menu_kb());
}

/** Wizard steps: name → url → user → pass (encrypted at write, Reza audit rule). */
function admin_panel_add_step(int $chatId, string $await, string $text): void {
    switch ($await) {
        case 'pnladd_name':
            $name = trim($text);
            if ($name === '') { send_or_edit($chatId, '❌ اسم پنل نمی‌تونه خالی باشه، دوباره بفرست:'); return; }
            $panels = get_setting('panels', []) ?: [];
            if (isset($panels[$name])) { send_or_edit($chatId, "❌ پنلی با اسم «{$name}» از قبل ثبت شده. اسم دیگه‌ای بفرست:"); return; }
            st_set($chatId, ['await' => 'pnladd_url', 'pnl_name' => $name]);
            send_or_edit($chatId, "🔗 آدرس پنل رو بفرست (مثلاً https://example.ir):");
            return;
        case 'pnladd_url':
            if (!preg_match('#^https?://#', $text)) { send_or_edit($chatId, '❌ آدرس باید با http(s) شروع شه:'); return; }
            st_set($chatId, ['await' => 'pnladd_user', 'pnl_url' => panel_clean_base_url($text)]);
            send_or_edit($chatId, '👤 یوزرنیم ادمین پنل:');
            return;
        case 'pnladd_user':
            st_set($chatId, ['await' => 'pnladd_pass', 'pnl_user' => trim($text)]);
            send_or_edit($chatId, '🔑 پسورد ادمین پنل:');
            return;
        case 'pnladd_pass':
            $name = (string)st_get($chatId, 'pnl_name', '');
            $url = (string)st_get($chatId, 'pnl_url', '');
            $user = (string)st_get($chatId, 'pnl_user', '');
            $pass = trim($text);
            st_pop($chatId);
            // test ping first
            $probe = ['base_url' => $url, 'username' => $user, 'password' => $pass, 'ptype' => 'pasarguard'];
            send_or_edit($chatId, '🔍 در حال تست اتصال...');
            $r = panel_ping($probe);
            if (empty($r['ok'])) {
                send_or_edit($chatId, "❌ لاگین ناموفق\nدوباره از «➕ افزودن پنل» شروع کن.");
                return;
            }
            $panels = get_setting('panels', []) ?: [];
            // اسم انتخابی ادمین (فرمان رضا)؛ اگر وسط کار اسم تکراری شد، پسوند عددی می‌گیره
            $finalName = $name !== '' ? $name : 'پنل ' . (count($panels) + 1);
            $i = 2;
            while (isset($panels[$finalName])) { $finalName = $name . ' ' . $i; $i++; }
            $panels[$finalName] = [
                'base_url' => $url, 'username' => $user,
                'password' => panel_encrypt_pw($pass), // encrypt at write (audit rule)
                'ptype' => 'pasarguard', 'active' => true,
            ];
            set_setting('panels', $panels);
            send_or_edit($chatId, "✅ پنل «{$finalName}» اضافه و وصل شد.", admin_menu_kb());
            return;
    }
}


/** پاریتی main.py 2324-2340: toggle سرویس تست پنل */
function admin_panel_test_toggle(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    $panels[$name]['is_test_panel'] = empty($panels[$name]['is_test_panel']);
    // Reza UX fix: روشن‌کردن toggle بدون حجم/مدت → خودکار دیفالت 1 گیگ / 1 روز ست شود (وگرنه کاربر «فعلاً سرویس تست فعال نیست» می‌دید)
    $note = '';
    if (!empty($panels[$name]['is_test_panel'])
        && (empty($panels[$name]['test_gb']) || empty($panels[$name]['test_days']))) {
        $panels[$name]['test_gb'] = $panels[$name]['test_gb'] ?: 1;
        $panels[$name]['test_days'] = $panels[$name]['test_days'] ?: 1;
        $note = '\n⚙️ حجم/مدت ست نبود — دیفالت 1 گیگ / 1 روز اعمال شد (از «⚙️ حجم/مدت تست» قابل تغییر است).';
    }
    set_setting('panels', $panels);
    send_or_edit($chatId, (!empty($panels[$name]['is_test_panel']) ? '🧪 سرویس تست روشن شد' : '🧪 سرویس تست خاموش شد') . $note);
    admin_panel_view($chatId, $name);
}

/** پاریتی main.py 2342-2352: پرامپت حجم/مدت تست (دو خط) */
function admin_panel_test_prompt(int $chatId, string $name): void {
    st_set($chatId, ['await' => 'pnltest', 'pnltest_name' => $name]);
    send_or_edit($chatId,
        "🖊 مشخصات سرویس تست را بفرست (دو خط):\n\nحجم به گیگ: مثلا 1\nمدت به روز: مثلا 1\n\n(این پنل برای سرویس‌های تست کاربران استفاده خواهد شد)",
        ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]]);
}

/** state pnltest — اعمال حجم/مدت تست */
function admin_panel_test_apply(int $chatId, string $text): void {
    $name = (string)st_get($chatId, 'pnltest_name', '');
    $lines = array_values(array_filter(array_map('trim', explode("\n", $text))));
    if (count($lines) < 2 || !is_numeric($lines[0]) || !is_numeric($lines[1])) {
        send_or_edit($chatId, "❌ فرمت درست نیست. دو خط بفرست:\nحجم (گیگ)\nمدت (روز) — مثلا:\n1\n1");
        return;
    }
    $panels = get_setting('panels', []) ?: [];
    if (isset($panels[$name])) {
        $panels[$name]['test_gb'] = (float)$lines[0];
        $panels[$name]['test_days'] = (int)$lines[1];
        set_setting('panels', $panels);
    }
    st_pop($chatId);
    send_or_edit($chatId, "✅ سرویس تست ثبت شد: {$lines[0]} گیگ / {$lines[1]} روز");
    admin_panel_view($chatId, $name);
}

/** پاریتی main.py 1690-1730: انتخاب نقش مدیران جدید پنل */
function admin_panel_rolepick(int $chatId, string $name): void {
    send_or_edit($chatId, "🛡 نقش مدیران ساخته‌شده توسط ربات در «{$name}»:",
        ['inline_keyboard' => [
            [['text' => '👑 مدیر کل (همه‌چیز)', 'callback_data' => "pnlrole:2:$name"]],
            [['text' => '👤 اپراتور (ساخت سرویس)', 'callback_data' => "pnlrole:3:$name"]],
            [['text' => '🌐 CDN (فقط سرویس)', 'callback_data' => "pnlrole:5:$name"]],
            [['text' => '◀️ بازگشت', 'callback_data' => "pnl:view:$name"]],
        ]]);
}

function admin_panel_role_set(int $chatId, int $rid, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (isset($panels[$name])) {
        $panels[$name]['role_id'] = $rid;
        set_setting('panels', $panels);
    }
    $lbl = [2 => '👑 مدیر کل', 3 => '👤 اپراتور', 5 => '🌐 CDN'][$rid] ?? '👤 اپراتور';
    send_or_edit($chatId, "✅ نقش مدیران: $lbl");
    admin_panel_view($chatId, $name);
}

/** پاریتی main.py 2395-2425: آمار پنل (system stats + فروش) */
function admin_panel_stats(int $chatId, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    $d = $panels[$name];
    $d['password'] = panel_decrypt_pw($d['password'] ?? '');
    send_or_edit($chatId, '📊 در حال دریافت آمار...');
    $r = panel_bridge_call($d, 'stats', []);
    $nadmins = 0;
    if (!empty($r['ok'])) {
        $nadmins = (int)($r['admins_count'] ?? 0);
        $ver = (string)($r['version'] ?? '—');
        $ramTotal = (string)($r['ram_total_gb'] ?? '—');
        $ramUsed = (string)($r['ram_used_gb'] ?? '—');
        $traffic = (string)($r['traffic_tb'] ?? '—');
        $status = '✅ پنل متصل است';
    } else {
        $ver = $ramTotal = $ramUsed = $traffic = '—';
        $status = '🔴 قطع';
    }
    $st = db()->query("SELECT COUNT(*) c, COALESCE(SUM(price),0) s FROM purchases WHERE status='active'")->fetch();
    $txt = "📊 آمار پنل شما 👇\n\n"
        . "🖥 وضعیت اتصال: $status\n"
        . "👥 تعداد مدیران ساخته شده در پنل: $nadmins\n"
        . "📡 نسخه پنل: $ver\n"
        . "💻 رم کل سرور: $ramTotal گیگابایت\n"
        . "💻 مصرف رم پنل: $ramUsed گیگابایت\n"
        . "🌐 ترافیک کل مصرف شده: $traffic ترابایت\n"
        . "🛍 تعداد فروش کل در این پنل: {$st['c']}\n"
        . "🛍 جمع فروش کل: " . number_format((int)$st['s']) . " تومان";
    send_or_edit($chatId, $txt);
}

/** پاریتی main.py 2385-2391: پرامپت افزودن پلن حجمی (گیگ → قیمت) */
function admin_plan_add_prompt(int $chatId, string $name): void {
    st_set($chatId, ['await' => 'pladd_gb', 'plan_panel' => $name]);
    send_or_edit($chatId, '➕ حجم پلن را بفرست (گیگ): مثلا 100',
        ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]]);
}

function admin_plan_gb_apply(int $chatId, string $text): void {
    $gb = trim($text);
    if (!is_numeric($gb) || (float)$gb <= 0) { send_or_edit($chatId, '❌ عدد گیگ نامعتبر. دوباره بفرست (مثلا 100):'); return; }
    st_set($chatId, ['await' => 'pladd_price', 'plan_gb' => (float)$gb]);
    send_or_edit($chatId, '💰 قیمت این پلن را بفرست (تومان): مثلا 300000');
}

function admin_plan_price_apply(int $chatId, string $text): void {
    $price = str_replace([',', ' '], '', trim($text));
    if (!is_numeric($price) || (int)$price <= 0) { send_or_edit($chatId, '❌ قیمت نامعتبر. دوباره بفرست (تومان):'); return; }
    $name = (string)st_get($chatId, 'plan_panel', '');
    $gb = (float)st_get($chatId, 'plan_gb', 0);
    st_pop($chatId);
    db()->prepare('INSERT INTO panel_plans(panel_name, volume_gb, price, active) VALUES(?,?,?,1)')
        ->execute([$name, $gb, (int)$price]);
    send_or_edit($chatId, '✅ پلن افزوده شد: ' . sprintf('%g گیگ — %s ت', $gb, number_format((int)$price)));
    admin_panel_view($chatId, $name);
}

/** پاریتی main.py 2249-2262: نمای پلن (ویرایش قیمت/حجم/فعال‌سازی/حذف) */
function admin_plan_view(int $chatId, string $name, int $pid): void {
    $st = db()->prepare('SELECT * FROM panel_plans WHERE id=?');
    $st->execute([$pid]);
    $pl = $st->fetch();
    if (!$pl) { send_or_edit($chatId, 'پلن یافت نشد.'); return; }
    $mark = !empty($pl['active']) ? '🟢 فعال' : '🔴 غیرفعال';
    send_or_edit($chatId,
        sprintf("📦 پلن %g گیگ\n💰 قیمت: %s تومان\n%s", (float)$pl['volume_gb'], number_format((int)$pl['price']), $mark),
        ['inline_keyboard' => [
            [['text' => '✏️ ویرایش قیمت', 'callback_data' => "pled:$pid:price:$name"], ['text' => '✏️ ویرایش حجم', 'callback_data' => "pled:$pid:gb:$name"]],
            [['text' => !empty($pl['active']) ? '🔴 غیرفعال کن' : '🟢 فعال کن', 'callback_data' => "pltog:$pid:$name"]],
            [['text' => '🗑 حذف پلن', 'callback_data' => "okdel:plan:$pid:$name"]],
            [['text' => '◀️ بازگشت', 'callback_data' => "pnl:view:$name"]],
        ]]);
}

function admin_plan_edit_prompt(int $chatId, int $pid, string $field, string $name): void {
    st_set($chatId, ['await' => "pled:$field", 'pled_pid' => $pid, 'pled_panel' => $name]);
    $st = db()->prepare('SELECT * FROM panel_plans WHERE id=?');
    $st->execute([$pid]);
    $pl = $st->fetch();
    $cur = $pl ? ($field === 'price' ? number_format((int)$pl['price']) . ' تومان' : sprintf('%g گیگ', (float)$pl['volume_gb'])) : '—';
    $what = $field === 'price' ? 'قیمت (تومان)' : 'حجم (گیگ)';
    send_or_edit($chatId, "✏️ مقدار فعلی: $cur\n\nمقدار جدید $what را بفرست:",
        ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]]);
}

function admin_plan_edit_apply(int $chatId, string $field, string $text): void {
    $pid = (int)st_get($chatId, 'pled_pid', 0);
    $name = (string)st_get($chatId, 'pled_panel', '');
    $v = str_replace([',', ' '], '', trim($text));
    if (!is_numeric($v) || (float)$v <= 0) { send_or_edit($chatId, '❌ مقدار نامعتبر. دوباره بفرست:'); return; }
    if ($field === 'price') db()->prepare('UPDATE panel_plans SET price=? WHERE id=?')->execute([(int)$v, $pid]);
    else db()->prepare('UPDATE panel_plans SET volume_gb=? WHERE id=?')->execute([(float)$v, $pid]);
    st_pop($chatId);
    send_or_edit($chatId, '✅ پلن ویرایش شد.');
    admin_plan_view($chatId, $name, $pid);
}

function admin_plan_toggle(int $chatId, int $pid, string $name): void {
    db()->prepare('UPDATE panel_plans SET active = 1 - active WHERE id=?')->execute([$pid]);
    admin_plan_view($chatId, $name, $pid);
}

function admin_plan_delete(int $chatId, int $pid, string $name): void {
    db()->prepare('DELETE FROM panel_plans WHERE id=?')->execute([$pid]);
    send_or_edit($chatId, '🗑 پلن حذف شد.');
    admin_panel_view($chatId, $name);
}

/** پاریتی main.py pnledit: prompts for panel scalar fields */
function admin_panel_field_edit(int $chatId, string $field, string $name): void {
    $panels = get_setting('panels', []) ?: [];
    $cur = $panels[$name] ?? [];
    $curval = ['user' => $cur['username'] ?? '', 'pass' => '••••••',
               'url' => $cur['base_url'] ?? '', 'name' => $name,
               'extra_price' => $cur['extra_gb_price'] ?? '',
               'extra_min' => $cur['extra_gb_min'] ?? ''][$field] ?? '';
    st_set($chatId, ['await' => "pnledit_$field", 'edit_pnl' => $name]);
    $hints = [
        'extra_price' => 'قیمت حجم اضافه به تومان برای هر گیگ (مثلاً 6000):',
        'extra_min' => 'حداقل گیگ قابل خرید حجم اضافه (مثلاً 10):',
        'name' => 'نام جدید پنل را بفرست:',
        'url' => 'آدرس جدید پنل را بفرست:',
        'user' => 'یوزر ادمین جدید را بفرست:',
        'pass' => 'پسورد ادمین جدید را بفرست:',
    ];
    send_or_edit($chatId,
        '✏️ مقدار فعلی: ' . (($curval !== '' && $curval !== null) ? (string)$curval : '— تنظیم نشده') . "\n\n" . ($hints[$field] ?? 'مقدار جدید را بفرست:'),
        ['inline_keyboard' => [[['text' => '❌ لغو', 'callback_data' => 'setcancel']]]]);
}

/** state pnledit_<field> — apply scalar field edits (name/url/user/pass/extra_price/extra_min) */
function admin_panel_field_apply(int $chatId, string $field, string $text): void {
    $name = (string)st_get($chatId, 'edit_pnl', '');
    $text = trim($text);
    $panels = get_setting('panels', []) ?: [];
    if (!isset($panels[$name])) { st_pop($chatId); send_or_edit($chatId, 'پنل یافت نشد.'); return; }
    switch ($field) {
        case 'name':
            $newName = $text;
            if ($newName === '' || (isset($panels[$newName]) && $newName !== $name)) {
                send_or_edit($chatId, '❌ نام نامعتبر یا تکراری:'); return;
            }
            $panels[$newName] = $panels[$name];
            unset($panels[$name]);
            // rename plans
            db()->prepare('UPDATE panel_plans SET panel_name=? WHERE panel_name=?')->execute([$newName, $name]);
            set_setting('panels', $panels);
            st_pop($chatId);
            send_or_edit($chatId, '✅ نام پنل شد: ' . $newName);
            admin_panel_view($chatId, $newName);
            return;
        case 'url':
            if (!preg_match('#^https?://#', $text)) { send_or_edit($chatId, '❌ آدرس باید با http(s) شروع شه:'); return; }
            $panels[$name]['base_url'] = panel_clean_base_url($text);
            break;
        case 'user':
            $panels[$name]['username'] = $text;
            break;
        case 'pass':
            $panels[$name]['password'] = panel_encrypt_pw($text);
            break;
        case 'extra_price':
            if (!is_numeric($text) || (int)$text < 0) { send_or_edit($chatId, '❌ قیمت نامعتبر (عدد تومان بفرست، 0 = حذف):'); return; }
            $panels[$name]['extra_gb_price'] = (int)$text;
            break;
        case 'extra_min':
            if (!is_numeric($text) || (int)$text < 1) { send_or_edit($chatId, '❌ حداقل نامعتبر (عدد گیگ بفرست):'); return; }
            $panels[$name]['extra_gb_min'] = (int)$text;
            break;
        default:
            st_pop($chatId);
            return;
    }
    set_setting('panels', $panels);
    st_pop($chatId);
    send_or_edit($chatId, '✅ ذخیره شد.');
    admin_panel_view($chatId, $name);
}