#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive

COLOR_RED='[0;31m'
COLOR_GREEN='[0;32m'
COLOR_YELLOW='[1;33m'
COLOR_BLUE='[0;34m'
COLOR_RESET='[0m'

print_color() {
    local color="$1"
    local text="$2"
    case "$color" in
        red) printf "${COLOR_RED}%s${COLOR_RESET}
" "$text" ;;
        green) printf "${COLOR_GREEN}%s${COLOR_RESET}
" "$text" ;;
        yellow) printf "${COLOR_YELLOW}%s${COLOR_RESET}
" "$text" ;;
        blue) printf "${COLOR_BLUE}%s${COLOR_RESET}
" "$text" ;;
        *) echo "$text" ;;
    esac
}

print_color blue "=================================================="
print_color blue "       WireNest Panel — Automated Installer       "
print_color blue "=================================================="

if [ "$EUID" -ne 0 ]; then
    print_color red "[-] Please run this script as root (sudo bash)."
    exit 1
fi

# 1. Update and install dependencies first
print_color blue "[+] Updating package lists and installing dependencies..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y -qq php php-cli php-curl php-mbstring php-sqlite3 git curl unzip apache2
elif command -v yum >/dev/null 2>&1; then
    yum update -y
    yum install -y php php-cli php-common php-mbstring php-pdo php-sqlite3 php-xml httpd git curl unzip
fi

# 2. Setup directory and clone/copy files first
INSTALL_DIR="/opt/wirenest-panel"
print_color blue "[+] Setting up installation directory at $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/data"
mkdir -p "$INSTALL_DIR/logs"

if [ -d "./core" ]; then
    cp -r ./* "$INSTALL_DIR/"
else
    print_color blue "[+] Cloning WireNest Panel repository..."
    git clone https://github.com/wirenest/wirenest-panel.git "$INSTALL_DIR" || true
fi

cd "$INSTALL_DIR"

# 3. Prompt for Telegram Bot Token & Admin ID interactively
echo ""
read -p "Enter your Telegram Bot Token: " BOT_TOKEN
while [ -z "$BOT_TOKEN" ]; do
    read -p "Bot Token cannot be empty. Enter Telegram Bot Token: " BOT_TOKEN
done

read -p "Enter your Admin Telegram ID (numeric): " INITIAL_ADMIN_ID
while ! [[ "$INITIAL_ADMIN_ID" =~ ^[0-9]+$ ]]; do
    read -p "Invalid ID. Enter numeric Admin Telegram ID: " INITIAL_ADMIN_ID
done

# 4. Generate random webhook key & create .env
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

# 5. Automatically set Webhook on Telegram
print_color blue "[+] Setting Telegram Webhook automatically..."
if command -v systemctl >/dev/null 2>&1; then
    systemctl enable apache2 || systemctl enable httpd || true
    systemctl restart apache2 || systemctl restart httpd || true
fi

PUBLIC_IP=$(curl -s https://api.ipify.org || curl -s ifconfig.me || hostname -I | awk '{print $1}')

if [ -d "/var/www/html" ]; then
    ln -sfn "$INSTALL_DIR" /var/www/html/wirenest-panel
    WEBHOOK_URL="http://$PUBLIC_IP/wirenest-panel/core/webhook.php?key=$WEBHOOK_KEY"
else
    WEBHOOK_URL="http://$PUBLIC_IP/core/webhook.php?key=$WEBHOOK_KEY"
fi

print_color blue "[+] Registering Webhook URL: $WEBHOOK_URL"
TG_RESPONSE=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=$WEBHOOK_URL")
echo "$TG_RESPONSE" | grep -q '"ok":true' && print_color green "[+] Telegram Webhook successfully set and bot is ready!" || print_color yellow "[!] Warning: Could not auto-set webhook via Telegram API."

print_color green "[+]"
print_color green "[+] WireNest Panel installed and fully configured successfully!"
print_color green "[+] Files located at: $INSTALL_DIR"
print_color blue "=================================================="
