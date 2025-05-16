#!/usr/bin/env python3.11
"""
Main application for Vibe Coder.
This is the entry point for the application.
"""
import os
import sys
import time
import logging
from flask import Flask, request, jsonify, send_from_directory, url_for, render_template, redirect
import qrcode
import io
import base64
import subprocess
import shutil
import uuid
import threading
import socket

# Import helper modules
import sys
import os

# Add the current directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now import with relative paths
from thermal_printer import thermal_printer_manager
from venmo_email import email_processor, init_email_monitoring
from venmo_qr import venmo_qr_manager
from venmo_config import VENMO_CONFIG, EMAIL_CONFIG
from config import PRINTER_CONFIG  # Import printer config
from github_service import github_service
from app_generator import generate_app_files
from receipt_manager import receipt_manager  # Import the new receipt manager

# Helper function to get local IP address
def get_local_ip():
    """Get the local IP address of this machine for network connections."""
    try:
        # Get the local IP by creating a socket connection to an external server
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # The address doesn't need to be reachable
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

# --- App Initialization ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="", template_folder="templates")
GENERATED_APPS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "generated_apps"))

# Payment mode configuration
PAYMENT_MODE = {
    "current_mode": os.environ.get("INITIAL_PAYMENT_MODE", "venmo"),  # Get from environment or default to "venmo"
    "venmo": {
        "name": "Venmo", 
        "url": "https://venmo.com/code?user_id=3354253905100800472&created=1746493056.679508",
        "app_url": "venmo://paycharge?txn=pay&recipients=3354253905100800472&amount=0.25&note=Custom%20App%20Request"
    },
    "vibepay": {
        "name": "VibePay",
        "url": "/vibepay"  # Local URL for the simulated payment page
    }
}

# Initialize the thermal printer - simplified to always return True
def init_thermal_printer():
    """Check printer status - simplified to always return True."""
    return True if thermal_printer_manager.printer else False

# --- QR Code Generation --- 
def generate_qr_code_base64(url: str) -> str:
    """Generates a QR code for the given URL and returns it as a base64 encoded PNG image."""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return img_base64
    except Exception as e:
        print(f"Error generating QR code for {url}: {e}")
        return ""

# --- Logging System for Display ---
# Store logs in memory for display
application_logs = []
log_id_counter = 0

# Generation cooldown mechanism to prevent multiple apps being generated at once
GENERATION_LOCK = {
    "is_generating": False,
    "last_generation_time": 0,
    "cooldown_seconds": 15  # Time to wait between generations
}

def add_log(message, level="info"):
    """Add a log entry to the application logs."""
    global log_id_counter
    log_id_counter += 1
    
    log_entry = {
        "id": log_id_counter,
        "timestamp": time.time(),
        "message": message,
        "level": level
    }
    
    # Add to in-memory log store (limit to 1000 entries)
    application_logs.append(log_entry)
    if len(application_logs) > 1000:
        application_logs.pop(0)  # Remove oldest log
        
    # Also print to console
    print(f"[{level.upper()}] {message}")
    
    return log_entry

def can_generate_new_app():
    """Check if we can generate a new app based on cooldown and current generation status."""
    current_time = time.time()
    
    # If we're already generating, block new generations
    if GENERATION_LOCK["is_generating"]:
        add_log("App generation already in progress. Please wait...", "warning")
        return False
        
    # Check if we're still in the cooldown period
    time_since_last = current_time - GENERATION_LOCK["last_generation_time"]
    if time_since_last < GENERATION_LOCK["cooldown_seconds"]:
        remaining = GENERATION_LOCK["cooldown_seconds"] - time_since_last
        add_log(f"Generation cooldown in effect. Please wait {remaining:.1f} seconds.", "warning")
        return False
        
    return True

def start_generation():
    """Mark the start of app generation."""
    GENERATION_LOCK["is_generating"] = True
    
def end_generation():
    """Mark the end of app generation and update the cooldown timer."""
    GENERATION_LOCK["is_generating"] = False
    GENERATION_LOCK["last_generation_time"] = time.time()

