from cryptography.fernet import Fernet, InvalidToken
from config import DATA_ENCRYPTION_KEYS

_PREFIX = "enc:"

_primary = Fernet(DATA_ENCRYPTION_KEYS[0].encode())
_all = [Fernet(k.encode()) for k in DATA_ENCRYPTION_KEYS]

def encrypt_str(value: str) -> str:
    token = _primary.encrypt(value.encode("utf-8")).decode("utf-8")
    return _PREFIX + token

def decrypt_str(value: str) -> str:
    if not value.startswith(_PREFIX):
        return value

    token = value[len(_PREFIX):].encode("utf-8")
    for f in _all:
        try:
            return f.decrypt(token).decode("utf-8")
        except InvalidToken:
            pass
    raise ValueError("Unable to decrypt (no key matched)")
