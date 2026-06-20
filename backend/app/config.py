import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Use SQLite only for simplicity and reliability
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/local_rag.db"
    
    # LLM Provider Configuration
    LLM_PROVIDER: str = "ollama"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3"  # Default Ollama LLM model
    
    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "bge"  # Use BGE for faster embeddings
    USE_BGE_EMBEDDING: bool = True  # Enable BGE embeddings for performance
    BGE_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    
    # Vector Store Configuration
    VECTOR_STORE_TYPE: str = "faiss"  # Use FAISS for reliable vector storage
    
    # Authentication
    SECRET_KEY: str = "6c93f0b2f8a846c2bf1974de452932b17a0ef19e4871e8c07cb7f7ffb587a8b3"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # File Upload
    UPLOAD_DIR: str = "./data/uploads"
    CHUNK_SIZE: int = 2000  # Increased from 1000 to reduce number of chunks
    CHUNK_OVERLAP: int = 400  # Increased from 200 to maintain context
    
    # Performance tuning
    EMBEDDING_BATCH_SIZE: int = 64  # Increased from 32 for faster processing
    LLM_TEMPERATURE: float = 0.2
    LLM_STREAMING: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
