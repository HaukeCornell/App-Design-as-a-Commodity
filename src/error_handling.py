#!/usr/bin/env python3.11
"""
Standardized error handling for Vibe Coder application.
This module provides consistent error handling and logging mechanisms.
"""
import logging
import traceback
import sys
import json
from typing import Dict, Any, Optional, Callable, Type, Union
from functools import wraps
from flask import jsonify, Response

# Configure logger
logger = logging.getLogger(__name__)

# Error codes
class ErrorCodes:
    """Standardized error codes for the application."""
    # General errors (1000-1999)
    UNKNOWN_ERROR = 1000
    CONFIGURATION_ERROR = 1001
    INVALID_INPUT = 1002
    
    # API errors (2000-2999)
    API_ERROR = 2000
    RATE_LIMIT_EXCEEDED = 2001
    AUTHENTICATION_FAILED = 2002
    AUTHORIZATION_FAILED = 2003
    RESOURCE_NOT_FOUND = 2004
    
    # Thermal printer errors (3000-3999)
    PRINTER_CONNECTION_ERROR = 3000
    PRINTER_COMMUNICATION_ERROR = 3001
    
    # GitHub errors (4000-4999)
    GITHUB_API_ERROR = 4000
    GITHUB_AUTHENTICATION_ERROR = 4001
    GITHUB_REPO_EXISTS = 4002
    GITHUB_REPO_CREATION_ERROR = 4003
    GIT_COMMAND_ERROR = 4004
    
    # Venmo errors (5000-5999)
    VENMO_EMAIL_ERROR = 5000
    VENMO_PAYMENT_ERROR = 5001
    VENMO_PARSING_ERROR = 5002
    
    # Generation errors (6000-6999)
    GEMINI_API_ERROR = 6000
    APP_GENERATION_ERROR = 6001
    CONTENT_CREATION_ERROR = 6002

class AppError(Exception):
    """Base exception class for application-specific errors."""
    
    def __init__(self, 
                 message: str, 
                 code: int = ErrorCodes.UNKNOWN_ERROR, 
                 details: Optional[Dict[str, Any]] = None,
                 original_exception: Optional[Exception] = None):
        """
        Initialize the application error.
        
        Args:
            message: Human-readable error message
            code: Numeric error code for categorization and lookup
            details: Additional structured information about the error
            original_exception: The original exception that caused this error, if any
        """
        self.message = message
        self.code = code
        self.details = details or {}
        self.original_exception = original_exception
        
        # Include original exception info in details if available
        if original_exception:
            if 'original_exception' not in self.details:
                self.details['original_exception'] = {
                    'type': type(original_exception).__name__,
                    'message': str(original_exception)
                }
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the error to a dictionary representation."""
        error_dict = {
            'error': {
                'code': self.code,
                'message': self.message
            }
        }
        
        if self.details:
            error_dict['error']['details'] = self.details
            
        return error_dict
        
    def to_response(self, status_code: int = 400) -> Response:
        """Convert the error to a Flask response."""
        return jsonify(self.to_dict()), status_code

class ValidationError(AppError):
    """Error raised when validation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCodes.INVALID_INPUT, details, original_exception)

