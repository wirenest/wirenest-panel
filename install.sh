#!/usr/bin/env bash
#
# WireNest Panel — Automated Installer
# Run: sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/wirenest/wirenest-panel/master/install.sh)"
#
# Non-interactive usage:
#   BOT_TOKEN="123:ABC..." ADMIN_ID="123456789" sudo -E bash install.sh

set -Eeuo pipefail
trap 'printf "\033[0;31m[-] Installer failed at line %s. Fix the error above and run it again.\033[0m\n" "$LINENO" >&2' ERR

export DEBIAN_FRONTEND=noninteractive

REPO_URL="${WIRENEST_REPO_URL:-https://github.com/wirenest/wirenest-panel.git}"
BRANCH="master"
INSTALL_DIR="/opt/wirenest-panel"
SERVICE_NAME="wirenest"
CONF_DIR="/etc/wirenest-panel"
CONF_FILE="$CONF_DIR/bot.env"
CLI_PATH="/usr/local/bin/wirenest-panel"
MIN_PY_MINOR=10   # the bot code needs Python >= 3.10

COLOR_RED=$'\033[0;31m'
COLOR_GREEN=$'\033[0;32m'
COLOR_YELLOW=$'\033[1;33m'
COLOR_BLUE=$'\033[0;34m'
COLOR_RESET=$'\033[0m'

print_color() {
  local color="$1" text="$2"
  case "$color" in
    red)    printf "%s%s%s\n" "$COLOR_RED" "$text" "$COLOR_RESET" ;;
    green)  printf "%s%s%s\n" "$COLOR_GREEN" "$text" "$COLOR_RESET" ;;
    yellow) printf "%s%s%s\n" "$COLOR_YELLOW" "$text" "$COLOR_RESET" ;;
    blue)   printf "%s%s%s\n" "$COLOR_BLUE" "$text" "$COLOR_RESET" ;;
    *)      printf "%s\n" "$text" ;;
  esac
}

die() { print_color red "[-] $*"; exit 1; }

# Read a line from the terminal even when the script is piped through curl.
ask() {
  local prompt="$1" var
  if [ -r /dev/tty ]; then
    read -r -p "$prompt" var </dev/tty || die "Could not read from the terminal. Pass BOT_TOKEN and ADMIN_ID as environment variables."
  else
    die "No terminal available. Pass BOT_TOKEN and ADMIN_ID as environment variables."
  fi
  printf '%s' "$var"
}

print_color blue "=================================================="
print_color blue "      WireNest Python Bot — Automated Installer    "
print_color blue "=================================================="

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  die "Please run this script as root (sudo bash)."
fi

command -v apt-get >/dev/null 2>&1 || die "This installer supports Debian/Ubuntu only (apt-get not found)."
command -v systemctl >/dev/null 2>&1 || die "systemd is required (systemctl not found)."

# ---------------------------------------------------------------- 1. packages
print_color blue "[+] Updating package lists and installing base packages..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl ca-certificates

# ------------------------------------------------- 2. pick a Python >= 3.10
py_ok() { "$1" -c "import sys; sys.exit(0 if sys.version_info >= (3, $MIN_PY_MINOR) else 1)" 2>/dev/null; }

find_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && py_ok "$c"; then command -v "$c"; return 0; fi
  done
  return 1
}

PYTHON_BIN="$(find_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  print_color yellow "[!] System Python is older than 3.$MIN_PY_MINOR — trying to install a newer one..."
  for v in 3.12 3.11 3.10; do
    if apt-get install -y "python$v" "python$v-venv" >/dev/null 2>&1; then break; fi
  done
  PYTHON_BIN="$(find_python || true)"
fi
if [ -z "$PYTHON_BIN" ] && [ -r /etc/os-release ] && grep -qi '^ID=ubuntu' /etc/os-release; then
  print_color yellow "[!] Adding the deadsnakes PPA for a newer Python..."
  apt-get install -y software-properties-common
  add-apt-repository -y ppa:deadsnakes/ppa
  apt-get update -y
  apt-get install -y python3.11 python3.11-venv
  PYTHON_BIN="$(find_python || true)"
fi
[ -n "$PYTHON_BIN" ] || die "Python 3.$MIN_PY_MINOR or newer is required and could not be installed. Use Ubuntu 22.04+ / Debian 12+."
print_color green "[+] Using $("$PYTHON_BIN" --version 2>&1) ($PYTHON_BIN)"

