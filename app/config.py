from pathlib import Path
import os
from dotenv import load_dotenv
import re

from passlib.context import CryptContext

RMQ_URL = 'amqp://guest:guest@localhost'

ENV_PATH = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=ENV_PATH)

TOKEN_SECRET_KEY = os.getenv('JWT_SECRET')
if not TOKEN_SECRET_KEY:
    raise RuntimeError('Missing env variable: JWT_SECRET')
TOKEN_ALGORITHM = 'HS256'
TOKEN_EXPIRE_MINS = 60

PASSWORD_REGEX = re.compile(r'^(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[a-zA-Z]).{8,100}$')

pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')

DATA_ENCRYPTION_KEYS_RAW = os.getenv('DATA_ENCRYPTION_KEYS')
if not DATA_ENCRYPTION_KEYS_RAW:
    raise RuntimeError('Missing env variable: DATA_ENCRYPTION_KEYS')

DATA_ENCRYPTION_KEYS = [k.strip() for k in DATA_ENCRYPTION_KEYS_RAW.split(',') if k.strip()]
if not DATA_ENCRYPTION_KEYS:
    raise RuntimeError('Missing env variable: DATA_ENCRYPTION_KEYS')
