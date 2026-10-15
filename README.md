<div align="center">

# 🤖 WireNest | PasarGuard Panel Maker & Sales Bot 🚀
### The Most Advanced PHP Telegram Bot for Panel Creation, Proxy Management & Automated Sales

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PHP Version](https://img.shields.io/badge/PHP-%3E%3D8.1-blue.svg)](https://php.net/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20cPanel-green.svg)]()

[English](#-quick-installation) | [فارسی](./README_FA.md)

</div>

---

## ⚡ Quick Installation

Run the following command on your server to install WireNest Panel automatically:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/wirenest/wirenest-panel/master/install.sh)"
```

During installation, the script will prompt you for:
1. 🔑 **Telegram Bot Token**
2. 👤 **Admin Telegram ID (Numeric)**

---

## 🔥 Key Features & Capabilities (Panel Maker & Store)

### 💎 1. Advanced "Panel Maker" System
- 🏢 **Custom Panel Provisioning:** Create, setup, and sell dedicated sub-panels and accounts to your clients and resellers.
- 🔗 **PasarGuard Integration:** Seamlessly communicates with PasarGuard panels to manage admins, data limits, and traffic quotas.
- ⚙️ **Multi-Node Architecture:** Easily manage and control multiple proxy servers and nodes from one place.

### 💰 2. Financial System, Wallet & Auto Sales
- 💳 **Instant Wallet Top-up:** Users can add credit and automatically pay for subscriptions or renewals.
- 🧾 **Receipt Verification Queue:** Users upload payment slips, and admins can review/approve them instantly from the panel.
- 🎁 **Discount & Gift Vouchers:** Create percentage/fixed discount codes and wallet top-up gift cards.

### 🤖 3. Automated Sales & Delivery Bot
- 📦 **Instant Delivery:** Fast and clean checkout flow for selecting plans, paying from wallet, and receiving configs instantly.
- 🧪 **Free Trial Service:** Offer limited trial accounts to new users with automated expiration handling.
- 📋 **My Services Dashboard:** View active subscriptions, traffic usage, expiration dates, and connection details.

### 🛠 4. Comprehensive Admin Dashboard
- 📢 **Broadcast System:** Send mass announcements (to all users, buyers only, or non-buyers) with pinning options.
- 📊 **Detailed Analytics:** Monitor user statistics, transaction history, revenue, and resource usage.
- ✉️ **Support & Ticketing:** Direct user-to-admin support messaging through the bot.
- 🔌 **Emergency Power Switch:** Turn the bot on/off instantly for maintenance.

### 🛡 5. Robust Security & Reliability
- 🔐 **`AES-256-GCM` Encryption:** Securely store sensitive credentials, passwords, and panel tokens.
- 🌐 **WAF & Cloudflare Bypass:** Built-in cURL client and Python bridge (`panel_bridge.py`) for handling protected panels.

---

## 📂 Project Structure

- 📁 `core/` — Bot bootstrap, handlers, webhook router, and cron worker.
- 📁 `admin/` — Admin management panels, stats, broadcasts, and settings.
- 📁 `flows/` — User purchase flows, wallet, services, and trial generation.
- 📁 `lib/` — API clients, encryption utilities, and Python bridge.

---

## 📜 License & Donation Notice

This project is licensed under the **MIT License**.

## 📜 License & Donation

This project is open-source under MIT License.

> ⚠️ **Notice:** This is an initial version of the project. To continue development, add new features, and maintain the project, we need your support!
> 
> **🪙 USDT (BEP20) Donation Address:**
> ```text
> 0x87696D2F1750AE4aac625864F9Ff70514089d5ef
> ```