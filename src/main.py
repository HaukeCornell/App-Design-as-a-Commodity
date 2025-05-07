import sys
import os
from dotenv import load_dotenv
import logging # Added import for logging

# Load environment variables from .env file
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, request, jsonify, send_from_directory, url_for, render_template, redirect
import json
import subprocess
import shutil
import qrcode
import io
import base64
import time # For potential delays
import threading
import uuid

# Import escpos library
from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError, Error as EscposError

# Import the app generator function
from src.app_generator import generate_app_files

# Import Venmo related modules
from src.venmo_email import email_processor, init_email_monitoring
from src.venmo_qr import venmo_qr_manager
from src.venmo_config import VENMO_CONFIG, EMAIL_CONFIG

# --- App Initialization ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", static_url_path="", template_folder="templates")
GENERATED_APPS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "generated_apps"))

# --- Thermal Printer Configuration ---
thermal_printer = None
# Epson TM-T20 series typically use these IDs. Verify with `lsusb` if issues arise.

PRINTER_VENDOR_ID = 0x04b8
PRINTER_PRODUCT_ID = 0x0e03 # Updated to 0x0e03 based on user's System Information
# PRINTER_PROFILE = "TM-T20" # Profile for TM-T20 series - Commented out original

# Logger for printer specific messages (will be captured by root logger's handler)
printer_logger = logging.getLogger("thermal_printer")

def init_thermal_printer():
    """Initializes connection to the thermal printer."""
    global thermal_printer
    # Try the specific profiles for TM-T20II and 'default'
    printer_profiles_to_try = ["TM-T20II", "TM-T20II-42col", "default"]

    for profile_name in printer_profiles_to_try:
        try:
            printer_logger.info(f"Attempting to connect to thermal printer: Vendor ID 0x{PRINTER_VENDOR_ID:04x}, Product ID 0x{PRINTER_PRODUCT_ID:04x}, Profile: {profile_name}")
            thermal_printer = Usb(PRINTER_VENDOR_ID, PRINTER_PRODUCT_ID, 0, profile=profile_name)
            
            thermal_printer.hw("INIT")
            printer_logger.info(f"Thermal printer connected and initialized successfully (Profile: {profile_name}).")
            # Removed text_type from set() call
            thermal_printer.set(align='center', width=1, height=1, density=9) 
            return
        except USBNotFoundError:
            printer_logger.error("Thermal printer not found by USB system. Please ensure it is connected, powered on, and Vendor/Product IDs are correct.")
            thermal_printer = None
            return # Stop trying if USB device not found at all
        except Exception as e:
            printer_logger.warning(f"Failed to connect or initialize with profile '{profile_name}': {e}")
            thermal_printer = None
            # Continue to the next profile in the list

    if not thermal_printer:
        printer_logger.error("Could not connect to thermal printer with the specified profiles (TM-T20II, TM-T20II-42col). Check USB connection, IDs, and ensure libusb is installed if necessary.")

def safe_print_text(lines: list[str], align: str = 'center', cut: bool = False, text_type: str = 'NORMAL', width: int = 1, height: int = 1):
    """Safely prints text lines to the thermal printer."""
    if thermal_printer:
        try:
            # Removed text_type from set() call, width and height are passed directly if needed by textln or other methods
            thermal_printer.set(align=align, width=width, height=height)
            for line in lines:
                thermal_printer.textln(line)
            if cut:
                thermal_printer.cut()
        except EscposError as e:
            printer_logger.error(f"ESC/POS library error during text printing: {e}")
        except Exception as e:
            printer_logger.error(f"Unexpected error during text printing: {e}")
    else:
        # Log to console if printer not available, as this is a primary interface
        print("[NO PRINTER] " + "\n[NO PRINTER] ".join(lines))
        printer_logger.warning("Thermal printer not available, skipping text print. Logged to console.")

