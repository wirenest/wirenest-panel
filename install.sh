#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'; RESET=$'\033[0m'
info()  { printf '%s[+] %s%s\n' "$BLUE" "$1" "$RESET"; }
ok()    { printf '%s[+] %s%s\n' "$GREEN" "$1" "$RESET"; }
warn()  { printf '%s[!] %s%s\n' "$YELLOW" "$1" "$RESET"; }
fail()  { printf '%s[-] %s%s\n' "$RED" "$1" "$RESET"; exit 1; }

printf '%s==================================================\n' "$BLUE"
printf '       WireNest Panel - Automated Installer\n'
printf '==================================================%s\n' "$RESET"

[ "$EUID" -eq 0 ] || fail "Please run this script as root."
command -v apt-get >/dev/null 2>&1 || fail "This installer supports Ubuntu/Debian only."

# Ensure curl and ca-certificates exist before initial checks
if ! command -v curl >/dev/null 2>&1; then
    info "Installing curl..."
    apt-get update -y -qq
    apt-get install -y -qq curl ca-certificates
fi

# ---------- ask(): reads from the terminal even when run via "curl | bash" ----------
ask() {
    # usage: ask VAR "Prompt"
    local __var="$1" __prompt="$2" __val=""
    if [ -n "${!__var:-}" ]; then return 0; fi
    [ -r /dev/tty ] || fail "No terminal available. Pass $__var as an environment variable."
    while [ -z "$__val" ]; do
        read -r -p "$__prompt" __val </dev/tty
        # Strip leading/trailing whitespace and carriage returns
        __val="$(printf '%s' "$__val" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    done
    printf -v "$__var" '%s' "$__val"
}

# ---------- 1. Collect input: domain, email, token, admin id ----------
echo ""
ask DOMAIN "Enter your domain (e.g. panel.example.com): "
DOMAIN="${DOMAIN,,}"
DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
[[ "$DOMAIN" =~ ^([a-z0-9-]+\.)+[a-z]{2,}$ ]] || fail "Invalid domain: $DOMAIN"

