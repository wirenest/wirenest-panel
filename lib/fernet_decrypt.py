#!/usr/bin/env python3
"""fernet_decrypt.py — decrypt a raw python-Fernet token (argv[1]) using PANEL_CRYPTO_KEY from /root/marzban-bot/.env."""
import base64
import os
import sys

from cryptography.fernet import Fernet


def main() -> None:
    if len(sys.argv) < 2:
        print("")
        return
    tok = sys.argv[1]
    key = ""
    # primary: this project's own key file (portable, BASE_DIR-relative)
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "crypto.key"),
        "/root/marzban-bot/.env",  # legacy fallback (old python project)
    ]
    for envf in candidates:
        if not os.path.exists(envf):
            continue
        if envf.endswith(".key"):
            key = open(envf).read().strip()  # raw key file
            break
        for line in open(envf):
            if line.startswith("PANEL_CRYPTO_KEY="):
                key = line.split("=", 1)[1].strip()
                break
        if key:
            break
    if not key:
        print("")
        return
    key = key + "=" * (-len(key) % 4)
    try:
        print(Fernet(key.encode()).decrypt(tok.encode()).decode())
    except Exception:
        print("")


if __name__ == "__main__":
    main()
