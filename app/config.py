"""
Configuration management for the Telesales Intelligence System.
Loads environment variables and enforces validation with Pydantic Settings.
"""

from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://telesales:telesales_secret@127.0.0.1:5434/telesales_db",
        description="SQLAlchemy database connection URI (PostgreSQL)"
    )

    # Cohere API
    COHERE_API_KEY: Optional[str] = Field(
        default=None,
        description="Cohere API authorization key"
    )
    COHERE_MODEL: str = Field(
        default="command-r-plus-08-2024",
        description="Cohere pretrained model identifier for complex reasoning"
    )
    COHERE_EMBED_MODEL: str = Field(
        default="embed-multilingual-v3.0",
        description="Cohere multilingual embedding model identifier"
    )
    COHERE_TEMPERATURE: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Model temperature (0.0 for deterministic extraction)"
    )
    COHERE_TIMEOUT_SECONDS: int = Field(
        default=60,
        gt=0,
        description="Cohere HTTP request timeout in seconds"
    )
    COHERE_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts on Cohere rate limits or transient errors"
    )
    COHERE_MOCK_MODE: str = Field(
        default="auto",
        description="'true', 'false', or 'auto' (activates offline mock if API key is missing)"
    )

    # Analysis & Coaching
    COACHING_LANGUAGE: Literal["ar", "en"] = Field(
        default="ar",
        description="Target language for generated coaching actions ('ar' for Jordanian Arabic, 'en' for English)"
    )

    # Ingestion & Concurrency
    BATCH_CONCURRENCY: int = Field(
        default=4,
        gt=0,
        description="Maximum concurrent calls processed in batch runner"
    )
    TRANSCRIPTS_FOLDER_PATH: str = Field(
        default="./data/sample_transcripts",
        description="Default folder path for batch transcript ingestion"
    )

    # Microsoft Power BI Service API (Optional post-batch refresh)
    POWERBI_REFRESH_ENABLED: bool = Field(
        default=False,
        description="Whether to trigger Power BI dataset refresh after batch analysis"
    )
    POWERBI_TENANT_ID: Optional[str] = None
    POWERBI_CLIENT_ID: Optional[str] = None
    POWERBI_CLIENT_SECRET: Optional[str] = None
    POWERBI_WORKSPACE_ID: Optional[str] = None
    POWERBI_DATASET_ID: Optional[str] = None

    # Server Runtime
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_mock_llm(self) -> bool:
        """Determines whether the LLM client should run in mock/offline mode."""
        mode = self.COHERE_MOCK_MODE.strip().lower()
        if mode in ("true", "1", "yes"):
            return True
        if mode in ("false", "0", "no"):
            return False
        # 'auto' mode: if API key is missing or dummy placeholder, use mock
        return not bool(self.COHERE_API_KEY and self.COHERE_API_KEY.strip() and "your_cohere" not in self.COHERE_API_KEY)


settings = Settings()
