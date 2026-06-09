"""Loguru logging setup with console + JSON file output."""
import sys
from pathlib import Path
from loguru import logger

# Ensure logs directory exists
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Console output (colorized for dev)
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# JSON file output (for production log aggregation)
logger.add(
    logs_dir / "app_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
    level="DEBUG",
    rotation="00:00",  # Rotate at midnight
    retention="30 days",
    compression="zip",
    serialize=True,  # JSON format
)

# Error log file (separate, always includes traceback)
logger.add(
    logs_dir / "error_{time:YYYY-MM-DD}.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}\n{exception}",
    level="ERROR",
    rotation="00:00",
    retention="90 days",
    compression="zip",
    backtrace=True,
    diagnose=True,
)