def safe_print_qr(data: str, text_above: str = None, text_below: str = None, align: str = 'center', size: int = 6, cut: bool = False):
    """Safely prints a QR code to the thermal printer."""
    if thermal_printer:
        try:
            thermal_printer.set(align=align)
            if text_above:
                thermal_printer.textln(text_above)
            thermal_printer.qr(data, size=size)
            if text_below:
                thermal_printer.textln(text_below)
            if cut:
                thermal_printer.cut()
        except EscposError as e:
            printer_logger.error(f"ESC/POS library error during QR printing: {e}")
        except Exception as e:
            printer_logger.error(f"Unexpected error during QR printing: {e}")
    else:
        qr_message = f"QR Data: {data}"
        if text_above: qr_message = f"{text_above}\n{qr_message}"
        if text_below: qr_message = f"{qr_message}\n{text_below}"
        print(f"[NO PRINTER] {qr_message}")
        printer_logger.warning("Thermal printer not available, skipping QR print. Logged to console.")

# Initialize Venmo QR manager with email monitoring
def init_venmo_system():
    """Initialize the Venmo payment system on startup."""
    print("Initializing Venmo payment system...")
    # We'll set the correct base URL when the first request comes in
    # This prevents using localhost in production
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

# --- GitHub Configuration --- 
# --- IMPORTANT: Load PAT from environment variable --- 
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_USERNAME = "sandvibe" # User provided username

if not GITHUB_PAT:
    print("Warning: GITHUB_PAT environment variable not set. GitHub integration will likely fail.")

