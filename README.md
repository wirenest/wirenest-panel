<div align="center">

# WireNest Panel 🚀
### Unified PHP Telegram Sales & Management Bot for PasarGuard, Marzban & Sanaei Panels

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PHP Version](https://img.shields.io/badge/PHP-%3E%3D8.1-blue.svg)](https://php.net/)
[![Platform](https://img.shields.io/badge/Platform-cPanel%20%7C%20Linux-green.svg)]()

[English](#-features) | [فارسی](./README_FA.md)

</div>

---

## 🌟 Overview

**WireNest Panel** is a robust, lightweight, and modern PHP-based Telegram sales and management bot designed specifically for shared hosting (`cPanel`) and Linux servers. It seamlessly integrates with **PasarGuard**, **Marzban**, and **Sanaei** proxy panels, offering high performance without the overhead of heavy background daemons.

---

## ✨ Features

- **Shared Hosting Friendly:** Runs smoothly on cPanel without requiring permanent background daemons (supports Webhook & Cron worker architecture).
- **Multi-Panel Support:** Connect and manage multiple PasarGuard / Marzban / Sanaei nodes and panels simultaneously.
- **Advanced Encryption:** Upgraded to `AES-256-GCM` for secure storage of panel credentials and tokens.
- **Cloudflare / WAF Bypass:** Includes a hybrid Python bridge (`panel_bridge.py`) and pure PHP cURL implementation.
- **Complete Sales Flow:** Wallet system, automated receipt verification, subscription delivery, traffic top-ups, and user management.

---

## ⚙️ Installation on cPanel / Shared Hosting

1. **Upload Files:** Upload the project files to your public directory or a dedicated subfolder on your cPanel hosting.
2. **Configure Environment:**
   Copy `.env.example` to `.env` and configure your bot credentials:
   ```env
   BOT_TOKEN=your_telegram_bot_token
   INITIAL_ADMIN_ID=your_telegram_admin_id
   WEBHOOK_KEY=random_secret_key
   ```
3. **Set Webhook:**
   Set your Telegram bot webhook to:
   `https://yourdomain.com/path/to/core/webhook.php?key=your_secret_key`
4. **Setup Cron Job:**
   Add a 1-minute cron job in cPanel to run `core/worker.php` for background tasks.

---

## 📂 Project Structure

- `core/` — Bot bootstrap, handlers, webhooks, cron, and update router.
- `admin/` — Admin panels, broadcasts, stats, and settings management.
- `flows/` — User purchase, wallet, and service management flows.
- `lib/` — Panel API clients, encryption helpers, and Python bridge.

---

## 📜 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

Made with ❤️ for Internet freedom
