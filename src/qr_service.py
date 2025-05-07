#!/usr/bin/env python3.11
"""
QR code generation service for Vibe Coder application.
This module handles creation of QR codes for various application uses.
"""
import io
import base64
import logging
import qrcode
from typing import Optional

# Import error handling
from src.error_handling import exception_handler

# Set up logging
logger = logging.getLogger(__name__)

class QRCodeService:
    """Service class for handling QR code generation."""
    
    @staticmethod
    @exception_handler
    def generate_base64(url: str, box_size: int = 10, border: int = 4) -> str:
        """
        Generate a QR code for a URL and return as base64 encoded PNG.
        
        Args:
            url: The URL to encode in the QR code
            box_size: Size of each box in the QR code
            border: Size of the border around the QR code
            
        Returns:
            Base64 encoded PNG image of the QR code
        """
        try:
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=box_size,
                border=border,
            )
            
            # Add data
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            return img_base64
            
        except Exception as e:
            logger.error(f"Error generating QR code for {url}: {e}")
            return ""
    
    @staticmethod
    @exception_handler
    def generate_file(url: str, file_path: str, box_size: int = 10, border: int = 4) -> bool:
        """
        Generate a QR code and save it to a file.
        
        Args:
            url: The URL to encode in the QR code
            file_path: Path where the QR code image should be saved
            box_size: Size of each box in the QR code
            border: Size of the border around the QR code
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create QR code instance
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=box_size,
                border=border,
            )
            
            # Add data
            qr.add_data(url)
            qr.make(fit=True)
            
            # Create image and save to file
            img = qr.make_image(fill_color="black", back_color="white")
            img.save(file_path)
            
            logger.info(f"QR code for '{url}' saved to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving QR code to file {file_path}: {e}")
            return False

# Create singleton instance
qr_service = QRCodeService()