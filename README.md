# 🤖 WireNest | PasarGuard Panel Maker & Sales Bot 🚀

### A Python Telegram bot for creating PasarGuard panels, managing proxy services and automating sales

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org/)
[![Platform](https://img.shields.io/badge/Platform-Debian%20%7C%20Ubuntu-lightgrey.svg)](#-requirements)

[فارسی 🇮🇷](README_FA.md)

WireNest lets you sell and manage PasarGuard panels entirely from Telegram. Customers browse plans, top up a wallet, buy a service and receive their panel credentials instantly, while you manage everything from an admin menu inside the bot. The bot interface is in Persian.

---

## 📋 Table of Contents

- [Requirements](#-requirements)
- [Installation](#-installation)
- [First Run](#-first-run)
- [Features](#-features)
- [Management CLI](#-management-cli)
- [Manual Installation](#-manual-installation-advanced)
- [Updating & Backups](#-updating--backups)
- [Project Structure](#-project-structure)
- [Troubleshooting](#-troubleshooting)
- [Security Notes](#-security-notes)

---

## ✅ Requirements

| Item | Requirement |
|---|---|
| OS | Debian 12+ or Ubuntu 22.04+ (needs `apt` and `systemd`) |
| Access | `root` / `sudo` |
| Python | 3.10 or newer (the installer sets this up for you) |
| Telegram | A bot token from [@BotFather](https://t.me/BotFather) and your numeric Telegram ID (get it from [@userinfobot](https://t.me/userinfobot)) |
| Panel | At least one reachable PasarGuard panel with an admin account |

---

## ⚡ Installation

Run this on your server:

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/wirenest/wirenest-panel/master/install.sh)"
```

The installer will ask for your **bot token** and your **admin Telegram ID**, validate the token against Telegram, then:

1. installs the required packages (Python ≥ 3.10, git, curl),
2. downloads the bot to `/opt/wirenest-panel`,
3. creates a virtual environment and installs the dependencies,
4. registers and starts a `systemd` service named `wirenest`,
5. installs the `wirenest-panel` management command.

### Non-interactive install

```bash
BOT_TOKEN="123456:ABC-your-token" ADMIN_ID="123456789" \
sudo -E bash -c "$(curl -fsSL https://raw.githubusercontent.com/wirenest/wirenest-panel/master/install.sh)"
```

> Re-running the installer on a server that already has WireNest reinstalls the code but **keeps your `data/` and `logs/` folders**.

---

## 🚀 First Run

1. Open your bot in Telegram and send `/start`. The account whose ID you gave the installer gets the **👨‍💼 Admin panel** button.
2. In **📦 Panel management**, add your PasarGuard panel(s) and create the sale plans (volume and price).
3. In **⚙️ Settings**, set your card number / owner name and any payment gateways you want to offer, plus the support contact and bot texts.
4. (Optional) In **📚 Guide management**, add connection tutorials, and create discount or gift codes.
5. Send `/start` from a normal user account and walk through a test purchase.

---

## 🔥 Features

### 👤 For customers
- **🔐 Buy a subscription:** pick a plan, see an invoice and get the panel address, username and password instantly.
- **🏦 Wallet & top-up:** top up by card-to-card, TRON, ZarinPal or AqayePardakht (as enabled by the admin); receipts are reviewed by the admin.
- **🏷 Discount codes:** apply a code on the invoice screen, even before the wallet has enough balance. The discounted price carries through the top-up and the final payment.
- **🛍 My services:** view your services, change the panel password and buy extra volume.
- **🧪 Free test service:** time-limited trial accounts that are removed automatically on expiry.
- **📡 Connection guide, 📋 terms, ❓ FAQ and ☎️ support.**
- **🎁 Gift codes:** redeem wallet-credit gift codes.
- **📢 Forced channel join** (optional).

### 🛠 For admins
- **📊 Statistics:** sales and system overview.
- **📦 Panel management:** connect multiple PasarGuard panels/nodes and manage their plans.
- **👥 User management:** user cards, balances and services.
- **🧾 Receipt queue:** approve, reject, or approve with a corrected amount.
- **🏷 Discount codes and 🎁 gift codes:** percent or fixed amount, usage limits, expiry.
- **🛠 Feature toggles:** enable or disable buying, top-up, service management, gifts, guide and FAQ.
- **📣 Broadcast messages and 🎫 support tickets.**
- **🎨 Appearance:** customise button styles and texts.
- **🔌 Power switch:** turn the bot on or off for maintenance.

### ⚙️ Automation & security
- **Background jobs** clean up expired test services and stale pending purchases.
- **Panel passwords are stored encrypted** (AES-GCM), never in plain text.
- Payment receipts are checked for duplicate transaction IDs.
- Concurrency-safe discount usage (a code can't exceed its usage limit).
- Persistent state, so users can continue after a restart.

---

## 🛠 Management CLI

After installation, use these commands (run as root):

| Command | Description |
|---|---|
| `wirenest-panel status` | Show the service status |
| `wirenest-panel logs [lines]` | Show the last log lines (default 100) |
| `wirenest-panel restart` | Restart the bot |
| `wirenest-panel update` | Pull the latest version from GitHub, reinstall dependencies and restart |
| `wirenest-panel uninstall` | Remove the bot **and its data** (asks for confirmation) |

---

## 🧰 Manual Installation (advanced)

```bash
git clone https://github.com/wirenest/wirenest-panel.git
cd wirenest-panel
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Edit `pesarguard/config.py` and set:

```python
BOT_TOKEN = "123456:ABC-your-token"
ADMIN_ID = 123456789
```

Then start it:

```bash
./venv/bin/python run.py
```

Data is stored next to `run.py`: `data/bot.sqlite` (database), `data/state.json` and `logs/bot.log`.

---

## 🔄 Updating & Backups

- **Update:** `sudo wirenest-panel update`. This resets the code to the latest GitHub version, so **don't edit files inside `/opt/wirenest-panel` by hand** (your token and admin ID are re-applied automatically from `/etc/wirenest-panel/bot.env`).
- **Backup:** copy the `data/` folder (and optionally `logs/`):

  ```bash
  sudo cp -a /opt/wirenest-panel/data /root/wirenest-data-backup
  ```

- **Restore:** stop the service, put the backup back as `/opt/wirenest-panel/data`, then start the service again.

---

## 📂 Project Structure

```text
wirenest-panel/
├── run.py                    # Entry point
├── install.sh                # Automated installer
├── requirements.txt          # Python dependencies
└── pesarguard/               # Bot engine
    ├── config.py             # Token, admin ID, paths
    ├── bootstrap.py          # Timezone, folders, logging
    ├── database.py           # SQLite helpers and settings
    ├── state.py              # Per-user conversation state
    ├── telegram_api.py       # Telegram send/edit helpers
    ├── panel_api.py          # PasarGuard panel API client
    ├── crypto.py             # Password encryption
    ├── keyboards.py          # Menus and inline keyboards
    ├── dispatcher.py         # Routes updates to handlers
    ├── cron.py               # Background jobs
    ├── main.py               # Application start-up
    └── handlers/
        ├── user/             # buy, wallet, services, test, receipts, info
        └── admin/            # stats, panels, users, receipts, discounts, broadcast, ...
```

---

## 🩺 Troubleshooting

| Problem | What to do |
|---|---|
| Bot doesn't answer | `sudo wirenest-panel status` then `sudo wirenest-panel logs 200` |
| Installer says Python is too old | Use Ubuntu 22.04+ / Debian 12+ |
| Logs say the bot token is empty (`BOT_TOKEN خالیه`) | Run `sudo wirenest-panel update` to re-apply the token from `/etc/wirenest-panel/bot.env`, or re-run the installer |
| Can't create services | Check the panel URL, admin credentials and that the server can reach the panel |
| Telegram is unreachable from your server | Make sure the server can reach `api.telegram.org` |

---

## 🔐 Security Notes

- The token is stored in `/etc/wirenest-panel/bot.env` and `pesarguard/config.py`, both readable by root only.
- Only the Telegram ID(s) registered as admin (the `ADMIN_ID` you gave the installer) can open the admin panel.

---

## 📄 License

Released under the [MIT License](LICENSE).


## 💖 Support / Donation

If you find this project useful, you can support us via BEP20 USDT:
`0x87696D2F1750AE4aac625864F9Ff70514089d5ef`
