from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class Inspection(Base):
    """Модель для хранения результатов проверок"""
    __tablename__ = 'inspections'
    
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
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
    operator_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)

class DefectStatistics(Base):
    """Агрегированная статистика по дефектам"""
    __tablename__ = 'defect_statistics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(DateTime, default=datetime.utcnow)
    defect_type = Column(String)
    count = Column(Integer)
    avg_confidence = Column(Float)

# Создание БД
engine = create_engine('sqlite:///pcb_defects.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)