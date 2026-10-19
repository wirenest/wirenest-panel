import re
import html
import urllib.parse
from datetime import datetime, timedelta

def esc(s) -> str:
    return html.escape(str(s or ""))

def num(p) -> str:
    return f"{int(p or 0):,}"

def fmt_price(p) -> str:
    return f"{num(p)} تومان"

def fmt_gb(v) -> str:
    try:
        v = float(v or 0)
        return f"{v:.1f}".rstrip("0").rstrip(".") + " GB"
    except Exception:
        return "0 GB"

def g2(v) -> str:
    try:
        v = float(v or 0)
        return f"{v:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"

def mask_mid(s: str) -> str:
    s = str(s or "")
    if len(s) < 8:
        return s
    return s[:4] + "****" + s[-4:]

def jdate(ts: str | None = None) -> str:
    try:
        if not ts:
            dt = datetime.now()
        elif isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
        else:
            dt = datetime.fromisoformat(str(ts))
        
        g_y, g_m, g_d = dt.year, dt.month, dt.day
        d_p = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        gy = g_y - 1600 if g_y > 1600 else g_y
        gm = g_m - 1
        gd = g_d - 1
        g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
        for i in range(gm):
            g_day_no += d_p[i]
        if gm > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
            g_day_no += 1
        g_day_no += gd
        j_day_no = g_day_no - 79
        j_np = j_day_no // 12053
        j_day_no %= 12053
        jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
        j_day_no %= 1461
        if j_day_no >= 366:
            jy += (j_day_no - 1) // 365
            j_day_no = (j_day_no - 1) % 365
        for i in range(11):
            length = 31 if i < 6 else 30
            if j_day_no < length:
                jm = i + 1
                jd = j_day_no + 1
                break
            j_day_no -= length
        else:
            jm = 12
            jd = j_day_no + 1
        return f"{jy}/{jm:02d}/{jd:02d} {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return str(ts or "")

def urldec(s: str) -> str:
    try:
        return urllib.parse.unquote(str(s or ""))
    except Exception:
        return str(s or "")

def strong_password() -> str:
    import secrets
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%"
    return "".join(secrets.choice(chars) for _ in range(12))

def parse_int_digits(text: str) -> int:
    text = str(text or "")
    fa_num = "۰۱۲۳۴۵۶۷۸۹"
    en_num = "0123456789"
    for f, e in zip(fa_num, en_num):
        text = text.replace(f, e)
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else 0
