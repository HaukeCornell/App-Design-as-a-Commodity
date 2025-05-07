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
from github_service import github_service
from app_generator import generate_app_files

# --- App Initialization ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="", template_folder="templates")
GENERATED_APPS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "generated_apps"))

# Initialize the thermal printer
def init_thermal_printer():
    """Initialize the thermal printer."""
    return thermal_printer_manager.initialize()

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

# --- Routes --- 
@app.route("/")
def index():
    """Serve the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")
    
@app.route("/api/venmo-scanned")
def venmo_scanned():
    """Handle notification that someone scanned the Venmo QR code."""
    # Log the scan
    add_log("Someone scanned the Venmo QR code", "info")
    thermal_printer_manager.print_text([
        "VENMO QR SCANNED!",
        "User is at the payment step.",
        "Waiting for Venmo email...",
        "--------------------",
        time.strftime("%Y-%m-%d %H:%M:%S")
    ], align='left', cut=True)
    
    # The actual payment logic happens in the email monitor
    # This endpoint is just for notification that someone scanned the QR
    
    return jsonify({
        "message": "Scan recorded. Check your Venmo app to complete payment.",
        "instructions": "In the payment note, describe the app you want to have built.",
        "pricing": {
            "quick_app": "$0.25",
            "high_quality_app": "$1.00"
        }
    })
    
@app.route("/api/email-monitor", methods=["POST"])
def toggle_email_monitoring():
    """Toggle email monitoring on/off."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing request data"}), 400
        
    monitoring_enabled = data.get("enabled", False)
    
    if monitoring_enabled:
        # Start email monitoring if not already running
        if not email_processor.monitoring_active:
            init_email_monitoring()
            add_log("Email monitoring started", "info")
        return jsonify({"message": "Email monitoring started", "status": "active"})
    else:
        # Stop email monitoring if running
        if email_processor.monitoring_active:
            email_processor.stop_monitoring()
            add_log("Email monitoring stopped", "info")
        return jsonify({"message": "Email monitoring stopped", "status": "inactive"})

@app.route("/api/email-status")
def get_email_status():
    """Get the status of email monitoring and last payment."""
    # Use the venmo_qr_manager's last_payment
    last_payment = venmo_qr_manager.last_payment
    last_generated_app = venmo_qr_manager.last_generated_app
    
    # Get current system status
    status = {
        "email_monitoring": email_processor.monitoring_active,
        "last_payment": last_payment,
        "last_generated_app": last_generated_app,
        "timestamp": time.time(),
        "venmo_profile_url": VENMO_CONFIG["venmo_profile_url"],
        "venmo_qr_code": venmo_qr_manager.get_venmo_qr_code()
    }
    
    return jsonify(status)

@app.route("/api/check-emails", methods=["POST"])
def check_emails_now():
    """Manually check for new emails."""
    if not email_processor.monitoring_active:
        return jsonify({"error": "Email monitoring is not active"}), 400
    
    try:
        # Force a check for new emails
        payments = email_processor.fetch_recent_venmo_emails()
        
        # Process any found payments
        payment_count = 0
        for payment in payments:
            # Process the payment through the venmo_qr_manager
            if venmo_qr_manager.handle_payment(payment):
                payment_count += 1
                add_log(f"Processed payment: ${payment.get('amount')} for {payment.get('note')}", "info")
            
        return jsonify({
            "message": "Email check completed",
            "payments_found": payment_count
        })
    except Exception as e:
        add_log(f"Error checking emails: {e}", "error")
        return jsonify({"error": f"Failed to check emails: {str(e)}"}), 500

