"""Configuration management for Program Mill."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Program Mill configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM API Keys
    anthropic_api_key: str = ""
    cerebras_api_key: str = ""

    # LLM Model Configuration
    default_llm_provider: Literal["anthropic", "cerebras"] = "anthropic"
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    cerebras_model: str = "llama3.3-70b"

    # LLM Retry Configuration
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 30
    llm_max_tokens: int = 50  # For Tier 3 checks
    llm_temperature: float = 0.0

    # Analysis Configuration
    max_tokens_per_analysis: int = 100000
    analysis_timeout_seconds: int = 300
    verification_depth: Literal["quick", "standard", "rigorous"] = "standard"

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8001
    api_reload: bool = True

    # Database
    database_path: str = "pmill.db"

    # Logging
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Security
    enable_code_execution: bool = False  # NEVER enable in production
    max_code_size_bytes: int = 1048576  # 1MB
    analysis_sandbox: bool = True

    # Performance
    max_concurrent_analyses: int = 5
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600


settings = Settings()
