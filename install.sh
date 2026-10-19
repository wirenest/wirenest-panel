#!/usr/bin/env bash
set -e

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_RESET='\033[0m'

print_color() {
    local color="$1"
    local text="$2"
    case "$color" in
        red) printf "${COLOR_RED}%s${COLOR_RESET}\n" "$text" ;;
        green) printf "${COLOR_GREEN}%s${COLOR_RESET}\n" "$text" ;;
        yellow) printf "${COLOR_YELLOW}%s${COLOR_RESET}\n" "$text" ;;
        blue) printf "${COLOR_BLUE}%s${COLOR_RESET}\n" "$text" ;;
        *) echo "$text" ;;
    esac
}

print_color blue "=================================================="
print_color blue "    WireNest Panel (Python) — Automated Installer  "
print_color blue "=================================================="

if [ "$EUID" -ne 0 ]; then
    print_color red "[-] Please run this script as root (sudo bash)."
    exit 1
fi

read -p "Enter your Telegram Bot Token: " BOT_TOKEN
while [ -z "$BOT_TOKEN" ]; do
    read -p "Bot Token cannot be empty. Enter Telegram Bot Token: " BOT_TOKEN
done

read -p "Enter your Admin Telegram ID (numeric): " INITIAL_ADMIN_ID
while ! [[ "$INITIAL_ADMIN_ID" =~ ^[0-9]+$ ]]; do
    read -p "Invalid ID. Enter numeric Admin Telegram ID: " INITIAL_ADMIN_ID
done

INSTALL_DIR="/opt/wirenest-panel"
print_color blue "[+] Installing dependencies..."

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y python3 python3-pip python3-venv git curl
elif command -v yum >/dev/null 2>&1; then
    yum install -y python3 python3-pip git curl
fi

print_color blue "[+] Setting up installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

TMP_CLONE=$(mktemp -d)
git clone https://github.com/wirenest/wirenest-panel.git "$TMP_CLONE"
cp -r "$TMP_CLONE"/* "$INSTALL_DIR/"
rm -rf "$TMP_CLONE"

cd "$INSTALL_DIR"

print_color blue "[+] Setting up Python Virtual Environment..."
python3 -m venv venv
venv/bin/pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    venv/bin/pip install -r requirements.txt
else
    venv/bin/pip install python-telegram-bot requests
fi

print_color blue "[+] Configuring Bot Settings..."
if [ -f "bot.py" ]; then
    sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/g" bot.py
    sed -i "s/ADMIN_ID = [0-9]*/ADMIN_ID = $INITIAL_ADMIN_ID/g" bot.py
fi

if [ -f "pesarguard.py" ]; then
    sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/g" pesarguard.py
    sed -i "s/ADMIN_ID = [0-9]*/ADMIN_ID = $INITIAL_ADMIN_ID/g" pesarguard.py
fi

if [ -f "modules/config.py" ]; then
    sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/g" modules/config.py
    sed -i "s/ADMIN_ID = [0-9]*/ADMIN_ID = $INITIAL_ADMIN_ID/g" modules/config.py
fi

chmod -R 775 "$INSTALL_DIR/data"
chmod -R 775 "$INSTALL_DIR/logs"

print_color blue "[+] Creating Systemd Service..."
cat <<EOF > /etc/systemd/system/wirenest.service
[Unit]
Description=WireNest Panel Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python3 $INSTALL_DIR/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

print_color blue "[+] Starting WireNest Service..."
systemctl daemon-reload
systemctl enable wirenest
systemctl restart wirenest

print_color green "[+]"
print_color green "[+] WireNest Panel installed and started successfully!"
print_color green "[+] Status: $(systemctl is-active wirenest)"
print_color blue "=================================================="