@app.route("/generate", methods=["POST", "GET"])
def generate_app_route():
    """Handle the app generation request from the frontend or Venmo payment."""
    try:
        # Check if this is a GET request with a session ID (from Venmo flow)
        if request.method == "GET" and request.args.get("session_id"):
            session_id = request.args.get("session_id")
            session = venmo_qr_manager.get_session(session_id)
            
            if not session:
                return jsonify({"error": "Invalid or expired session"}), 400
                
            if not session.get("paid", False):
                return jsonify({"error": "Payment not received yet"}), 400
                
            # Extract data from the session
            app_type = session.get("app_type", "calculator")
            payment_amount = session.get("amount", 0.25)
            
        # Otherwise, handle as normal POST request with JSON data
        else:
            data = request.get_json()
            if not data or "app_type" not in data or "amount" not in data:
                return jsonify({"error": "Missing app_type or amount in request"}), 400

            app_type = data.get("app_type")
            amount_str = data.get("amount")

            # Validate amount
            try:
                payment_amount = float(amount_str)
                if payment_amount <= 0:
                    raise ValueError("Amount must be positive")
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid amount specified"}), 400

        # Call App Generation Logic (Step 004 - Enhanced)
        generated_app_details = generate_app_files(app_type, payment_amount)
        
        if not generated_app_details:
            # Error logged within generate_app_files
            return jsonify({"error": f"Failed to generate app code for type: {app_type}"}), 500

        # Call GitHub Integration (Step 005 - Real)
        github_url = github_service.push_to_github(
            generated_app_details["path"], 
            generated_app_details["app_id"],
            generated_app_details["app_type"]
        )

        # Web Hosting URL (Step 005 - using local route)
        hosted_url_relative = url_for("serve_generated_app", app_id=generated_app_details["app_id"], _external=False)
        
        # Use IP address for URLs
        import socket
        def get_local_ip():
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
                
        local_ip = get_local_ip()
        
        # Use environment variable for external URL, falling back to IP address
        external_host = os.getenv("EXTERNAL_HOST", f"http://{local_ip}:5002")
        if not external_host.startswith(('http://', 'https://')):
            external_host = f"http://{external_host}"
        hosted_url_full = f"{external_host.strip('/')}{hosted_url_relative}"

        # Call QR Code Generation (Step 006)
        qr_code_base64 = generate_qr_code_base64(hosted_url_full)

        # Get actual model info from app_generator
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from app_generator import model
        
        model_name = "gemini-1.5-pro-latest"
        if model and hasattr(model, "_model_name"):
            model_name = model._model_name
            
        # Add accurate AI model information
        ai_info = [
            f"AI: {model_name}",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"App ID: {generated_app_details['app_id']}"
        ]
        
        # Capture the most recent logs, filtering out noise
        filtered_logs = []
        for log in application_logs:
            msg = log['message'].lower()
            # Skip unwanted logs
            if any(x in msg for x in ['debugger', 'pin:', 'http/1.1', 'api/email-status']):
                continue
            filtered_logs.append(log)
        
        # Get the recent logs after filtering
        recent_logs = filtered_logs[-8:] if filtered_logs else []
        log_entries = [f"{log['message']}" for log in recent_logs]
        
        # Combine AI info with log messages
        all_logs = ai_info + ["---"] + log_entries
        log_messages = "\n".join(all_logs)
        
        # Return success response including the full URL
        return jsonify({
            "message": f"App {generated_app_details['app_id']} generated successfully (Tier: {generated_app_details['tier']}).",
            "app_type_received": app_type,
            "amount_received": payment_amount,
            "hosted_url_relative": hosted_url_relative, # Relative URL for links within the page
            "hosted_url_full": hosted_url_full, # Full URL for display and QR code
            "github_url": github_url, 
            "qr_code_image": qr_code_base64,
            "readme_generated": "readme_path" in generated_app_details, # Boolean indicating if README was generated
            "user": "testuser", # Hardcoded user as requested
            "logs": log_messages
        }), 200

    except Exception as e:
        print(f"Error during generation route: {e}") # Log error server-side
        return jsonify({"error": f"An internal error occurred: {str(e)}"}), 500