def create_github_repo(repo_name: str) -> bool:
    """Creates a new GitHub repository using GitHub API."""
    if not GITHUB_PAT:
        print("[GitHub Integration] Error: GitHub PAT not set.")
        return False
        
    try:
        # Log creation attempt with specific account
        print(f"[GitHub Integration] Creating repository: {repo_name} for user: {GITHUB_USERNAME}")
        
        # Set up the authorization headers
        headers = {
            "Authorization": f"token {GITHUB_PAT}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Repository data
        data = {
            "name": repo_name,
            "description": f"App generated by Vibe Coder - {time.strftime('%Y-%m-%d')}",
            "private": False,
            "auto_init": False,  # Don't initialize with README
            "has_issues": True,
            "has_projects": False,
            "has_wiki": False
        }
        
        # Create repository using GitHub API
        import requests
        # Use the specific endpoint to create the repo
        response = requests.post(f"https://api.github.com/user/repos", headers=headers, json=data)
        
        # Check response
        if response.status_code == 201:
            print(f"[GitHub Integration] Successfully created repository: {repo_name} for user: {GITHUB_USERNAME}")
            print(f"[GitHub Integration] Repository URL: https://github.com/{GITHUB_USERNAME}/{repo_name}")
            return True
        else:
            print(f"[GitHub Integration] Failed to create repository: {repo_name}. Status code: {response.status_code}")
            print(f"[GitHub Integration] Response: {response.text}")
            
            # If there's a 422 error, the repo might already exist
            if response.status_code == 422 and "already exists" in response.text:
                print(f"[GitHub Integration] Repository already exists, will attempt to push anyway.")
                return True
                
            return False
            
    except Exception as e:
        print(f"[GitHub Integration] Error creating repository: {e}")
        return False

def push_to_github_real(app_path: str, app_id: str, app_type: str) -> str:
    """Pushes the generated app code to a new GitHub repository using git commands and PAT."""
    if not GITHUB_PAT:
        print("[GitHub Integration] Error: GitHub PAT not set.")
        return "https://github.com/error/pat-not-set"
        
    repo_name = f"vibe-coded-app-{app_id}"
    repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo_name}"
    git_url = f"{repo_url}.git"
    # Use PAT for authentication in the URL
    authenticated_repo_url = f"https://{GITHUB_USERNAME}:{GITHUB_PAT}@github.com/{GITHUB_USERNAME}/{repo_name}.git"
    commit_message = f"Add {app_type} app ({app_id}) generated by Vibe Coder"

    print(f"[GitHub Integration] Attempting to push code from {app_path} to {repo_url}")
    print(f"[GitHub Integration] Using account: {GITHUB_USERNAME}")
    
    # First create the repository
    repo_created = create_github_repo(repo_name)
    if not repo_created:
        print(f"[GitHub Integration] Warning: Could not create repository {repo_name}. Will attempt to push anyway.")

    try:
        # Check if git is initialized, if so, remove .git dir to avoid nesting issues
        git_dir = os.path.join(app_path, ".git")
        if os.path.exists(git_dir):
            print("[GitHub Integration] Removing existing .git directory.")
            shutil.rmtree(git_dir)
            time.sleep(0.5) # Small delay to ensure directory is removed

        # Initialize git repo
        print("[GitHub Integration] Initializing git repository...")
        subprocess.run(["git", "init"], cwd=app_path, check=True, capture_output=True, text=True)
        
        # Configure git user (temporary for this repo)
        subprocess.run(["git", "config", "user.name", "Vibe Coder Bot"], cwd=app_path, check=True)
        subprocess.run(["git", "config", "user.email", "noreply@vibe.coder"], cwd=app_path, check=True)

        # Add files
        print("[GitHub Integration] Adding files...")
        subprocess.run(["git", "add", "."], cwd=app_path, check=True, capture_output=True, text=True)

        # Commit
        print("[GitHub Integration] Committing files...")
        commit_result = subprocess.run(["git", "commit", "-m", commit_message], cwd=app_path, check=False, capture_output=True, text=True)
        
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stdout.lower() or "nothing to commit" in commit_result.stderr.lower():
                print("[GitHub Integration] Nothing to commit. Adding empty README to force commit.")
                with open(os.path.join(app_path, "README.md"), "a") as f:
                    f.write("\n\nGenerated at: " + time.strftime("%Y-%m-%d %H:%M:%S"))
                subprocess.run(["git", "add", "README.md"], cwd=app_path, check=True, capture_output=True, text=True)
                subprocess.run(["git", "commit", "-m", commit_message], cwd=app_path, check=True, capture_output=True, text=True)
            else:
                print(f"[GitHub Integration] Commit failed: {commit_result.stderr}")
                raise subprocess.CalledProcessError(commit_result.returncode, commit_result.args, stderr=commit_result.stderr)

        # Rename branch to main
        subprocess.run(["git", "branch", "-M", "main"], cwd=app_path, check=True, capture_output=True, text=True)

        # Add remote origin
        print(f"[GitHub Integration] Adding remote origin: {git_url}")
        # Remove existing remote origin if it exists to avoid error
        subprocess.run(["git", "remote", "remove", "origin"], cwd=app_path, check=False, capture_output=True, text=True)
        subprocess.run(["git", "remote", "add", "origin", authenticated_repo_url], cwd=app_path, check=True, capture_output=True, text=True)

        # Push to GitHub
        print("[GitHub Integration] Pushing to GitHub...")
        push_result = subprocess.run(["git", "push", "-u", "origin", "main"], cwd=app_path, check=False, capture_output=True, text=True) # check=False to handle repo not found

        if push_result.returncode != 0:
            if "repository not found" in push_result.stderr.lower():
                print(f"[GitHub Integration] Repository {repo_url} not found. Please verify the GitHub account and token.")
                return f"{repo_url} (Repo not found - please verify account permissions)"
            elif "permission to" in push_result.stderr.lower() and "denied" in push_result.stderr.lower():
                print(f"[GitHub Integration] Permission denied. Please verify the GitHub token has correct permissions.")
                return f"{repo_url} (Permission denied - check token permissions)"
            else:
                print(f"[GitHub Integration] Push failed: {push_result.stderr}")
                raise subprocess.CalledProcessError(push_result.returncode, push_result.args, stderr=push_result.stderr)
        
        print(f"[GitHub Integration] Successfully pushed {app_id} to {repo_url}")
        return repo_url

    except subprocess.CalledProcessError as e:
        print(f"[GitHub Integration] Failed during git operation: {e}")
        print(f"Command: {' '.join(e.cmd)}")
        print(f"Stderr: {e.stderr}")
        return f"{repo_url} (Error: {str(e).split(':', 1)[0]})"
    except FileNotFoundError:
         print("[GitHub Integration] Failed: git command not found. Ensure it is installed and in PATH.")
         return f"{repo_url} (Error: git command not found)"
    except Exception as e:
        print(f"[GitHub Integration] An unexpected error occurred: {e}")
        return f"{repo_url} (Error: {str(e)[:50]})"
    finally:
        # Clean up .git directory after push to prevent issues if run again in same dir
        git_dir = os.path.join(app_path, ".git")
        if os.path.exists(git_dir):
            try:
                shutil.rmtree(git_dir)
                print("[GitHub Integration] Cleaned up .git directory.")
            except Exception as e:
                 print(f"[GitHub Integration] Warning: Failed to clean up .git directory: {e}")

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

