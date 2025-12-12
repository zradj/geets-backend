from enum import Enum
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel

from db.session import init_db

app = FastAPI()

@app.get('/')
async def read_root():
    return {'Hello': 'World'}

def main():
    init_db()

if __name__ == '__main__':
    main()