# --- Route to serve generated apps (Part of Step 005) ---
@app.route("/apps/<app_id>/")
def serve_generated_app(app_id):
    """Serve the index.html of a generated app."""
    if not app_id or not all(c.isalnum() or c == "-" for c in app_id):
         return jsonify({"error": "Invalid app ID format"}), 400
         
    app_directory = os.path.abspath(os.path.join(GENERATED_APPS_DIR, app_id))
    if not app_directory.startswith(GENERATED_APPS_DIR):
        return jsonify({"error": "Invalid app path"}), 400
        
    index_path = os.path.join(app_directory, "index.html")
    if not os.path.exists(index_path):
        return jsonify({"error": "App not found"}), 404
        
    return send_from_directory(app_directory, "index.html")

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
        
        # Print payment received section on the continuous receipt (no cut)
        payment_details = [
            f"User: {user_who_paid}",
            f"Amount: ${payment_amount:.2f}",
            f"Request: {app_type}",
            "Generating your app...",
            time.strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        # Add payment section to the receipt without cutting
        thermal_printer_manager.print_continuous_receipt(
            payment_received_lines=payment_details,
            cut_after=False
        )

        # Call App Generation Logic
        generated_app_details = generate_app_files(app_type, payment_amount)
        
        if not generated_app_details:
            err_msg = f"Failed to generate app for payment: {app_type}"
            add_log(err_msg, "error")
            # Handle error with a cut - since we need to start a new flow
            thermal_printer_manager.print_text([
                "APP GENERATION FAILED",
                f"Request: {app_type}",
                f"Amount: ${payment_amount:.2f}",
                "We apologize for the inconvenience.",
                "Please see server logs for details.",
                "--------------------",
                time.strftime("%Y-%m-%d %H:%M:%S")
            ], align='left', cut=True)
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
        
        # Prepare app generation details lines
        app_details = [
            f"App Type: {actual_app_type}",
            f"Tier: {app_tier}",
            f"ID: {app_id}"
        ]

        # Add GitHub URL details
        if "Error:" in github_url or "(Repo not found" in github_url or "(Permission denied" in github_url or "pat-not-set" in github_url:
            app_details.append("GITHUB PUSH FAILED.")
            app_details.append("App was generated locally.")
        else:
            app_details.append("GitHub Repository:")
            app_details.append(github_url)

        # Generate base URL for hosted app using IP address
        import socket
        def get_local_ip_for_receipt(): # Renamed to avoid conflict if imported elsewhere
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "localhost"
                
        local_ip = get_local_ip_for_receipt()
        base_url = os.getenv("EXTERNAL_HOST", f"http://{local_ip}:5002")
        if not base_url.startswith(('http://', 'https://')):
            base_url = f"http://{base_url}"
            
        hosted_url_relative = f"/apps/{app_id}/"
        hosted_url_full = f"{base_url.strip('/')}{hosted_url_relative}"
        
        # Generate QR code for the app (for UI)
        qr_code_base64 = generate_qr_code_base64(hosted_url_full)
        
        # Add app URL details and QR code
        app_details.append("Access your app at:")
        app_details.append(hosted_url_full)
        
        # Complete the receipt with the app generation details and cut the paper
        thermal_printer_manager.print_continuous_receipt(
            app_generated_lines=app_details,
            app_url=hosted_url_full,  # Include the app URL for QR code
            cut_after=True
        )
        
        # After cutting, start a new receipt with initial instructions
        venmo_url = "https://venmo.com/code?user_id=3354253905100800472&created=1746493056.679508"
        thermal_printer_manager.print_continuous_receipt(
            initial_setup_lines=[
                "VIBE CODER",
                "--------------------", 
                "Scan Venmo QR code below",
                "to generate an app!",
                "--------------------",
                "Tier pricing:",
                "Simple app: $0.25",
                "Premium app: $1.00",
                "--------------------",
                "Type your app description and",
                "payment amount in Venmo.",
                "--------------------",
                time.strftime("%Y-%m-%d %H:%M:%S")
            ],
            venmo_qr_data=venmo_url,
            cut_after=False
        )
        
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
        
    except Exception as e:
        add_log(f"Error generating app from payment: {e}", "error")

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize the Venmo payment system
    init_venmo_system()
    # Initialize the Thermal Printer System
    init_thermal_printer()
    
    if thermal_printer_manager.initialized:
        # Get the venmo URL for the QR code - using direct app link
        venmo_url = "https://venmo.com/code?user_id=3354253905100800472&created=1746493056.679508"
        
        # Print initial instructions using continuous receipt format
        # This is the first section and doesn't cut the paper
        thermal_printer_manager.print_continuous_receipt(
            initial_setup_lines=[
                "VIBE CODER",
                "--------------------",
                "Scan Venmo QR code below",
                "to generate an app!",
                "--------------------",
                "Tier pricing:",
                "Simple app: $0.25",
                "Premium app: $1.00",
                "--------------------",
                "Type your app description and",
                "payment amount in Venmo.",
                "--------------------",
                time.strftime("%Y-%m-%d %H:%M:%S")
            ],
            venmo_qr_data=venmo_url,
            cut_after=False
        )
    else:
        print("NOTICE: Thermal printer not initialized. Printing to console only.")
    
    # Use port 5002 for local testing
    port = int(os.getenv("PORT", 5002))
    # Set debug=True for development
    app.run(debug=True, host="0.0.0.0", port=port)