# ------------------------------------------------ 3. Bot token & admin ID
echo ""
BOT_TOKEN="${BOT_TOKEN:-}"
ADMIN_ID="${ADMIN_ID:-}"
TOKEN_RE='^[0-9]{6,}:[A-Za-z0-9_-]{30,}$'

if [ -n "$BOT_TOKEN" ] && ! [[ "$BOT_TOKEN" =~ $TOKEN_RE ]]; then die "BOT_TOKEN from environment has an invalid format."; fi
while [ -z "$BOT_TOKEN" ]; do
  BOT_TOKEN="$(ask "Enter your Telegram Bot Token: ")"
  BOT_TOKEN="${BOT_TOKEN//[[:space:]]/}"
  if ! [[ "$BOT_TOKEN" =~ $TOKEN_RE ]]; then
    print_color red "[-] Invalid token format (expected 123456789:AA...). Try again."
    BOT_TOKEN=""
  fi
done

if [ -n "$ADMIN_ID" ] && ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then die "ADMIN_ID from environment must be numeric."; fi
while [ -z "$ADMIN_ID" ]; do
  ADMIN_ID="$(ask "Enter your Admin Telegram ID (numeric): ")"
  ADMIN_ID="${ADMIN_ID//[[:space:]]/}"
  if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    print_color red "[-] Invalid ID. It must be numeric."
    ADMIN_ID=""
  fi
done

# Soft check of the token against Telegram (a network failure is only a warning).
http_code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "https://api.telegram.org/bot${BOT_TOKEN}/getMe" || true)"
case "$http_code" in
  200) print_color green "[+] Bot token verified with Telegram." ;;
  401|404) die "Telegram rejected this bot token. Check it in @BotFather and run the installer again." ;;
  *) print_color yellow "[!] Could not reach api.telegram.org (HTTP ${http_code:-none}) — continuing without verification." ;;
esac

# Keep credentials outside the git checkout so updates never lose them.
mkdir -p "$CONF_DIR"
chmod 700 "$CONF_DIR"
umask 077
printf 'BOT_TOKEN=%s\nADMIN_ID=%s\n' "$BOT_TOKEN" "$ADMIN_ID" > "$CONF_FILE"
chmod 600 "$CONF_FILE"
umask 022

# ------------------------------------------- 4. Fetch code (keep user data)
print_color blue "[+] Setting up installation directory at $INSTALL_DIR..."
BACKUP_DIR=""
if [ -d "$INSTALL_DIR/data" ]; then
  BACKUP_DIR="$(mktemp -d)"
  print_color yellow "[!] Existing installation found — preserving data/ and logs/."
  mv "$INSTALL_DIR/data" "$BACKUP_DIR/data"
  if [ -d "$INSTALL_DIR/logs" ]; then mv "$INSTALL_DIR/logs" "$BACKUP_DIR/logs"; fi
fi

systemctl stop "$SERVICE_NAME.service" >/dev/null 2>&1 || true
rm -rf "$INSTALL_DIR"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

if [ -n "$BACKUP_DIR" ]; then
  rm -rf "$INSTALL_DIR/data" "$INSTALL_DIR/logs"
  mv "$BACKUP_DIR/data" "$INSTALL_DIR/data"
  if [ -d "$BACKUP_DIR/logs" ]; then mv "$BACKUP_DIR/logs" "$INSTALL_DIR/logs"; fi
  rmdir "$BACKUP_DIR" 2>/dev/null || true
fi
mkdir -p data logs
chmod 700 data

[ -f run.py ] || die "run.py not found in the repository — the Python bot files are missing from GitHub."
[ -f pesarguard/config.py ] || die "pesarguard/config.py not found in the repository."
[ -f requirements.txt ] || die "requirements.txt not found in the repository."

# ----------------------------------------------- 5. Management CLI (first)
print_color blue "[+] Installing management utility..."
cat > "$CLI_PATH" <<'CLI'
#!/usr/bin/env bash
set -Eeuo pipefail

INSTALL_DIR="/opt/wirenest-panel"
CONF_FILE="/etc/wirenest-panel/bot.env"
SERVICE="wirenest.service"
BRANCH="master"

[ "${EUID:-$(id -u)}" -eq 0 ] || { echo "Run as root: sudo wirenest-panel $*"; exit 1; }