# Monkey patch the logger handlers to capture logs
import logging
class ApplicationLogHandler(logging.Handler):
    def emit(self, record):
        level = record.levelname.lower()
        if level == 'critical':
            level = 'error'  # Map critical to error for UI
        add_log(record.getMessage(), level)

# Set up logging to capture log messages
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(ApplicationLogHandler())

# Configure logging levels for verbose modules
for logger_name in ["venmo_email", "venmo_qr"]:
    logger = logging.getLogger(logger_name)
    # Set to WARNING to reduce console output - use DEBUG for development
    logger.setLevel(logging.WARNING)
    # Still capture important logs for the UI
    logger.addHandler(ApplicationLogHandler())

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
    safe_print_text([
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
        github_url = push_to_github_real(
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
        for log in application_logs:
            msg = log['message'].lower()
            # Skip unwanted logs
            if any(x in msg for x in ['debugger', 'pin:', 'http/1.1', 'api/email-status']):
                continue
            filtered_logs.append(log)
        
        # Get the recent logs after filtering
        recent_logs = filtered_logs[-8:] if len(filtered_logs > 0) else []
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
        safe_print_text([
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
            add_log(err_msg, "error")
            safe_print_text([
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

        safe_print_text([
            f"APP '{actual_app_type}' GENERATED!",
            f"Tier: {app_tier}",
            f"ID: {app_id}",
            "--------------------",
            "Pushing to GitHub...",
        ], align='left') # No cut yet, more details to follow

        # Call GitHub Integration
        github_url = push_to_github_real(
            generated_app_details["path"], 
            app_id,
            actual_app_type
        )
        
        # Check for common error indicators in the returned GitHub URL string
        if "Error:" in github_url or "(Repo not found" in github_url or "(Permission denied" in github_url or "pat-not-set" in github_url:
            safe_print_text([
                "GITHUB PUSH FAILED.",
                "Details in server logs.",
                "App was generated locally.",
            ], align='left')
        else:
            safe_print_text([
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
        qr_code_base64 = generate_qr_code_base64(hosted_url_full)
        
        safe_print_text([
            "--------------------",
            "YOUR APP IS READY!",
            "Access URL:",
            # hosted_url_full, # URL printed by QR function's text_below
            "Scan QR code below to view:",
        ], align='left')
        safe_print_qr(hosted_url_full, text_below=f"{actual_app_type} ({app_id})", cut=False) # Add app type to QR text

        safe_print_text([
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
    
    if thermal_printer:
        safe_print_text([
            "VIBE CODER",
            "Thermal Receipt System Online",
            "--------------------",
            "Scan Venmo QR on main screen",
            "to generate an app!",
            "Payment URL (for reference):",
            VENMO_CONFIG["venmo_profile_url"],
            "--------------------",
            time.strftime("%Y-%m-%d %H:%M:%S")
        ], align='center', cut=True)
    else:
        print("NOTICE: Thermal printer not initialized. Printing to console only.")
    
    # Use port 5002 for local testing
    port = int(os.getenv("PORT", 5002))
    # Set debug=True for development
    app.run(debug=True, host="0.0.0.0", port=port)