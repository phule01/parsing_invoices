from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/tool_orc_db")

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool if "sqlite" not in DATABASE_URL else None,
    echo=os.getenv("DEBUG", "False").lower() == "true"
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
