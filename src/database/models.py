from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import bcrypt
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()

class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default='operator')  # admin, supervisor, operator
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)
    
    # Связь с проверками
    inspections = relationship("Inspection", back_populates="operator")
    
    def verify_password(self, password: str) -> bool:
        # Хеш в БД хранится как строка, bcrypt ожидает bytes
        password_bytes = password.encode('utf-8')
        hashed_bytes = self.hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    
    @staticmethod
    def hash_password(password: str) -> str:
        # Генерируем соль и хешируем
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8') # Сохраняем в БД как строку

class Inspection(Base):
    """Модель для хранения результатов проверок"""
    __tablename__ = 'inspections'
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    filename = Column(String)
    image_width = Column(Integer)
    image_height = Column(Integer)
    confidence_threshold = Column(Float)
    total_defects = Column(Integer)
    status = Column(String)
    severity_breakdown = Column(JSON)
    detections = Column(JSON)
    result_image_path = Column(String, nullable=True)
    processing_time = Column(Float)  # в секундах
    operator_id = Column(String, ForeignKey('users.id'), nullable=True)
    operator = relationship("User", back_populates="inspections")
    notes = Column(String, nullable=True)

class DefectStatistics(Base):
    """Агрегированная статистика по дефектам"""
    __tablename__ = 'defect_statistics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    defect_type = Column(String)
    count = Column(Integer)
    avg_confidence = Column(Float)

class ProductionLine(Base):
    """Модель производственной линии"""
    __tablename__ = 'production_lines'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Настройки линии
    default_confidence = Column(Float, default=0.25)
    auto_reject_on_critical = Column(Boolean, default=True)

class DefectTemplate(Base):
    """Шаблоны дефектов для различных типов плат"""
    __tablename__ = 'defect_templates'
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    board_type = Column(String)  # single-layer, multi-layer, flex, etc.
    acceptable_defects = Column(JSON)  # какие дефекты допустимы
    critical_thresholds = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# Создание БД
engine = create_engine('sqlite:///pcb_defects.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    """Зависимость для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()