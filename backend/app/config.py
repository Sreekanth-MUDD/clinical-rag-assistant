import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sanofi_admin:sanofi_secure_pass123@localhost:5432/rag_clinical_db"
    DATABASE_SYNC_URL: str = "postgresql+psycopg://sanofi_admin:sanofi_secure_pass123@localhost:5432/rag_clinical_db"
    
    # LLM Provider Configuration
    LLM_PROVIDER: str = "ollama"  # "ollama" or "openai"
    LLM_FALLBACK_PROVIDER: str = "openai"  # Fallback provider
    ENABLE_FALLBACK: bool = True  # Enable automatic fallback to OpenAI on errors
    
    # OpenAI Configuration (for fallback)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "mistral"  # Optimized for medium memory (7B parameters)
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"  # Lightweight, high-quality embeddings
    
    # Embedding Configuration
    EMBEDDING_PROVIDER: str = "bge"  # "bge" for sentence-transformers, "ollama" for Ollama embeddings
    BGE_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"  # High-quality, low-latency BGE model
    USE_BGE_EMBEDDING: bool = True  # Use BGE for better quality than Ollama embeddings
    
    # Authentication
    SECRET_KEY: str = "6c93f0b2f8a846c2bf1974de452932b17a0ef19e4871e8c07cb7f7ffb587a8b3"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # File Upload
    UPLOAD_DIR: str = "./data/uploads"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # Performance tuning
    EMBEDDING_BATCH_SIZE: int = 32  # Batch size for embedding generation
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
