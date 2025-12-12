import os
import re

from passlib.context import CryptContext

TOKEN_SECRET_KEY = os.getenv('JWT_SECRET')
if not TOKEN_SECRET_KEY:
    raise RuntimeError('Missing env variable: JWT_SECRET')
TOKEN_ALGORITHM = 'HS256'
TOKEN_EXPIRE_MINS = 60

PASSWORD_REGEX = re.compile(r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,100}$')

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
