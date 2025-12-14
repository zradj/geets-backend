from sqlalchemy.types import TypeDecorator, String
from utils.crypto import encrypt_str, decrypt_str

class EncryptedString(TypeDecorator):
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_str(value)