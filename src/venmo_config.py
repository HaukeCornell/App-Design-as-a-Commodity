#!/usr/bin/env python3.11
"""
Venmo payment configuration and credentials for the Vibe Coder app.
This module stores the configuration for Venmo payments and email processing.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
# Get the directory of this file and find the .env file in the project root
import os.path
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# Email Configuration 
EMAIL_CONFIG = {
    # Email credentials
    "email_address": os.getenv("VENMO_EMAIL_ADDRESS", "sandhaus@ik.me"),
    "email_password": os.getenv("VENMO_EMAIL_PASSWORD", ""),
    
    # IMAP Server Configuration
    "imap_server": os.getenv("VENMO_IMAP_SERVER", "mail.infomaniak.com"),
    "imap_port": int(os.getenv("VENMO_IMAP_PORT", "993")),
    "use_ssl": True,
    
    # SMTP Server Configuration (for potential future use)
    "smtp_server": os.getenv("VENMO_SMTP_SERVER", "mail.infomaniak.com"),
    "smtp_port": int(os.getenv("VENMO_SMTP_PORT", "465")),
    "smtp_use_ssl": True,
    
    # Email processing configuration
    "check_interval": int(os.getenv("EMAIL_CHECK_INTERVAL", "15")),  # seconds
    "max_emails_to_process": int(os.getenv("MAX_EMAILS_TO_PROCESS", "10")),
    "venmo_sender": os.getenv("VENMO_SENDER_EMAIL", "venmo@venmo.com"),
}

# Venmo Configuration
VENMO_CONFIG = {
    "venmo_profile_url": os.getenv("VENMO_PROFILE_URL", "https://account.venmo.com/u/haukesa"),
    # Direct URL to Venmo QR code (as provided) - this is used for the QR code generation
    "venmo_direct_url": os.getenv("VENMO_DIRECT_URL", "https://venmo.com/u/haukesa"),
    "min_amount": float(os.getenv("VENMO_MIN_AMOUNT", "0.25")),
    "max_amount": float(os.getenv("VENMO_MAX_AMOUNT", "2.00")),
    
    # Payment processing configuration
    "payment_timeout": int(os.getenv("PAYMENT_TIMEOUT", "600")),  # seconds (10 minutes)
    "allowed_payment_methods": ["Venmo"],
    
    # Server notification endpoint for when QR code is scanned
    "notify_url": os.getenv("NOTIFY_URL", "/api/venmo-scanned"),
}

# Session configuration for QR code scanning and payment tracking
SESSION_CONFIG = {
    "session_timeout": int(os.getenv("SESSION_TIMEOUT", "1800")),  # seconds (30 minutes)
    "max_active_sessions": int(os.getenv("MAX_ACTIVE_SESSIONS", "50")),
}

# Debug settings
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

# Validation
if not EMAIL_CONFIG["email_password"]:
    print("Warning: Email password not set in environment variables. Email monitoring will not work.")