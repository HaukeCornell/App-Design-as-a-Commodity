#!/usr/bin/env python3.11
"""
Routes for the Vibe Coder application.
This module contains all Flask routes for the web application.
"""
import os
import time
import socket
import sys
from flask import (
    Flask, 
    request, 
    jsonify, 
    send_from_directory, 
    url_for, 
    render_template, 
    Blueprint
)

# Add parent directory to path to fix imports when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import services
from src.thermal_printer import thermal_printer_manager
from src.github_service import github_service
from src.qr_service import qr_service
from src.logging_service import logging_service
from src.app_generator import generate_app_files

# Import Venmo related modules
from src.venmo_email import email_processor, init_email_monitoring
from src.venmo_qr import venmo_qr_manager
from src.venmo_config import VENMO_CONFIG, EMAIL_CONFIG

# Import configuration
from src.config import GENERATED_APPS_DIR

# Import error handling
from src.error_handling import (
    api_exception_handler, 
    ValidationError
)

# Create a Blueprint for the API
api_bp = Blueprint('api', __name__, static_folder="../static", static_url_path="")

# --- Static Routes ---

@api_bp.route("/")
def index():
    """Serve the main HTML page."""
    return send_from_directory(api_bp.static_folder, "index.html")

@api_bp.route("/apps/<app_id>/")
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

# --- API Routes ---

@api_bp.route("/api/venmo-scanned")
@api_exception_handler
def venmo_scanned():
    """Handle notification that someone scanned the Venmo QR code."""
    # Log the scan
    logging_service.add_log("Someone scanned the Venmo QR code", "info")
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
            "basic": "$0.25 minimum (1 iteration)",
            "improved": "Each additional dollar = 1 additional iteration"
        }
    })

@api_bp.route("/api/email-monitor", methods=["POST"])
@api_exception_handler
def toggle_email_monitoring():
    """Toggle email monitoring on/off."""
    data = request.get_json()
    if not data:
        raise ValidationError("Missing request data")
        
    monitoring_enabled = data.get("enabled", False)
    
    if monitoring_enabled:
        # Start email monitoring if not already running
        if not email_processor.monitoring_active:
            init_email_monitoring()
            logging_service.add_log("Email monitoring started", "info")
        return jsonify({"message": "Email monitoring started", "status": "active"})
    else:
        # Stop email monitoring if running
        if email_processor.monitoring_active:
            email_processor.stop_monitoring()
            logging_service.add_log("Email monitoring stopped", "info")
        return jsonify({"message": "Email monitoring stopped", "status": "inactive"})

@api_bp.route("/api/email-status")
@api_exception_handler
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

@api_bp.route("/api/check-emails", methods=["POST"])
@api_exception_handler
def check_emails_now():
    """Manually check for new emails."""
    if not email_processor.monitoring_active:
        raise ValidationError("Email monitoring is not active")
    
    # Force a check for new emails
    payments = email_processor.fetch_recent_venmo_emails()
    
    # Process any found payments
    payment_count = 0
    for payment in payments:
        # Process the payment through the venmo_qr_manager
        if venmo_qr_manager.handle_payment(payment):
            payment_count += 1
            logging_service.add_log(f"Processed payment: ${payment.get('amount')} for {payment.get('note')}", "info")
        
    return jsonify({
        "message": "Email check completed",
        "payments_found": payment_count
    })

