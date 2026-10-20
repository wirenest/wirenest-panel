from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import html
import re
import secrets
import urllib.parse
from datetime import datetime


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)

def num(p) -> str:
    return f"{int(round(float(p))):,}"

def fmt_price(p) -> str:
    return num(p) + " تومان"

def fmt_gb(v) -> str:
    f = float(v)
    if f == int(f):
        return str(int(f))
    return f"{f:.2f}".rstrip("0").rstrip(".")

def g2(v) -> str:
    return "%g" % float(v)

def mask_mid(s: str) -> str:
    s = str(s)
    if len(s) <= 6:
        return s
    return s[:4] + "****" + s[-2:]

def jdate(ts: str | None = None) -> str:
    try:
        dt = datetime.fromisoformat(ts) if ts else datetime.now()
    except Exception:
        return str(ts)
    gy, gm, gd = dt.year, dt.month, dt.day
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy <= 1600:
        jy = 0
        gy -= 621
    else:
        jy = 979
        gy -= 1600
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return f"{jy:04d}/{jm:02d}/{jd:02d} {dt.hour:02d}:{dt.minute:02d}"

def urldec(s: str) -> str:
    return urllib.parse.unquote(s)

def gen_username(prefix: str = "srv") -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return prefix + "".join(secrets.choice(chars) for _ in range(8))

def strong_password() -> str:
    lower, upper, digit, special = "abcdefghjkmnpqrstuvwxyz", "ABCDEFGHJKLMNPQRSTUVWXYZ", "23456789", "!@#$%&*?"
    chars = (
        [secrets.choice(lower) for _ in range(6)]
        + [secrets.choice(upper) for _ in range(3)]
        + [secrets.choice(digit) for _ in range(3)]
        + [secrets.choice(special)]
    )
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)

def parse_int_digits(text: str) -> int:
    m = re.search(r"\d+", text.replace(",", ""))
    return int(m.group(0)) if m else 0

def valid_panel_name(name: str) -> bool:
    return bool(name) and ":" not in name and "%" not in name and len(name.encode("utf-8")) <= 28

def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False
