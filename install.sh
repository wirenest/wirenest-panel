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
print_color blue "   WireNest Python Bot — Automated Installer      "
print_color blue "=================================================="

if [ "$EUID" -ne 0 ]; then
    print_color red "[-] Please run this script as root (sudo bash)."
    exit 1
fi

# 1. Update and install system dependencies
print_color blue "[+] Updating package lists and installing Python & Git..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl unzip

# 2. Prompt for Telegram Bot Token & Admin ID
echo ""
read -p "Enter your Telegram Bot Token: " BOT_TOKEN </dev/tty
while [ -z "$BOT_TOKEN" ]; do
    read -p "Bot Token cannot be empty. Enter Telegram Bot Token: " BOT_TOKEN </dev/tty
done

read -p "Enter your Admin Telegram ID (numeric): " ADMIN_ID </dev/tty
while ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; do
    read -p "Invalid ID. Enter numeric Admin Telegram ID: " ADMIN_ID </dev/tty
done

# 3. Setup directory and clone repo
INSTALL_DIR="/opt/wirenest-panel"
print_color blue "[+] Setting up installation directory at $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"
git clone https://github.com/wirenest/wirenest-panel.git "$INSTALL_DIR"

cd "$INSTALL_DIR"
mkdir -p data logs

# 4. Configure pesarguard/config.py with user values
print_color blue "[+] Configuring bot settings..."
CONFIG_FILE="$INSTALL_DIR/pesarguard/config.py"
if [ -f "$CONFIG_FILE" ]; then
    sed -i "s/BOT_TOKEN = \".*\"/BOT_TOKEN = \"$BOT_TOKEN\"/g" "$CONFIG_FILE"
    sed -i "s/ADMIN_ID = .*/ADMIN_ID = $ADMIN_ID/g" "$CONFIG_FILE"
fi

# 5. Install Python dependencies
print_color blue "[+] Installing Python requirements..."
pip3 install --no-cache-dir -r requirements.txt

# 6. Create SystemD service for background execution
print_color blue "[+] Creating SystemD service..."
cat <<EOF > /etc/systemd/system/wirenest.service
[Unit]
Description=WireNest Python Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/wirenest-panel
ExecStart=/usr/bin/python3 /opt/wirenest-panel/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wirenest.service
systemctl restart wirenest.service

# 7. Create CLI management utility
cat <<'CLI' > /usr/local/bin/wirenest-panel
#!/usr/bin/env bash
INSTALL_DIR="/opt/wirenest-panel"

case "$1" in
    update)
        echo "[+] Updating WireNest Panel from GitHub..."
        cd "$INSTALL_DIR"
        git fetch --all
        git reset --hard origin/master
        pip3 install --no-cache-dir -r requirements.txt
        systemctl restart wirenest.service
        echo "[+] Update complete."
        ;;
    status)
        systemctl status wirenest.service
        ;;
    restart)
        systemctl restart wirenest.service
        echo "[+] Bot restarted."
        ;;
    uninstall)
        read -p "Are you sure you want to uninstall WireNest Panel? (y/n): " confirm
        if [[ "$confirm" == "y" ]]; then
            echo "[+] Stopping and removing service..."
            systemctl stop wirenest.service
            systemctl disable wirenest.service
            rm -f /etc/systemd/system/wirenest.service
            systemctl daemon-reload
            rm -rf "$INSTALL_DIR"
            rm -f /usr/local/bin/wirenest-panel
            echo "[+] Uninstalled successfully."
        fi
        ;;
    *)
        echo "Usage: wirenest-panel {update|status|restart|uninstall}"
        ;;
esac
CLI
chmod +x /usr/local/bin/wirenest-panel

print_color green "[+]"
print_color green "[+] WireNest Python Bot installed and started successfully!"
print_color green "[+] You can manage the bot using: wirenest-panel {update|status|restart|uninstall}"
print_color blue "=================================================="
