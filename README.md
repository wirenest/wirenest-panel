# WireNest Panel 🚀
**WireNest Panel** is a robust, lightweight, and modern PHP-based Telegram sales & management bot designed specifically for shared hosting (cPanel) and Linux servers. It seamlessly integrates with **PasarGuard**, **Marzban**, and **Sanaei** proxy panels.

---

## ✨ Features
- **Shared Hosting Friendly:** Runs smoothly on cPanel without requiring permanent background daemons (supports Webhook & Cron worker architecture).
- **Multi-Panel Support:** Connect and manage multiple PasarGuard / Marzban / Sanaei nodes and panels.
- **Advanced Encryption:** Upgraded to `AES-256-GCM` for secure storage of panel credentials and tokens.
- **Cloudflare / WAF Bypass:** Includes a hybrid Python bridge (`panel_bridge.py`) and pure PHP cURL implementation.
- **Complete Sales & Management Flow:** Wallet system, automated receipts, subscription delivery, traffic top-ups, and user management.

---

## ⚙️ Installation on cPanel / Shared Hosting

1. **Upload Files:** Upload the project files to your public directory or a dedicated subfolder on your cPanel hosting.
2. **Configure Environment:**
   Copy `.env.example` to `.env` and fill in your credentials:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   INITIAL_ADMIN_ID=your_telegram_admin_id
   WEBHOOK_KEY=random_secret_key
   ```
3. **Set Webhook:**
   Set your Telegram bot webhook to:
   `https://yourdomain.com/path/to/core/webhook.php?key=your_secret_key`
4. **Setup Cron Job:**
   Add a 1-minute cron job in cPanel to run `core/worker.php` or `core/cron.php` if needed.

---

## 📂 Project Structure
- `core/` — Bot bootstrap, handlers, webhooks, cron, and update router.
- `admin/` — Admin panels, broadcasts, stats, and settings management.
- `flows/` — User purchase, wallet, and service management flows.
- `lib/` — Panel API clients, encryption helpers, and Python bridge.

---

## 📜 License
MIT License. Created with ❤️ for proxy administrators.
