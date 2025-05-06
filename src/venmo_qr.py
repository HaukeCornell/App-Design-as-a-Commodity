#!/usr/bin/env python3.11
"""
Venmo QR code management module.
This module handles the generation and management of Venmo QR codes,
as well as processing Venmo payments received through the email system.
"""
import os
import time
import uuid
import logging
import base64
from typing import Dict, Optional, Any, Callable
from datetime import datetime, timedelta

# Import config
from src.venmo_config import VENMO_CONFIG, SESSION_CONFIG

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('venmo_qr')

class VenmoQRManager:
    """Manager class for handling Venmo QR codes and payment sessions."""
    
    def __init__(self):
        """Initialize the Venmo QR manager."""
        self.sessions = {}  # Dictionary to store active sessions
        self.base_url = None  # Base URL for the application (set on first request)
        self.qr_code_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                         "venmo-sandhaus-qr-code.png")
        
        # Last received payment (for UI display)
        self.last_payment = None
        
        # Last generated app (for UI display)
        self.last_generated_app = None
        
    def set_base_url(self, url: str) -> None:
        """Set the base URL for the application."""
        self.base_url = url
        logger.info(f"Base URL set to: {url}")
        
    def get_venmo_qr_code(self) -> str:
        """
        Get the base64-encoded Venmo QR code image.
        
        Returns:
            Base64-encoded PNG image of the QR code
        """
        try:
            # Read the static QR code file
            with open(self.qr_code_path, "rb") as f:
                img_data = f.read()
                img_base64 = base64.b64encode(img_data).decode("utf-8")
                logger.info("Successfully loaded Venmo QR code image")
                return img_base64
        except Exception as e:
            logger.error(f"Error loading Venmo QR code image: {e}")
            return ""
        
    def create_payment_session(self, app_type: str) -> Dict[str, Any]:
        """
        Create a new payment session for a requested app.
        
        Args:
            app_type: The type of app being requested
            
        Returns:
            Dict containing session details including session_id and venmo_qr_code
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Create the session object
        session = {
            "id": session_id,
            "created_at": time.time(),
            "expires_at": time.time() + SESSION_CONFIG["session_timeout"],
            "app_type": app_type,
            "paid": False,
            "amount": None,
            "payment_timestamp": None,
            "sender": None,
            "payment_id": None,
            "payment_note": None
        }
        
        # Store the session
        self.sessions[session_id] = session
        logger.info(f"Created new payment session {session_id} for app type: {app_type}")
        
        # Clean up expired sessions
        self._clean_expired_sessions()
        
        return {
            "session_id": session_id,
            "venmo_qr_code": self.get_venmo_qr_code(),
            "venmo_profile_url": VENMO_CONFIG["venmo_profile_url"],
            "expires_at": session["expires_at"],
            "min_amount": VENMO_CONFIG["min_amount"],
            "max_amount": VENMO_CONFIG["max_amount"]
        }
        
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get details for an existing session.
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            Session dictionary or None if not found
        """
        session = self.sessions.get(session_id)
        
        if not session:
            logger.warning(f"Session {session_id} not found")
            return None
            
        # Check if the session has expired
        if time.time() > session["expires_at"]:
            logger.warning(f"Session {session_id} has expired")
            self._clean_expired_sessions()
            return None
            
        return session
        
    def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing session with new data.
        
        Args:
            session_id: The session ID to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False
            
        # Update the session with the new data
        for key, value in updates.items():
            session[key] = value
            
        return True
        
    def handle_payment(self, payment_data: Dict[str, Any], session_id: str = None) -> bool:
        """
        Process a Venmo payment and associate it with a session.
        
        Args:
            payment_data: The payment data from the Venmo email
            session_id: Optional session ID to associate with
            
        Returns:
            True if payment was successfully processed
        """
        try:
            # Check for specific keywords in the email body
            body_text = payment_data.get("body_text", "").lower()
            note = payment_data.get("note", "")
            
            # Use the note exactly as parsed from the email
            # The note is already extracted with the best possible accuracy in venmo_email.py
            # Just log what we got for debugging purposes
            logger.info(f"Using app description from payment note: '{note}'")
            
            logger.info(f"Processing payment: ${payment_data['amount']} with note: {note}")
            
            # Store the last payment for display in the UI
            self.last_payment = {
                "amount": payment_data.get("amount"),
                "note": note,  # Use the potentially updated note
                "sender": payment_data.get("sender"),
                "timestamp": time.time(),
                "payment_id": payment_data.get("payment_id"),
                "body_text": body_text  # Store body text for debugging
            }
            
            # If no session_id is provided, this may be a direct payment without a session
            if not session_id or session_id == "default":
                logger.info("No specific session provided, handling as direct payment")
                # Here we'll automatically generate an app for direct payments
                try:
                    # Import here to avoid circular imports
                    from src.main import generate_app_for_payment
                    
                    # Trigger app generation in a separate thread to avoid blocking
                    import threading
                    logger.info(f"Starting app generation for payment: {note}")
                    
                    # Make sure the note is valid and not just sender info
                    if note and len(note) > 5 and "paid you" not in note.lower():
                        threading.Thread(
                            target=generate_app_for_payment,
                            args=(note, payment_data.get("amount", 0.25)),
                            daemon=True
                        ).start()
                    else:
                        logger.error(f"Invalid app description detected: '{note}'. Cannot generate app without a valid description.")
                except Exception as gen_error:
                    logger.error(f"Failed to start app generation: {gen_error}")
                
                return True
                
            # Get the session
            session = self.get_session(session_id)
            if not session:
                logger.warning(f"Cannot process payment: Session {session_id} not found or expired")
                return False
                
            # Update the session with payment information
            payment_updates = {
                "paid": True,
                "amount": payment_data.get("amount"),
                "payment_timestamp": time.time(),
                "sender": payment_data.get("sender"),
                "payment_id": payment_data.get("payment_id"),
                "payment_note": note  # Use the potentially updated note
            }
            
            self.update_session(session_id, payment_updates)
            logger.info(f"Payment processed for session {session_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            return False
            
    def _clean_expired_sessions(self) -> None:
        """Remove expired sessions from the sessions dictionary."""
        current_time = time.time()
        expired_ids = []
        
        for session_id, session in self.sessions.items():
            if current_time > session["expires_at"]:
                expired_ids.append(session_id)
                
        for session_id in expired_ids:
            del self.sessions[session_id]
            
        if expired_ids:
            logger.info(f"Cleaned {len(expired_ids)} expired sessions")

# Create a singleton instance for app-wide use
venmo_qr_manager = VenmoQRManager()