# Initialize Venmo QR manager with email monitoring
def init_venmo_system():
    """Initialize the Venmo payment system on startup."""
    print("Initializing Venmo payment system...")
    venmo_qr_manager.set_base_url(None)
    
    # Display email configuration status
    if EMAIL_CONFIG["email_password"]:
        print(f"Email monitoring configured for: {EMAIL_CONFIG['email_address']}")
    else:
        print("WARNING: Email password not set. Email monitoring will not work correctly.")
    
    # Register the payment callback handler
    email_processor.register_callback("default", venmo_qr_manager.handle_payment)
    
    # Add the QR code path to logs for debugging
    qr_path = venmo_qr_manager.qr_code_path
    if os.path.exists(qr_path):
        print(f"Venmo QR code found at: {qr_path}")
    else:
        print(f"WARNING: Venmo QR code not found at: {qr_path}")
    
    # Start email monitoring in the background
    init_email_monitoring()

# --- Routes --- 
@app.route("/")
def index():
    """Serve the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")
    
@app.route("/vibepay")
def vibepay_payment():
    """Serve the VibePay simulation page."""
    # ...existing code...

@app.route("/api/vibepay-payment", methods=["POST"])
def process_vibepay_payment():
    """Process a simulated VibePay payment."""
    # Check if we can generate a new app (cooldown and lock mechanism)
    if not can_generate_new_app():
        return jsonify({
            "error": "App generation cooldown in effect or another app is being generated",
            "cooldown_seconds_remaining": max(0, GENERATION_LOCK["cooldown_seconds"] - (time.time() - GENERATION_LOCK["last_generation_time"])),
            "is_generating": GENERATION_LOCK["is_generating"]
        }), 429  # 429 Too Many Requests
        
    # Get the payment info from the request body
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request data"}), 400
        
    # Extract payment details
    try:
        amount = float(data.get("amount", 0))
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount"}), 400
        
    note = data.get("note", "")
    if not note or len(note.strip()) == 0:
        return jsonify({"error": "Note is required"}), 400
        
    # Log the payment
    add_log(f"VibePay payment received: ${amount:.2f} for '{note}'", "info")
    
    # Use our receipt manager to print the payment confirmation
    payment_details = {
        "amount": amount,
        "note": note,
        "sender": "VibePay User",
        "timestamp": time.time()
    }
    receipt_manager.print_payment_confirmation(payment_details)
    
    # Acquire the generation lock
    start_generation()
    
    # Use the same flow as real Venmo payments to generate the app
    try:
        # Generate the app directly 
        add_log(f"Starting app generation for VibePay payment", "info")
        
        generate_app_for_payment(
            note,
            amount,
            "VibePay User"  # This specific user identifier helps track the payment source
        )
        
        # Update the last payment for the UI but mark it as processed
        venmo_qr_manager.last_payment = {
            "amount": amount,
            "note": note,
            "sender": "VibePay User",
            "timestamp": time.time(),
            "processed": True  # Mark as already processed to prevent duplicate generation from UI
        }
        
        return jsonify({
            "success": True,
            "message": "Payment processed successfully"
        })
    except Exception as e:
        # Release lock on error
        end_generation()
        add_log(f"Error processing VibePay payment: {e}", "error")
        return jsonify({
            "success": False,
            "error": f"Error processing payment: {str(e)}"
        }), 500

@app.route("/api/venmo-scanned")
def venmo_scanned():
    """Handle notification that someone scanned the Venmo QR code."""
    # Log the scan
    current_mode = PAYMENT_MODE["current_mode"]
    payment_service = PAYMENT_MODE[current_mode]["name"]
    
    add_log(f"Someone scanned the {payment_service} QR code", "info")
    
    # Print a simple scan notification
    thermal_printer_manager.print_text([
        f"{payment_service.upper()} QR SCANNED!",
        "Waiting for payment confirmation...",
        time.strftime("%H:%M:%S"),
        "",
    ], align='center', cut=False)
    
    # The actual payment logic happens in the email monitor for Venmo
    # or through the simulation endpoint for VibePay
    
    return jsonify({
        "message": f"Scan recorded. Check your {payment_service} app to complete payment.",
        "instructions": f"In the {payment_service} note, describe the app you want to have built.",
        "pricing": {
            "quick_app": "$0.25",
            "high_quality_app": "$1.00"
        }
    })

@app.route("/api/toggle-payment-mode", methods=["POST"])
def toggle_payment_mode():
    """Toggle between Venmo and VibePay payment modes."""
    global PAYMENT_MODE
    
    # Get the requested mode from the request body
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request data"}), 400
        
    requested_mode = data.get("mode")
    
    # Validate the requested mode
    if requested_mode not in ["venmo", "vibepay"]:
        return jsonify({"error": f"Invalid payment mode: {requested_mode}"}), 400
    
    current_mode = PAYMENT_MODE["current_mode"]
    
    # If already in the requested mode, return early
    if current_mode == requested_mode:
        return jsonify({
            "message": f"Already in {requested_mode} mode", 
            "payment_mode": requested_mode
        })
    
    # Update the payment mode
    PAYMENT_MODE["current_mode"] = requested_mode
    
    # Log the mode change
    add_log(f"Payment mode switched from {current_mode} to {requested_mode}", "info")
    
    # Get payment URL and format it properly for the current mode
    payment_service = PAYMENT_MODE[requested_mode]["name"]
    
    # Get proper URL depending on payment mode
    if requested_mode == "venmo":
        payment_url = PAYMENT_MODE[requested_mode].get("app_url", PAYMENT_MODE[requested_mode]["url"])
    else:
        payment_url = PAYMENT_MODE[requested_mode]["url"]
        # Create a full URL for VibePay if using local path
        if payment_url.startswith("/"):
            local_ip = get_local_ip()
            port = int(os.getenv("PORT", 5002))
            payment_url = f"http://{local_ip}:{port}{payment_url}"
    
    # Use receipt manager to print the new header with QR code
    receipt_manager.print_payment_header(payment_service, payment_url)
    
    return jsonify({
        "message": f"Payment mode switched to {requested_mode}",
        "payment_mode": requested_mode
    })

@app.route("/api/email-status")
def get_email_status():
    """Get the status of email monitoring and last payment."""
    # Use the venmo_qr_manager's last_payment
    last_payment = venmo_qr_manager.last_payment
    last_generated_app = venmo_qr_manager.last_generated_app
    
    # Log the current payment mode for debugging
    current_mode = PAYMENT_MODE["current_mode"]
    payment_service = PAYMENT_MODE[current_mode]["name"]
    add_log(f"Current payment mode (from /api/email-status): {current_mode}", "debug")
    
    # Get Venmo QR code - use app URL for mobile Venmo app opening
    venmo_app_url = PAYMENT_MODE["venmo"].get("app_url", PAYMENT_MODE["venmo"]["url"])
    venmo_qr_code = generate_qr_code_base64(venmo_app_url)
    
    # Generate VibePay QR code
    vibepay_url = PAYMENT_MODE["vibepay"]["url"]
    if vibepay_url.startswith("/"):
        local_ip = get_local_ip()
        port = int(os.getenv("PORT", 5002))
        vibepay_url = f"http://{local_ip}:{port}{vibepay_url}"
    vibepay_qr_code = generate_qr_code_base64(vibepay_url)
    
    # Get current system status
    status = {
        "email_monitoring": email_processor.monitoring_active,
        "last_payment": last_payment,
        "last_generated_app": last_generated_app,
        "timestamp": time.time(),
        "venmo_profile_url": VENMO_CONFIG["venmo_profile_url"],
        "venmo_qr_code": venmo_qr_code,
        "vibepay_qr_code": vibepay_qr_code,
        "vibepay_url": vibepay_url,
        "payment_mode": current_mode,
        "debug_info": {
            "current_mode": current_mode,
            "server_time": time.time(),
            "venmo_url": venmo_app_url,  # Use the app URL here for reference
            "vibepay_url": PAYMENT_MODE["vibepay"]["url"]
        }
    }
    
    return jsonify(status)

# Function to generate app from payment data
def generate_app_for_payment(app_type: str, payment_amount: float, user_who_paid: str = "TestUser") -> None:
    """
    Generate an app based on a received payment.
    Called automatically when a payment is received through email monitoring.
    
    Args:
        app_type: The type of app to generate (from the payment note)
        payment_amount: The amount of the payment
        user_who_paid: Name of the user who paid (from Venmo note if possible)
    """
    try:
        log_msg = f"Starting app generation for payment: '{app_type}' (${payment_amount:.2f}) from '{user_who_paid}'"
        add_log(log_msg, "info")
        
        # For Venmo payments received via email, we need to print the payment confirmation
        # VibePay payments already have their confirmation printed in the process_vibepay_payment endpoint
        if user_who_paid != "VibePay User":
            # Print payment confirmation for Venmo payments
            payment_details = {
                "amount": payment_amount,
                "note": app_type,
                "sender": user_who_paid,
                "timestamp": time.time()
            }
            receipt_manager.print_payment_confirmation(payment_details)

        try:
            # Call App Generation Logic
            generated_app_details = generate_app_files(app_type, payment_amount)
            
            if not generated_app_details:
                err_msg = f"Failed to generate app for payment: {app_type}"
                add_log(err_msg, "error")
                # Print error message if generation failed
                thermal_printer_manager.print_text([
                    "APP GENERATION FAILED",
                    f"Request: {app_type}",
                    f"Amount: ${payment_amount:.2f}",
                    "We apologize for the inconvenience.",
                    "Please see server logs for details.",
                    "--------------------",
                    time.strftime("%Y-%m-%d %H:%M:%S")
                ], align='left', cut=True)
                # Release the generation lock
                end_generation()
                return
            
            app_id = generated_app_details["app_id"]
            app_tier = generated_app_details["tier"]
            actual_app_type = generated_app_details["app_type"] # Use type from details
    
            # Call GitHub Integration
            github_url = github_service.push_to_github(
                generated_app_details["path"], 
                app_id,
                actual_app_type
            )
            
            # Generate base URL for hosted app using IP address
            local_ip = get_local_ip()
            base_url = os.getenv("EXTERNAL_HOST", f"http://{local_ip}:5002")
            if not base_url.startswith(('http://', 'https://')):
                base_url = f"http://{base_url}"
                
            hosted_url_relative = f"/apps/{app_id}/"
            hosted_url_full = f"{base_url.strip('/')}{hosted_url_relative}"
            
            # Generate QR code for the app (for UI)
            qr_code_base64 = generate_qr_code_base64(hosted_url_full)
            
            # Use the receipt manager to print the app completion details
            app_details = {
                "app_id": app_id,
                "app_type": actual_app_type,
                "tier": app_tier,
                "github_url": github_url
            }
            receipt_manager.print_app_completion(app_details, hosted_url_full)
            
            # Store the generated app info for access by the UI
            venmo_qr_manager.last_generated_app = {
                "app_id": generated_app_details["app_id"],
                "app_type": generated_app_details["app_type"],
                "tier": generated_app_details["tier"],
                "hosted_url_full": hosted_url_full,
                "hosted_url_relative": hosted_url_relative,
                "github_url": github_url,
                "qr_code_image": qr_code_base64,
                "message": f"App {generated_app_details['app_id']} generated successfully (Tier: {generated_app_details['tier']}).",
                "readme_generated": "readme_path" in generated_app_details,
                "timestamp": time.time(),
                "logs": log_msg
            }
            
            # Log the success
            add_log(f"App generation completed: {app_type} (${payment_amount})", "info")
            add_log(f"App available at: {hosted_url_full}", "info")
            add_log(f"GitHub repository: {github_url}", "info")
            
            # Print a new receipt header for the next customer
            # Get payment service details for the current mode
            current_mode = PAYMENT_MODE["current_mode"]
            payment_service = PAYMENT_MODE[current_mode]["name"]
            payment_url = PAYMENT_MODE[current_mode]["url"]
            
            # Format full URL for VibePay if needed
            if current_mode == "vibepay" and payment_url.startswith("/"):
                local_ip = get_local_ip()
                port = int(os.getenv("PORT", 5002))
                payment_url = f"http://{local_ip}:{port}{payment_url}"
            
            # Print header for new transaction
            receipt_manager.print_payment_header(payment_service, payment_url)
            
        finally:
            # Always release the generation lock, even if there's an error
            end_generation()
            
    except Exception as e:
        # Make sure we release the lock in case of any exceptions
        end_generation()
        add_log(f"Error generating app from payment: {e}", "error")

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize the Venmo payment system
    init_venmo_system()
    # Initialize the Thermal Printer System
    init_thermal_printer()
    
    # Initialize receipt for current payment mode
    current_mode = PAYMENT_MODE["current_mode"]
    payment_service = PAYMENT_MODE[current_mode]["name"]
    
    # Get proper URL depending on payment mode
    if current_mode == "venmo":
        payment_url = PAYMENT_MODE[current_mode].get("app_url", PAYMENT_MODE[current_mode]["url"])
    else:
        payment_url = PAYMENT_MODE[current_mode]["url"]
        # Format full URL for VibePay if needed
        if payment_url.startswith("/"):
            local_ip = get_local_ip()
            port = int(os.getenv("PORT", 5002))
            payment_url = f"http://{local_ip}:{port}{payment_url}"
    
    # Print initial payment header
    receipt_manager.print_payment_header(payment_service, payment_url)
    
    # Use port 5002 for local testing
    port = int(os.getenv("PORT", 5002))
    # Set debug=True for development
    app.run(debug=True, host="0.0.0.0", port=port)