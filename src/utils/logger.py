"""Logging configuration using loguru"""

import sys
from pathlib import Path
from loguru import logger
from src.config.base_config import settings


def setup_logger(log_file: str = "automation.log"):
    """Configure logger with file and console output"""
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with colors
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=settings.log_level,
        colorize=True,
    )
    
    # Add file handler
    log_path = settings.logs_dir / log_file
    logger.add(
        log_path,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
    )
    
    logger.info(f"Logger initialized. Logs saved to: {log_path}")
    return logger


# Initialize default logger
log = setup_logger()


