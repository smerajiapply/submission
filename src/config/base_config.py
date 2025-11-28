"""Base configuration and settings"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Google Gemini Configuration
    gemini_api_key: str
    gemini_model: str = "gemini-2.0-flash-exp"
    
    # Browser Configuration
    headless: bool = False
    browser_timeout: int = 30000
    
    # Logging
    log_level: str = "INFO"
    
    # Paths
    project_root: Path = Path(__file__).parent.parent.parent
    output_dir: Path = project_root / "outputs"
    offers_dir: Path = output_dir / "offers"
    logs_dir: Path = output_dir / "logs"
    config_dir: Path = project_root / "src" / "config" / "schools"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create directories if they don't exist
        self.output_dir.mkdir(exist_ok=True)
        self.offers_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()

