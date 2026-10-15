#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive

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
    print_color red "[-] Please run this script as root."
    exit 1
fi

# 1. Install Dependencies
print_color blue "[+] Installing dependencies (Apache, PHP, SQLite, Certbot)..."
if command -v apt-get >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y -qq php php-cli php-curl php-mbstring php-sqlite3 git curl unzip apache2 certbot python3-certbot-apache
elif command -v yum >/dev/null 2>&1; then
    yum update -y
    yum install -y php php-cli php-common php-mbstring php-pdo php-sqlite3 php-xml httpd git curl unzip certbot
fi

# 2. Get User Inputs
echo ""
read -p "Enter Domain (e.g. s.example.com): " DOMAIN </dev/tty
read -p "Enter Email (for SSL): " EMAIL </dev/tty
read -p "Enter Telegram Bot Token: " BOT_TOKEN </dev/tty
read -p "Enter Admin Telegram ID: " ADMIN_ID </dev/tty

# 3. Setup Project
INSTALL_DIR="/opt/wirenest-panel"
rm -rf "$INSTALL_DIR"
print_color blue "[+] Cloning WireNest Panel repository..."
git clone https://github.com/wirenest/wirenest-panel.git "$INSTALL_DIR"

cd "$INSTALL_DIR"
mkdir -p data logs
chmod -R 775 data logs
chown -R www-data:www-data data logs

# 4. Configure Web Server & SSL
print_color blue "[+] Configuring Apache for $DOMAIN..."
cat <<EOF > /etc/apache2/sites-available/wirenest.conf
<VirtualHost *:80>
    ServerName $DOMAIN
    DocumentRoot $INSTALL_DIR
    <Directory $INSTALL_DIR>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
EOF

a2ensite wirenest.conf || true
a2enmod rewrite ssl || true
systemctl restart apache2

print_color blue "[+] Obtaining SSL Certificate..."
certbot --apache -d "$DOMAIN" --email "$EMAIL" --agree-tos --no-eff-email --non-interactive || print_color yellow "[!] SSL failed, continuing with HTTP..."

# 5. Configuration (.env)
WEBHOOK_KEY=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)
cat <<EOF > .env
BOT_TOKEN=$BOT_TOKEN
INITIAL_ADMIN_ID=$ADMIN_ID
WEBHOOK_KEY=$WEBHOOK_KEY
DB_PATH=$INSTALL_DIR/data/bot.sqlite
EOF
chmod 640 .env
chown root:www-data .env

# 6. Set Telegram Webhook
PUBLIC_IP=$(curl -s https://api.ipify.org || echo "")
WEBHOOK_URL="https://$DOMAIN/core/webhook.php?key=$WEBHOOK_KEY"
print_color blue "[+] Registering Webhook: $WEBHOOK_URL"
curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=$WEBHOOK_URL&ip_address=$PUBLIC_IP"


# 7. Create wirenest-panel CLI alias
cat <<'CLI' > /usr/local/bin/wirenest-panel
#!/usr/bin/env bash
INSTALL_DIR="/opt/wirenest-panel"

case "$1" in
    update)
        echo "[+] Updating WireNest Panel from GitHub..."
        cd "$INSTALL_DIR"
        git fetch --all
        git reset --hard origin/master
        chown -R www-data:www-data data logs .env
        chmod -R 775 data logs
        chmod 640 .env
        systemctl restart apache2
        echo "[+] Update complete."
        ;;
    uninstall)
        read -p "Are you sure you want to uninstall WireNest Panel? (y/n): " confirm
        if [[ "$confirm" == "y" ]]; then
            echo "[+] Removing files and configuration..."
            rm -rf "$INSTALL_DIR"
            rm -f /etc/apache2/sites-available/wirenest.conf
            rm -f /etc/apache2/sites-enabled/wirenest.conf
            systemctl restart apache2
            rm -f /usr/local/bin/wirenest-panel
            echo "[+] Uninstalled successfully."
        fi
        ;;
    *)
        echo "Usage: wirenest-panel {update|uninstall}"
        ;;
esac
CLI
chmod +x /usr/local/bin/wirenest-panel

print_color green "[+]"
print_color green "[+] WireNest Panel installed and fully configured successfully!"
print_color green "[+] Access your panel at https://$DOMAIN"
print_color blue "=================================================="
