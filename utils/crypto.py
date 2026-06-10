import json
import hashlib
from base64 import b64decode

try:
    # pyrefly: ignore [missing-import]
    from Crypto.Cipher import AES
    CRYPTO_ENABLED = True
except ImportError:
    CRYPTO_ENABLED = False

def is_crypto_enabled():
    return CRYPTO_ENABLED

def decrypt_aes_ecb(params_value, secret_key):
    """
    Phương thức giải mã dự phòng sử dụng AES-ECB.
    Yêu cầu thư viện pycryptodome phải được cài đặt trước.
    """
    if not CRYPTO_ENABLED:
        raise ImportError("pycryptodome chưa được cài đặt. Vui lòng chạy: pip install pycryptodome")
    
    raw = b64decode(params_value)
    key = hashlib.md5(secret_key.encode()).digest()
    cipher = AES.new(key, AES.MODE_ECB)
    dec = cipher.decrypt(raw)
    pad = dec[-1]
    payload = dec[:-pad].decode(errors="ignore")
    return json.loads(payload)
