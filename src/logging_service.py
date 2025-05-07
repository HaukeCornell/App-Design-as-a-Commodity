#!/usr/bin/env python3.11
"""
Logging service for Vibe Coder application.
This module provides functionality for logging messages to memory and console.
"""
import time
import logging
from typing import Dict, List, Any, Optional

# Import error handling
from src.error_handling import exception_handler

class LoggingService:
    """Service class for handling application logs."""
    
    def __init__(self):
        """Initialize the logging service."""
        self.application_logs = []  # Store logs in memory
        self.log_id_counter = 0  # Counter for log IDs
        
        # Configure logger
        self.logger = logging.getLogger(__name__)
    
    @exception_handler
    def add_log(self, message: str, level: str = "info") -> Dict[str, Any]:
        """
        Add a log entry to the application logs.
        
        Args:
            message: The log message text
            level: Log level (info, warning, error, debug)
            
        Returns:
            Dictionary containing the log entry
        """
        self.log_id_counter += 1
        
        log_entry = {
            "id": self.log_id_counter,
            "timestamp": time.time(),
            "message": message,
            "level": level
        }
        
        # Add to in-memory log store (limit to 1000 entries)
        self.application_logs.append(log_entry)
        if len(self.application_logs) > 1000:
            self.application_logs.pop(0)  # Remove oldest log
            
        # Also print to console
        print(f"[{level.upper()}] {message}")
        
        # Log to the appropriate logger level
        if level == "info":
            self.logger.info(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "debug":
            self.logger.debug(message)
            
        return log_entry
    
    def get_logs(self, limit: Optional[int] = None, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get logs from memory, optionally filtered by level and limited in count.
        
        Args:
            limit: Maximum number of logs to return (most recent)
            level: Filter logs by level (info, warning, error, debug)
            
        Returns:
            List of log entries
        """
        # Filter by level if specified
        if level:
            filtered_logs = [log for log in self.application_logs if log["level"] == level]
        else:
            filtered_logs = self.application_logs.copy()
            
        # Apply limit if specified
        if limit and limit > 0:
            filtered_logs = filtered_logs[-limit:]
            
        return filtered_logs
    
    def clear_logs(self) -> None:
        """Clear all logs from memory."""
        self.application_logs = []
        self.logger.info("Logs cleared from memory")
    
    def setup_custom_logger(self, name: str) -> logging.Logger:
        """
        Create and configure a custom logger with a specific name.
        
        Args:
            name: Name for the logger
            
        Returns:
            Configured logger instance
        """
        custom_logger = logging.getLogger(name)
        
        # Add a handler that will call our add_log method
        class CustomLogHandler(logging.Handler):
            def __init__(self, log_service):
                super().__init__()
                self.log_service = log_service
                
            def emit(self, record):
                level = record.levelname.lower()
                if level == 'critical':
                    level = 'error'  # Map critical to error for UI
                self.log_service.add_log(record.getMessage(), level)
                
        custom_logger.addHandler(CustomLogHandler(self))
        return custom_logger

# Create singleton instance
logging_service = LoggingService()