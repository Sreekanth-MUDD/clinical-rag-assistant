import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://sanofi_admin:sanofi_secure_pass123@localhost:5432/rag_clinical_db"
    DATABASE_SYNC_URL: str = "postgresql+psycopg://sanofi_admin:sanofi_secure_pass123@localhost:5432/rag_clinical_db"
    LLM_PROVIDER: str = "openai"  # openai or ollama
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"
    OLLAMA_LLM_MODEL: str = "llama3"
    SECRET_KEY: str = "6c93f0b2f8a846c2bf1974de452932b17a0ef19e4871e8c07cb7f7ffb587a8b3"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    UPLOAD_DIR: str = "./data/uploads"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
