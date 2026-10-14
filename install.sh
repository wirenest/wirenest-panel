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
print_color blue "       WireNest Panel — Automated Installer       "
print_color blue "=================================================="

if [ "$EUID" -ne 0 ]; then
    print_color red "[-] Please run this script as root (sudo bash)."
    exit 1
}

# Prompt for Telegram Bot Token & Admin ID
read -p "Enter your Telegram Bot Token: " BOT_TOKEN
while [ -z "$BOT_TOKEN" ]; do
    read -p "Bot Token cannot be empty. Enter Telegram Bot Token: " BOT_TOKEN
done

read -p "Enter your Admin Telegram ID (numeric): " INITIAL_ADMIN_ID
while ! [[ "$INITIAL_ADMIN_ID" =~ ^[0-9]+$ ]]; do
    read -p "Invalid ID. Enter numeric Admin Telegram ID: " INITIAL_ADMIN_ID
done

INSTALL_DIR="/opt/wirenest-panel"
print_color blue "[+] Installing dependencies (PHP, cURL, Git, Unzip)..."

if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y php php-cli php-curl php-mbstring php-sqlite3 php-openssl git curl unzip
elif command -v yum >/dev/null 2>&1; then
    yum install -y php php-cli php-common php-mbstring php-pdo php-sqlite3 php-xml git curl unzip
fi

print_color blue "[+] Setting up installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

# If running from local or cloning
if [ -d "./core" ]; then
    cp -r ./* "$INSTALL_DIR/"
else
    print_color blue "[+] Cloning WireNest Panel repository..."
    git clone https://github.com/wirenest/wirenest-panel.git "$INSTALL_DIR" || true
fi

cd "$INSTALL_DIR"

# Generate random webhook key
WEBHOOK_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)

print_color blue "[+] Configuring .env file..."
cat <<EOF > "$INSTALL_DIR/.env"
BOT_TOKEN=$BOT_TOKEN
INITIAL_ADMIN_ID=$INITIAL_ADMIN_ID
WEBHOOK_KEY=$WEBHOOK_KEY
DB_PATH=$INSTALL_DIR/data/bot.sqlite
PANEL_RELAY_URL=
PANEL_RELAY_KEY=
EOF

chmod 600 "$INSTALL_DIR/.env"
chmod -R 775 "$INSTALL_DIR/data"
chmod -R 775 "$INSTALL_DIR/logs"

print_color green "[+]"
print_color green "[+] WireNest Panel installed successfully!"
print_color green "[+] Files located at: $INSTALL_DIR"
print_color green "[+] Webhook URL for Telegram:"
print_color yellow "    https://yourdomain.com/path/to/wirenest-panel/core/webhook.php?key=$WEBHOOK_KEY"
print_color blue "=================================================="
