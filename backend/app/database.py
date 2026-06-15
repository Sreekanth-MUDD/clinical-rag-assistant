import datetime
import uuid
import logging
import os
from typing import AsyncGenerator
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import text
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Global flag to signal vector store layer
USE_POSTGRES = True

# Setup database URLs
DATABASE_URL = settings.DATABASE_URL

# Create Async Engine (re-assignable globally)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True
)

# Async Session Factory (re-assignable globally)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    disease_area = Column(String, nullable=False)
    model_type = Column(String, nullable=False)
    status = Column(String, default="completed")  # completed, processing, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    documents = relationship("Document", back_populates="experiment", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    experiment_id = Column(String, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, processing, ready, error
    page_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    experiment = relationship("Experiment", back_populates="documents")

# Dependency to get session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Database initialization with automated SQLite fallback
async def init_db():
    global engine, AsyncSessionLocal, USE_POSTGRES
    try:
        async with engine.begin() as conn:
            # Try PostgreSQL vector extension
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Connected to PostgreSQL/pgvector database successfully.")
    except Exception as e:
        logger.warning(f"Failed to connect to PostgreSQL: {e}. Falling back to SQLite local database.")
        USE_POSTGRES = False
        
        # Ensure local database directory exists
        db_dir = "./data"
        os.makedirs(db_dir, exist_ok=True)
        sqlite_url = "sqlite+aiosqlite:///./data/local_rag.db"
        
        # Recreate engine and session local globally for SQLite
        engine = create_async_engine(
            sqlite_url,
            echo=False,
            future=True
        )
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Initialize tables on SQLite
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized successfully.")