class ConfigurationError(AppError):
    """Error raised when there's a configuration issue."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCodes.CONFIGURATION_ERROR, details, original_exception)

class APIError(AppError):
    """Error raised when an external API request fails."""
    
    def __init__(self, 
                 message: str, 
                 code: int = ErrorCodes.API_ERROR, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None):
        super().__init__(message, code, details, original_exception)

class GitHubError(APIError):
    """Error raised when GitHub API operations fail."""
    
    def __init__(self, 
                 message: str, 
                 code: int = ErrorCodes.GITHUB_API_ERROR, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None):
        super().__init__(message, code, details, original_exception)

class PrinterError(AppError):
    """Error raised when thermal printer operations fail."""
    
    def __init__(self, 
                 message: str, 
                 code: int = ErrorCodes.PRINTER_CONNECTION_ERROR, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None):
        super().__init__(message, code, details, original_exception)

class GeminiError(APIError):
    """Error raised when Gemini API operations fail."""
    
    def __init__(self, 
                 message: str, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None):
        super().__init__(message, ErrorCodes.GEMINI_API_ERROR, details, original_exception)

class VenmoError(AppError):
    """Error raised when Venmo operations fail."""
    
    def __init__(self, 
                 message: str, 
                 code: int = ErrorCodes.VENMO_EMAIL_ERROR, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None):
        super().__init__(message, code, details, original_exception)

def handle_exception(exc: Exception, log_level: int = logging.ERROR) -> Dict[str, Any]:
    """
    Handle an exception and return a standardized error response.
    
    Args:
        exc: The exception to handle
        log_level: The logging level to use (default: ERROR)
        
    Returns:
        Standardized error response dictionary
    """
    # Handle AppError instances directly
    if isinstance(exc, AppError):
        logger.log(log_level, f"{type(exc).__name__}: {exc.message}", exc_info=True)
        return exc.to_dict()
    
    # Convert standard exceptions to AppError format
    error_code = ErrorCodes.UNKNOWN_ERROR
    error_message = "An unexpected error occurred"
    
    # Extract additional details from the exception
    details = {
        'exception_type': type(exc).__name__,
        'traceback': traceback.format_exc()
    }
    
    # Log the error
    logger.log(log_level, f"Unhandled exception: {type(exc).__name__}: {str(exc)}", exc_info=True)
    
    # Return standardized error format
    return {
        'error': {
            'code': error_code,
            'message': error_message,
            'details': details
        }
    }

def exception_handler(func: Callable) -> Callable:
    """
    Decorator to standardize exception handling.
    
    Args:
        func: The function to wrap with exception handling
        
    Returns:
        Wrapped function with standardized exception handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_response = handle_exception(e)
            if 'flask' in sys.modules:
                from flask import jsonify
                return jsonify(error_response), 500
            return error_response
    return wrapper

def api_exception_handler(func: Callable) -> Callable:
    """
    Decorator specifically for Flask API routes.
    
    Args:
        func: The API route function to wrap
        
    Returns:
        Wrapped function with standardized API exception handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppError as e:
            # Use the appropriate status code based on the error type
            status_code = 400
            if isinstance(e, ValidationError):
                status_code = 400
            elif e.code in [ErrorCodes.RESOURCE_NOT_FOUND]:
                status_code = 404
            elif e.code in [ErrorCodes.AUTHENTICATION_FAILED, ErrorCodes.AUTHORIZATION_FAILED]:
                status_code = 401
            elif e.code in [ErrorCodes.RATE_LIMIT_EXCEEDED]:
                status_code = 429
                
            return jsonify(e.to_dict()), status_code
        except Exception as e:
            # Handle unexpected exceptions
            error_response = handle_exception(e)
            return jsonify(error_response), 500
    return wrapper

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> None:
    """
    Validate that all required fields are present in the provided data.
    
    Args:
        data: Dictionary containing data to validate
        required_fields: List of required field names
        
    Raises:
        ValidationError: If any required fields are missing
    """
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {', '.join(missing_fields)}",
            {'missing_fields': missing_fields}
        )

def log_and_raise(error_class: Type[AppError], 
                 message: str, 
                 log_level: int = logging.ERROR, 
                 code: Optional[int] = None, 
                 details: Optional[Dict[str, Any]] = None, 
                 original_exception: Optional[Exception] = None) -> None:
    """
    Log an error message and raise an AppError.
    
    Args:
        error_class: AppError subclass to raise
        message: Error message
        log_level: Logging level
        code: Error code (if None, the default for the error class will be used)
        details: Additional error details
        original_exception: Original exception, if any
        
    Raises:
        AppError: The specified error class
    """
    logger.log(log_level, message, exc_info=original_exception is not None)
    
    if code:
        raise error_class(message, code, details, original_exception)
    else:
        raise error_class(message, details=details, original_exception=original_exception)