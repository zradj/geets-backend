import os
import re

from passlib.context import CryptContext

TOKEN_SECRET_KEY = os.getenv('JWT_SECRET')
assert(TOKEN_SECRET_KEY is not None)
TOKEN_ALGORITHM = 'HS256'
TOKEN_EXPIRE_MINS = 60

PASSWORD_REGEX = re.compile(r'((?=\d)(?=[a-z])(?=[A-Z])(?=[\W]).{8,64})')

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
