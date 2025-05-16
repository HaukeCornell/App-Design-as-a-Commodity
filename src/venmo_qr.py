#!/usr/bin/env python3.11
"""
VenmoQRManager - Handles the Venmo QR code generation and payment processing.
"""
import os
import time
import json
import uuid
import logging
from typing import Dict, Any, Optional, Callable
import qrcode
import base64
import io

# Relative imports
from venmo_config import VENMO_CONFIG
from receipt_manager import receipt_manager  # Import the new receipt manager

class VenmoQRManager:
    """Manages the Venmo QR code and payment processing."""
    
    def __init__(self):
        self.venmo_base_url = VENMO_CONFIG.get("venmo_profile_url", "")
        self.qr_code_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "venmo_qr.png")
        self.last_payment = None
        self.last_generated_app = None
        self.payment_callback = None
        self.sessions = {}

    def set_base_url(self, url: Optional[str]) -> None:
        """Set the Venmo base URL."""
        self.venmo_base_url = url or VENMO_CONFIG.get("venmo_profile_url", "")

    def register_payment_callback(self, callback: Callable[[Dict[str, Any]], bool]) -> None:
        """Register a callback function for processing payments."""
        self.payment_callback = callback

    def get_venmo_qr_code(self) -> str:
        """Get the Venmo QR code as a base64-encoded string."""
        try:
            if os.path.exists(self.qr_code_path):
                with open(self.qr_code_path, "rb") as f:
                    return base64.b64encode(f.read()).decode("utf-8")
            else:
                # Generate QR code dynamically
                if self.venmo_base_url:
                    return self.generate_venmo_qr_base64()
                return ""
        except Exception as e:
            logging.error(f"Error getting Venmo QR code: {e}")
            return ""

    def generate_venmo_qr_base64(self) -> str:
        """Generate a base64-encoded QR code for the Venmo URL."""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.venmo_base_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save to buffer and encode
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            
            # Save to file for caching
            try:
                with open(self.qr_code_path, "wb") as f:
                    f.write(buffer.getvalue())
                logging.info(f"Venmo QR code saved to {self.qr_code_path}")
            except Exception as e:
                logging.error(f"Error saving Venmo QR code to file: {e}")
            
            # Return base64 encoded string
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            logging.error(f"Error generating Venmo QR code: {e}")
            return ""

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def create_session(self, app_type: str) -> Dict[str, str]:
        """Create a new session for a payment."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "app_type": app_type,
            "created": time.time(),
            "paid": False,
            "amount": 0
        }
        return {"session_id": session_id}

    def handle_payment(self, payment_data: Dict[str, Any]) -> bool:
        """
        Process a Venmo payment.
        Returns True if payment was successfully handled.
        """
        try:
            # Store the payment data
            self.last_payment = payment_data
            
            # Grab the app description from the note field
            app_description = payment_data.get("note", "Simple app").strip()
            
            # Call the payment callback if registered
            if self.payment_callback:
                return self.payment_callback(payment_data)
                
            # Import here to avoid circular imports
            from main import generate_app_for_payment
            
            # If no callback registered, process directly
            amount = float(payment_data.get("amount", 0))
            sender = payment_data.get("sender", "Unknown")
            
            # Generate the app
            generate_app_for_payment(app_description, amount, sender)
            
            return True
        except Exception as e:
            logging.error(f"Error handling payment: {e}")
            return False

# Create a global instance for use by other modules
venmo_qr_manager = VenmoQRManager()