import os
import time
import logging
from datetime import datetime

# Logging Setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("PesarguardBot")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOT_TOKEN = "8500420442:AAHQZ4CtgjuvBuEi-X3Mb9mRG19n8u8R6pk"
ADMIN_ID = 7254045901
SUPPORT_ID = ""
CARD_NUMBER = ""
CARD_OWNER = ""
PANEL_CRYPTO_KEY = ""
PANEL_RELAY_URL = ""
PANEL_RELAY_KEY = ""
PANEL_VERIFY_SSL = True

DB_PATH = os.path.join(BASE_DIR, "data", "bot.sqlite")
STATE_FILE = os.path.join(BASE_DIR, "data", "state.json")
LOG_FILE = os.path.join(BASE_DIR, "logs", "bot.log")

os.environ.setdefault("TZ", "Asia/Tehran")
try:
    time.tzset()
except Exception:
    pass

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

def log_event(module: str, event: str, level: str = "INFO", details: str = ""):
    msg = f"[{module.upper()}] {event}" + (f" | Details: {details}" if details else "")
    if level == "ERROR":
        logger.error(msg)
    elif level == "WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now_str}] [{level}] {msg}\n")