@api_bp.route("/generate", methods=["POST", "GET"])
@api_exception_handler
def generate_app_route():
    """Handle the app generation request from the frontend or Venmo payment."""
    # Check if this is a GET request with a session ID (from Venmo flow)
    if request.method == "GET" and request.args.get("session_id"):
        session_id = request.args.get("session_id")
        session = venmo_qr_manager.get_session(session_id)
        
        if not session:
            raise ValidationError("Invalid or expired session")
            
        if not session.get("paid", False):
            raise ValidationError("Payment not received yet")
            
        # Extract data from the session
        app_type = session.get("app_type", "calculator")
        payment_amount = session.get("amount", 0.25)
        
    # Otherwise, handle as normal POST request with JSON data
    else:
        data = request.get_json()
        if not data or "app_type" not in data or "amount" not in data:
            raise ValidationError("Missing app_type or amount in request")

        app_type = data.get("app_type")
        amount_str = data.get("amount")

        # Validate amount
        try:
            payment_amount = float(amount_str)
            if payment_amount <= 0:
                raise ValueError("Amount must be positive")
        except (ValueError, TypeError):
            raise ValidationError("Invalid amount specified")

    # Call App Generation Logic (Step 004 - Enhanced)
    generated_app_details = generate_app_files(app_type, payment_amount)
    
    if not generated_app_details:
        # Error logged within generate_app_files
        return jsonify({"error": f"Failed to generate app code for type: {app_type}"}), 500

    # Call GitHub Integration 
    github_url = github_service.push_to_github(
        generated_app_details["path"], 
        generated_app_details["app_id"],
        generated_app_details["app_type"]
    )

    # Web Hosting URL (using local route)
    hosted_url_relative = url_for("api.serve_generated_app", app_id=generated_app_details["app_id"], _external=False)
    
    # Use IP address for URLs
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

    # Generate QR code
    qr_code_base64 = qr_service.generate_base64(hosted_url_full)

    # Get actual model info from app_generator
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.app_generator import model
    
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
    for log in logging_service.get_logs(limit=20):
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
        logging_service.add_log(log_msg, "info")
        thermal_printer_manager.print_text([
            "PAYMENT RECEIVED!",
            f"User: {user_who_paid}",
            f"Amount: ${payment_amount:.2f}",
            f"Request: {app_type}",
            "--------------------",
            "Generating your app...",
            time.strftime("%Y-%m-%d %H:%M:%S")
        ], align='left', cut=True)

        # Call App Generation Logic
        generated_app_details = generate_app_files(app_type, payment_amount)
        
        if not generated_app_details:
            err_msg = f"Failed to generate app for payment: {app_type}"
            logging_service.add_log(err_msg, "error")
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

        thermal_printer_manager.print_text([
            f"APP '{actual_app_type}' GENERATED!",
            f"Tier: {app_tier}",
            f"ID: {app_id}",
            "--------------------",
            "Pushing to GitHub...",
        ], align='left') # No cut yet, more details to follow

        # Call GitHub Integration
        github_url = github_service.push_to_github(
            generated_app_details["path"], 
            app_id,
            actual_app_type
        )
        
        # Check for common error indicators in the returned GitHub URL string
        if "Error:" in github_url or "(Repo not found" in github_url or "(Permission denied" in github_url or "pat-not-set" in github_url:
            thermal_printer_manager.print_text([
                "GITHUB PUSH FAILED.",
                "Details in server logs.",
                "App was generated locally.",
            ], align='left')
        else:
            thermal_printer_manager.print_text([
                "Pushed to GitHub successfully!",
                 github_url, # This might be long, but good for a receipt
            ], align='left')

        # Generate base URL for hosted app using IP address
        # Try to get local network IP address
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
        qr_code_base64 = qr_service.generate_base64(hosted_url_full)
        
        thermal_printer_manager.print_text([
            "--------------------",
            "YOUR APP IS READY!",
            "Access URL:",
            # hosted_url_full, # URL printed by QR function's text_below
            "Scan QR code below to view:",
        ], align='left')
        thermal_printer_manager.print_qr(hosted_url_full, text_below=f"{actual_app_type} ({app_id})", cut=False) # Add app type to QR text

        thermal_printer_manager.print_text([
            "--------------------",
            "Thank you for using Vibe Coder!",
            time.strftime("%Y-%m-%d %H:%M:%S")
        ], align='center', cut=True)
        
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
        logging_service.add_log(f"App generation completed: {app_type} (${payment_amount})", "info")
        logging_service.add_log(f"App available at: {hosted_url_full}", "info")
        logging_service.add_log(f"GitHub repository: {github_url}", "info")
        
    except Exception as e:
        logging_service.add_log(f"Error generating app from payment: {e}", "error")