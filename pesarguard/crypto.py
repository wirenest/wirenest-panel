from pesarguard import bootstrap as _bootstrap  # noqa: F401  (keeps original import-time order)
import base64
import os
import secrets
from pesarguard.bootstrap import bot_log
from pesarguard.config import BASE_DIR, PANEL_CRYPTO_KEY


def panel_crypto_key() -> str:
    k = PANEL_CRYPTO_KEY
    if k:
        return k
    kf = os.path.join(BASE_DIR, "data", "crypto.key")
    if os.path.isfile(kf):
        return open(kf).read().strip()
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    with open(kf, "w") as f:
        f.write(key)
    try:
        os.chmod(kf, 0o600)
    except Exception:
        pass
    return key

def panel_encrypt_pw(plain: str) -> str:
    if not plain:
        return ""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = base64.b64decode(panel_crypto_key())
    iv = secrets.token_bytes(12)
    ct_tag = AESGCM(key).encrypt(iv, plain.encode(), None)
    ct, tag = ct_tag[:-16], ct_tag[-16:]
    return "phpenc2:" + base64.b64encode(iv + tag + ct).decode()

def panel_decrypt_pw(enc: str) -> str:
    if not enc:
        return ""
    try:
        if enc.startswith("phpenc2:"):
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            raw = base64.b64decode(enc[8:])
            if len(raw) < 28:
                return ""
            iv, tag, ct = raw[:12], raw[12:28], raw[28:]
            return AESGCM(base64.b64decode(panel_crypto_key())).decrypt(iv, ct + tag, None).decode()
        if enc.startswith("phpenc:"):
            from cryptography.hazmat.primitives import padding
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            raw = base64.b64decode(enc[7:])
            if len(raw) < 16:
                return ""
            c = Cipher(algorithms.AES(base64.b64decode(panel_crypto_key())), modes.CBC(raw[:16])).decryptor()
            padded = c.update(raw[16:]) + c.finalize()
            un = padding.PKCS7(128).unpadder()
            return (un.update(padded) + un.finalize()).decode()
        if enc.startswith("pyfer:"):
            return enc[6:]
        if enc.startswith("gAAAA"):
            from cryptography.fernet import Fernet

            key = panel_crypto_key()
            key = key + "=" * (-len(key) % 4)
            return Fernet(key.encode()).decrypt(enc.encode()).decode()
    except Exception as e:
        bot_log(f"decrypt failed: {e}")
        return ""
    return enc
