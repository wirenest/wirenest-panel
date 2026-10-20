import os


# NOTE (split): config.py lives one level below the project root; BASE_DIR must still be the
# folder that contains data/ and logs/ (the folder holding run.py).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOT_TOKEN = "8750301426:AAGlkkPd0XEp7ghR7Vva4iXiGVh11OhhssQ"

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
