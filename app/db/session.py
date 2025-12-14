from pathlib import Path
from sqlmodel import Session, SQLModel, create_engine

from schemas import *

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

sqlite_file = DATA_DIR / "database.db"
sqlite_url = f"sqlite:///{sqlite_file}"

engine = create_engine(
    sqlite_url,
    echo=True,
    connect_args={"check_same_thread": False},
)

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
