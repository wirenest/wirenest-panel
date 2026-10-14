<div align="center">

# WireNest Panel 🚀
### Unified PHP Telegram Sales & Management Bot for PasarGuard, Marzban & Sanaei Panels

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PHP Version](https://img.shields.io/badge/PHP-%3E%3D8.1-blue.svg)](https://php.net/)
[![Platform](https://img.shields.io/badge/Platform-Linux server%20%7C%20Linux-green.svg)]()

[English](#-features) | [فارسی](./README_FA.md)

</div>

---

## 🚀 Quick Installation

Run the following command on your server to install WireNest Panel automatically:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/wirenest/wirenest-panel/master/install.sh)"
```

During installation, the script will prompt you for:
1. **Telegram Bot Token**
2. **Admin Telegram ID (Numeric)**

---

## ✨ Comprehensive Feature List

- **Shared Hosting & Linux server Friendly:** Optimized to run seamlessly on standard Linux server environments without permanent background daemons.
- **Multi-Panel & Multi-Node Architecture:** Connect, manage, and test connections for multiple PasarGuard, Marzban, and Sanaei proxy panels simultaneously.
- **Advanced Security & Encryption:** Upgraded to `AES-256-GCM` authenticated encryption for securely storing sensitive admin credentials and panel tokens.
- **Cloudflare & WAF Bypass:** Hybrid execution supporting both pure PHP cURL and a Python bridge (`panel_bridge.py`) for handling protected panels.
- **Complete Automated Sales Flow:**
  - Instant subscription delivery & management.
  - Wallet system with credit top-up and balance deduction.
  - Automated receipt uploading and admin verification queue.
  - Discount codes (vouchers) and gift code generation.
- **Robust Admin Tools:**
  - Broadcast messaging system (all users, buyers, non-buyers).
  - Detailed statistics, user lookup, and mass balance adjustments.
  - Ticket management and support messaging system.
  - Panel status toggle & maintenance power switch.

---

## 📂 Project Structure

- `core/` — Bot bootstrap, handlers, webhooks, cron, and update router.
- `admin/` — Admin panels, broadcasts, stats, and settings management.
- `flows/` — User purchase, wallet, and service management flows.
- `lib/` — Panel API clients, encryption helpers, and Python bridge.

---

## 📜 License & Notice

This project is licensed under the **MIT License**. 

> ⚠️ **Notice:** To access the final production-ready version of this project, a $100 donation is required. Please contact the repository owner for details.
\n\n> **USDT (BEP20) Donation Address:** `0x87696D2F1750AE4aac625864F9Ff70514089d5ef`