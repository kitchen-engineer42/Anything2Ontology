"""Configuration management for ontology assembly module."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ontology assembly configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Shared paths
    output_dir: Path = Field(default=Path("./output"))
    skus_output_dir: Path = Field(default=Path("./output/skus"))
    log_dir: Path = Field(default=Path("./logs"))

    # Module 4: Ontology
    ontology_dir: Path = Field(default=Path("./ontology"))

    # LLM Configuration (SiliconFlow)
    siliconflow_api_key: str = Field(default="")
    siliconflow_base_url: str = Field(default="https://api.siliconflow.cn/v1")
    chatbot_model: str = Field(
        default="Pro/zai-org/GLM-5",
        description="Model for spec chatbot",
    )
    max_chat_rounds: int = Field(default=5)
    chatbot_temperature: float = Field(default=0.4)
    chatbot_max_tokens: int = Field(default=8000)

    # Language
    language: Literal["en", "zh"] = Field(default="en")

    # Logging
    log_level: str = Field(default="INFO")
    log_format: Literal["json", "text", "both"] = Field(default="both")


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()


# Default singleton
settings = Settings()
