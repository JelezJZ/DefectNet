import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///pcb_defects.db")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(bind=engine)


def get_db():
    """Dependency for obtaining a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
