import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker

from src.database.models import Base

db_url = URL.create(
    drivername=os.getenv("DB_DRIVER", "postgresql+psycopg2"),
    username=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASS", "postgres"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 5432)),
    database=os.getenv("DB_NAME", "defectnet")
)

DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_engine(
    db_url,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    """Dependency for obtaining a database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