ask EMAIL "Enter your email (for SSL certificate): "
[[ "$EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]] || fail "Invalid email: $EMAIL"

ask BOT_TOKEN "Enter your Telegram Bot Token: "
BOT_TOKEN="${BOT_TOKEN//[[:space:]]/}"

ask INITIAL_ADMIN_ID "Enter your Admin Telegram ID (numeric): "
while ! [[ "$INITIAL_ADMIN_ID" =~ ^[0-9]+$ ]]; do
    warn "Admin ID must be numeric."
    INITIAL_ADMIN_ID=""
    ask INITIAL_ADMIN_ID "Enter your Admin Telegram ID (numeric): "
done

# ---------- 2. Validate bot token ----------
info "Checking bot token with Telegram..."
if ! curl -4 -fsS "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | grep -q '"ok":true'; then
    fail "Telegram rejected this bot token (or Telegram API is unreachable). Check it and run again."
fi
ok "Bot token is valid."

# ---------- 3. Check that the domain points to this server ----------
info "Checking DNS for $DOMAIN..."
PUBLIC_IP="$(curl -4 -fsS https://api.ipify.org || curl -4 -fsS https://ifconfig.me || true)"
DOMAIN_IP="$(getent ahostsv4 "$DOMAIN" | awk '{print $1; exit}' || true)"
if [ -z "$DOMAIN_IP" ]; then
    fail "Domain $DOMAIN does not resolve yet. Create an A record pointing to $PUBLIC_IP, wait a few minutes, and run again."
fi
if [ -n "$PUBLIC_IP" ] && [ "$DOMAIN_IP" != "$PUBLIC_IP" ]; then
    warn "Domain resolves to $DOMAIN_IP but this server is $PUBLIC_IP."
    warn "If you use Cloudflare, turn the proxy (orange cloud) OFF until the certificate is issued."
    fail "DNS mismatch. Fix the A record and run again."
fi
ok "DNS OK: $DOMAIN -> $DOMAIN_IP"

# ---------- 4. Install dependencies ----------
info "Installing dependencies..."
apt-get update -y
apt-get install -y -qq php php-cli php-curl php-mbstring php-sqlite3 php-xml \
    git curl unzip openssl apache2 libapache2-mod-php certbot python3-certbot-apache

# ---------- 5. Install project files ----------
INSTALL_DIR="/opt/wirenest-panel"
REPO_URL="${REPO_URL:-https://github.com/wirenest/wirenest-panel.git}"
info "Installing project to $INSTALL_DIR..."

if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only || warn "git pull failed; keeping existing files."
elif [ -d "./core" ] && [ "$(cd . && pwd)" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    cp -a ./* "$INSTALL_DIR/"
else
    if [ -e "$INSTALL_DIR" ] && [ -n "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]; then
        BACKUP="${INSTALL_DIR}.bak-$(date +%s)"
        warn "$INSTALL_DIR is not empty; moving it to $BACKUP"
        mv "$INSTALL_DIR" "$BACKUP"
    fi
    git clone "$REPO_URL" "$INSTALL_DIR" \
        || fail "git clone failed. Check the repository URL ($REPO_URL) and your network."
fi

[ -d "$INSTALL_DIR/core" ] || fail "Project files are missing (no core/ directory). Installation aborted."

mkdir -p "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

# ---------- 6. Write .env ----------
WEBHOOK_KEY="$(openssl rand -hex 16)"

info "Writing .env..."
cat > "$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=$BOT_TOKEN
INITIAL_ADMIN_ID=$INITIAL_ADMIN_ID
WEBHOOK_KEY=$WEBHOOK_KEY
DB_PATH=$INSTALL_DIR/data/bot.sqlite
PANEL_RELAY_URL=
PANEL_RELAY_KEY=
EOF

# Set ownership and permissions so Apache (www-data) can serve core/ and write to data/ and logs/
chown -R www-data:www-data "$INSTALL_DIR"
find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
find "$INSTALL_DIR" -type f -exec chmod 644 {} \;
chown root:www-data "$INSTALL_DIR/.env"
chmod 640 "$INSTALL_DIR/.env"
chmod -R 775 "$INSTALL_DIR/data" "$INSTALL_DIR/logs"

# ---------- 7. Apache virtual host ----------
info "Configuring Apache for $DOMAIN..."
cat > /etc/apache2/sites-available/wirenest.conf <<EOF
<VirtualHost *:80>
    ServerName $DOMAIN
    DocumentRoot $INSTALL_DIR

    <Directory $INSTALL_DIR>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    # Never expose secrets, database, logs or git data
    <DirectoryMatch "^$INSTALL_DIR/(data|logs|\.git)">
        Require all denied
    </DirectoryMatch>
    <FilesMatch "^\.(env|git)">
        Require all denied
    </FilesMatch>
    <FilesMatch "\.(sqlite|sqlite3|db|log)$">
        Require all denied
    </FilesMatch>

    ErrorLog \${APACHE_LOG_DIR}/wirenest-error.log
    CustomLog \${APACHE_LOG_DIR}/wirenest-access.log combined
</VirtualHost>
EOF

a2enmod rewrite headers >/dev/null 2>&1 || true
a2ensite wirenest.conf >/dev/null
a2dissite 000-default.conf >/dev/null 2>&1 || true
apache2ctl configtest
systemctl enable apache2 >/dev/null 2>&1 || true
systemctl restart apache2

# ---------- 8. Firewall (only if ufw is active) ----------
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
    info "Opening ports 80 and 443 in ufw..."
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
fi

# ---------- 9. SSL certificate ----------
info "Requesting SSL certificate from Let's Encrypt..."
if ! certbot --apache -d "$DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email \
        --redirect --non-interactive; then
    fail "Certbot failed. Make sure ports 80/443 are open on your provider's firewall, the domain points to this server (no Cloudflare proxy), then run again."
fi
systemctl reload apache2
sleep 2
ok "SSL certificate installed for $DOMAIN."

# ---------- 10. Set Telegram webhook over HTTPS ----------
WEBHOOK_URL="https://$DOMAIN/core/webhook.php?key=$WEBHOOK_KEY"
info "Registering webhook: https://$DOMAIN/core/webhook.php?key=****"

TG_RESPONSE="$(curl -4 -sS -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
    --data-urlencode "url=${WEBHOOK_URL}" \
    --data-urlencode "secret_token=${WEBHOOK_KEY}" \
    --data-urlencode "drop_pending_updates=true" || true)"

if echo "$TG_RESPONSE" | grep -q '"ok":true'; then
    ok "Telegram webhook set successfully. Bot is ready!"
else
    warn "Could not set webhook. Telegram response:"
    echo "$TG_RESPONSE"
    warn "Check manually: curl -4 https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
fi

echo ""
ok "WireNest Panel installed."
ok "Files:   $INSTALL_DIR"
ok "Domain:  https://$DOMAIN"
printf '%s==================================================%s\n' "$BLUE" "$RESET"
