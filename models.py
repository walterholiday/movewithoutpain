from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import date

Base = declarative_base()

class Exercise(Base):
    __tablename__ = "exercises"
    id = Column(Integer, primary_key=True)
    category = Column(String(20), nullable=False)
    order = Column(Integer, nullable=False)
    
    name_en = Column(String(100), nullable=False)
    name_es = Column(String(100), nullable=False)
    description_en = Column(Text, nullable=False)
    description_es = Column(Text, nullable=False)
    reps_or_time_en = Column(String(50), nullable=False)
    reps_or_time_es = Column(String(50), nullable=False)
    tips_en = Column(Text, nullable=True)
    tips_es = Column(Text, nullable=True)
    
    youtube_video_id = Column(String(20), nullable=True)
    image_url = Column(String(255), nullable=True)
    # Comma-separated routine path slugs, e.g. "full,mobility,morning"
    paths = Column(String(120), nullable=True)

class DailyTip(Base):
    __tablename__ = "daily_tips"
    id = Column(Integer, primary_key=True)
    tip_date = Column(Date, unique=True, nullable=False)
    content_en = Column(Text, nullable=False)
    content_es = Column(Text, nullable=False)
    generated_by_ai = Column(Boolean, default=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/movewithoutpain")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
