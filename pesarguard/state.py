from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import json
import os
import threading
from pesarguard.config import STATE_FILE


_STATE_LOCK = threading.RLock()

try:
    with open(STATE_FILE, encoding="utf-8") as _f:
        STATE: dict = json.load(_f) or {}
except Exception:
    STATE = {}

def _state_save() -> None:
    with _STATE_LOCK:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATE, f, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)

def st_get(uid: int, k: str, default=None):
    v = STATE.get(str(uid), {}).get(k, default)
    return default if v is None else v

def st_set(uid: int, kv: dict) -> None:
    STATE.setdefault(str(uid), {}).update(kv)
    _state_save()

def st_pop(uid: int) -> None:
    STATE.pop(str(uid), None)
    _state_save()

def st_all(uid: int) -> dict:
    return dict(STATE.get(str(uid), {}))