apply_config() {
  [ -f "$CONF_FILE" ] || { echo "[-] $CONF_FILE not found."; exit 1; }
  # shellcheck disable=SC1090
  . "$CONF_FILE"
  BOT_TOKEN="$BOT_TOKEN" ADMIN_ID="$ADMIN_ID" python3 - "$INSTALL_DIR/pesarguard/config.py" <<'PY'
import os, re, sys
path = sys.argv[1]
token, admin = os.environ["BOT_TOKEN"], int(os.environ["ADMIN_ID"])
src = open(path, encoding="utf-8").read()
src, n1 = re.subn(r"^BOT_TOKEN\s*=.*$", lambda m: 'BOT_TOKEN = "%s"' % token, src, flags=re.M)
src, n2 = re.subn(r"^ADMIN_ID\s*=.*$", lambda m: "ADMIN_ID = %d" % admin, src, flags=re.M)
if n1 != 1 or n2 != 1:
    sys.exit("BOT_TOKEN / ADMIN_ID lines not found in config.py")
open(path, "w", encoding="utf-8").write(src)
PY
  chmod 600 "$INSTALL_DIR/pesarguard/config.py"
}

install_deps() {
  cd "$INSTALL_DIR"
  [ -d venv ] || "$(cat "$INSTALL_DIR/.python-bin")" -m venv venv
  ./venv/bin/pip install --no-cache-dir --upgrade pip >/dev/null
  ./venv/bin/pip install --no-cache-dir -r requirements.txt
}

case "${1:-}" in
  apply-config)
    apply_config
    ;;
  update)
    echo "[+] Updating WireNest Panel from GitHub..."
    cd "$INSTALL_DIR"
    git fetch --depth 1 origin "$BRANCH"
    git reset --hard "origin/$BRANCH"
    apply_config
    install_deps
    systemctl restart "$SERVICE"
    echo "[+] Update complete."
    ;;
  status)
    systemctl status "$SERVICE" --no-pager || true
    ;;
  logs)
    journalctl -u "$SERVICE" -n "${2:-100}" --no-pager
    ;;
  restart)
    systemctl restart "$SERVICE"
    echo "[+] Bot restarted."
    ;;
  uninstall)
    read -r -p "Uninstall WireNest Panel and DELETE all its data (database, logs)? (y/n): " confirm </dev/tty
    if [[ "$confirm" == "y" ]]; then
      systemctl stop "$SERVICE" 2>/dev/null || true
      systemctl disable "$SERVICE" 2>/dev/null || true
      rm -f "/etc/systemd/system/$SERVICE"
      systemctl daemon-reload
      rm -rf "$INSTALL_DIR" /etc/wirenest-panel /usr/local/bin/wirenest-panel
      echo "[+] Uninstalled successfully."
    fi
    ;;
  *)
    echo "Usage: wirenest-panel {update|status|logs [lines]|restart|uninstall}"
    ;;
esac
CLI
chmod +x "$CLI_PATH"

# ---------------------------------- 6. Configure bot + install dependencies
print_color blue "[+] Configuring bot settings..."
printf '%s\n' "$PYTHON_BIN" > "$INSTALL_DIR/.python-bin"
"$CLI_PATH" apply-config

print_color blue "[+] Installing Python requirements (this can take a minute)..."
"$PYTHON_BIN" -m venv venv
./venv/bin/pip install --no-cache-dir --upgrade pip >/dev/null
./venv/bin/pip install --no-cache-dir -r requirements.txt

# ------------------------------------------------------ 7. systemd service
print_color blue "[+] Creating systemd service..."
cat > "/etc/systemd/system/$SERVICE_NAME.service" <<EOF
[Unit]
Description=WireNest Python Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME.service" >/dev/null 2>&1
systemctl restart "$SERVICE_NAME.service"

# ---------------------------------------------------- 8. Verify it started
sleep 5
if ! systemctl is-active --quiet "$SERVICE_NAME.service"; then
  print_color red "[-] The service failed to start. Last log lines:"
  journalctl -u "$SERVICE_NAME.service" -n 30 --no-pager || true
  exit 1
fi

print_color green "[+] WireNest Python Bot installed and running!"
print_color green "[+] Manage it with: wirenest-panel {update|status|logs|restart|uninstall}"
print_color blue "=================================================="
