import logging
import os
import sys
import time
from pesarguard.config import DB_PATH, LOG_FILE, STATE_FILE


os.environ.setdefault("TZ", "Asia/Tehran")

try:
    time.tzset()
except Exception:
    pass

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)

def bot_log(msg: str) -> None:
    logging.info(msg)
