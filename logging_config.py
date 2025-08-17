"""
Logging configuration for the HBD App.
Provides centralized logging setup with file rotation and console output.
"""

import logging
import logging.handlers
import os
import json
import time
from pathlib import Path


def setup_logging(config_path: str = "config.json") -> logging.Logger:
    """
    Set up comprehensive logging for the application.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Configured logger instance
    """
    # Load logging configuration
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        log_config = config.get('logging', {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load logging config from {config_path}: {e}")
        log_config = {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/hbd_app.log",
            "max_bytes": 10485760,
            "backup_count": 5
        }
    
    # Create logs directory if it doesn't exist
    log_file = log_config.get('file', 'logs/hbd_app.log')
    log_dir = Path(log_file).parent
    log_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.get('level', 'INFO')))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=log_config.get('max_bytes', 10485760),  # 10MB
        backupCount=log_config.get('backup_count', 5)
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_config.get('level', 'INFO')))
    root_logger.addHandler(console_handler)
    
    # Create app-specific logger
    app_logger = logging.getLogger('hbd_app')
    app_logger.info("Logging system initialized")
    app_logger.info(f"Log file: {log_file}")
    app_logger.info(f"Log level: {log_config.get('level', 'INFO')}")
    
    return app_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the module/component
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f'hbd_app.{name}')


# Function to log function entry and exit (decorator)
def log_function_call(func):
    """
    Decorator to log function entry and exit with parameters and execution time.
    """
    import functools
    import time
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Entering {func.__name__} with args={args}, kwargs={kwargs}")
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"Exiting {func.__name__} successfully in {execution_time:.3f}s")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error in {func.__name__} after {execution_time:.3f}s: {str(e)}", exc_info=True)
            raise
    
    return wrapper


# Context manager for logging operations
class LoggedOperation:
    """Context manager for logging the start and end of operations."""
    
    def __init__(self, operation_name: str, logger_name: str = None):
        self.operation_name = operation_name
        self.logger = get_logger(logger_name or 'operations')
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting operation: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = time.time() - self.start_time
        if exc_type is None:
            self.logger.info(f"Completed operation: {self.operation_name} in {execution_time:.3f}s")
        else:
            self.logger.error(f"Failed operation: {self.operation_name} after {execution_time:.3f}s: {exc_val}")
        return False  # Don't suppress exceptions