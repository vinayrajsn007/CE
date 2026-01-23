"""
Logging Configuration Utility
Sets up logging to both console and file

Usage:
    from utils.logging_config import setup_logging
    
    setup_logging()
    logger = logging.getLogger(__name__)
"""

import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
import pytz

# IST timezone
IST = pytz.timezone('Asia/Kolkata')


def setup_logging(level=logging.INFO, log_dir="logs", log_prefix="trading"):
    """
    Setup logging configuration to write to both console and file
    
    Args:
        level: Logging level (default: logging.INFO)
        log_dir: Directory to store log files (default: "logs")
        log_prefix: Prefix for log file names (default: "trading")
    
    Returns:
        None
    """
    root_logger = logging.getLogger()
    
    # Check if logging is already configured (has handlers)
    if root_logger.handlers:
        # Logging already configured, just update level if needed
        root_logger.setLevel(level)
        return
    
    # Create logs directory if it doesn't exist
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Get current date in IST for log file naming
    current_date = datetime.now(IST).strftime('%Y-%m-%d')
    log_filename = os.path.join(log_dir, f"{log_prefix}_{current_date}.log")
    
    # Set logging level
    root_logger.setLevel(level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (StreamHandler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (RotatingFileHandler - rotates when file reaches 10MB, keeps 5 backups)
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Log the log file location
    root_logger.info(f"Logging initialized. Log file: {os.path.abspath(log_filename)}")
