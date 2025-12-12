from sqlmodel import SQLModel, create_engine

from schemas import *

sqlite_file_name = 'data/database.db'
sqlite_url = f'sqlite:///{sqlite_file_name}'

engine = create_engine(sqlite_url, echo=True)

def init_db():
    SQLModel.metadata.create_all(engine)
