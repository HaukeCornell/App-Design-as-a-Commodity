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
    "current_mode": "venmo",  # "venmo" or "vibepay"
    "venmo": {
        "name": "Venmo", 
        "url": "https://venmo.com/code?user_id=3354253905100800472&created=1746493056.679508"
    },
    "vibepay": {
        "name": "VibePay",
        "url": "/vibepay"  # Local URL for the simulated payment page
    }
}

# Initialize the thermal printer
def init_thermal_printer():
    """Initialize the thermal printer."""
    return thermal_printer_manager.initialize()

# ASCII art for VIBE CODER
VIBE_CODER_ASCII = [
    "\\  /o|_  _   /   _  _| _  _",
    " \\/ ||_)(-`  \\__(_)(_|(-`| "
]

# Function to get initial receipt content
def get_initial_receipt_content():
    """Get the standardized initial receipt content based on current payment mode"""
    current_mode = PAYMENT_MODE["current_mode"]
    payment_service = PAYMENT_MODE[current_mode]["name"]
    payment_url = PAYMENT_MODE[current_mode]["url"]
    
    # Create a full URL for VibePay if using local path
    if current_mode == "vibepay" and payment_url.startswith("/"):
        import socket
        local_ip = get_local_ip()
        port = int(os.getenv("PORT", 5002))
        payment_url = f"http://{local_ip}:{port}{payment_url}"
    
    return {
        "initial_setup_lines": [
            "App Design as a Commodity",
            "Interactive Art Installation",
            time.strftime("%m/%d/%Y"),
            "www.haukesand.github.io",
            "",
            "",
            "",
            VIBE_CODER_ASCII[0],
            VIBE_CODER_ASCII[1],
            "",
            "ITEM:",
            "CUSTOM APP DEVELOPMENT",
            "",
            "- Pay $0.25 for a quick app",
            "- Pay $1.00 for a high quality app",
            "",
            f"In the {payment_service} description,",
            "describe the app you want.",
            "",
            "Your app will be automatically",
            "generated after payment.",
            "--------------------",
            "Scan QR code below to pay:",
            f"Using {payment_service}",
            "",

        ],
        "venmo_qr_data": payment_url
    }

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

# --- Routes --- 
@app.route("/")
def index():
    """Serve the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")
    
@app.route("/vibepay")
def vibepay_payment():
    """Serve the VibePay simulation page."""
    # Generate a simple HTML page that simulates a Venmo-like payment form
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>VibePay - Simulated Payment</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #0074DE;
                color: white;
            }}
            .container {{
                max-width: 400px;
                margin: 0 auto;
                background-color: white;
                border-radius: 12px;
                padding: 20px;
                color: #333;
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            }}
            h1 {{
                text-align: center;
                color: #0074DE;
                margin-bottom: 25px;
            }}
            .logo {{
                font-size: 24px;
                font-weight: bold;
                text-align: center;
                margin-bottom: 20px;
            }}
            label {{
                display: block;
                margin: 15px 0 5px;
                font-weight: bold;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 6px;
                box-sizing: border-box;
                font-size: 16px;
            }}
            textarea {{
                height: 100px;
                resize: vertical;
            }}
            button {{
                background-color: #0074DE;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 20px;
                width: 100%;
                font-size: 16px;
                font-weight: bold;
                margin-top: 20px;
                cursor: pointer;
            }}
            button:hover {{
                background-color: #0065C1;
            }}
            .success-message {{
                display: none;
                background-color: #E3F2FD;
                border-left: 4px solid #0074DE;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">VibePay</div>
            <h1>Simulated Payment</h1>
            
            <form id="payment-form">
                <label for="amount">Amount</label>
                <input type="number" id="amount" name="amount" min="0.01" step="0.01" value="0.25" required>
                
                <label for="note">App Description</label>
                <textarea id="note" name="note" placeholder="Describe the app you want to build..." required></textarea>
                
                <div id="success-message" class="success-message">
                    Payment successful! Your app is being generated.
                </div>
                
                <button type="submit">Pay Now</button>
            </form>
        </div>
        
        <script>
            // Variable to track if a submission is in progress
            let isSubmitting = false;
            
            document.getElementById('payment-form').addEventListener('submit', function(e) {{
                e.preventDefault();
                
                // Prevent multiple submissions
                if (isSubmitting) {{
                    console.log("Payment already being processed, ignoring duplicate submission");
                    return;
                }}
                
                isSubmitting = true;
                
                const amount = document.getElementById('amount').value;
                const note = document.getElementById('note').value;
                
                // Disable all form elements to prevent interaction
                const form = document.getElementById('payment-form');
                Array.from(form.elements).forEach(element => {{
                    element.disabled = true;
                }});
                
                // Disable the button immediately to prevent multiple submits
                const submitButton = document.querySelector('button[type="submit"]');
                submitButton.disabled = true;
                submitButton.textContent = 'Processing...';
                
                // Send the payment info to our simulated payment endpoint
                fetch('/api/vibepay-payment', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                    }},
                    body: JSON.stringify({{
                        amount: amount,
                        note: note,
                        timestamp: new Date().getTime() // Add a timestamp to ensure uniqueness
                    }})
                }})
                .then(response => response.json().then(data => {{ return {{response, data}}; }}))
                .then(result => {{
                    const response = result.response;
                    const data = result.data;
                    
                    // Handle cooldown or already generating case
                    if (response.status === 429) {{
                        const successMsg = document.getElementById('success-message');
                        successMsg.style.display = 'block';
                        successMsg.style.backgroundColor = '#fff3cd';
                        successMsg.style.borderLeft = '4px solid #ffc107';
                        
                        if (data.is_generating) {{
                            successMsg.innerHTML = '<strong>Another app is currently being generated.</strong><br>Please wait until the current generation completes before submitting a new request.';
                        }} else {{
                            const remainingTime = Math.ceil(data.cooldown_seconds_remaining || 15);
                            successMsg.innerHTML = '<strong>Generation cooldown in effect.</strong><br>Please wait ' + remainingTime + ' seconds before requesting another app.';
                            
                            // Start a countdown
                            let timeLeft = remainingTime;
                            const interval = setInterval(() => {{
                                timeLeft--;
                                if (timeLeft <= 0) {{
                                    clearInterval(interval);
                                    submitButton.disabled = false;
                                    submitButton.textContent = 'Pay Now';
                                    successMsg.style.display = 'none';
                                }} else {{
                                    successMsg.innerHTML = '<strong>Generation cooldown in effect.</strong><br>Please wait ' + timeLeft + ' seconds before requesting another app.';
                                }}
                            }}, 1000);
                        }}
                        
                        return;
                    }}
                    
                    // Handle standard success
                    if (response.ok && data.success) {{
                        // Show success message
                        const successMsg = document.getElementById('success-message');
                        successMsg.style.display = 'block';
                        successMsg.innerHTML = 'Payment successful! Your app is being generated.';
                        successMsg.style.backgroundColor = '#E3F2FD';
                        successMsg.style.borderLeft = '4px solid #0074DE';
                        
                        // Redirect after 3 seconds
                        setTimeout(() => {{
                            window.location.href = '/';
                        }}, 3000);
                    }} else {{
                        // Handle error conditions
                        const successMsg = document.getElementById('success-message');
                        successMsg.style.display = 'block';
                        successMsg.style.backgroundColor = '#FFEBEE';
                        successMsg.style.borderLeft = '4px solid #F44336';
                        successMsg.innerHTML = '<strong>Error:</strong> ' + (data.error || 'Failed to process payment');
                        
                        // Enable form elements after 5 seconds
                        setTimeout(() => {{
                            Array.from(form.elements).forEach(element => {{
                                element.disabled = false;
                            }});
                            submitButton.disabled = false;
                            submitButton.textContent = 'Pay Now';
                            isSubmitting = false; // Reset submission state
                        }}, 5000);
                    }}
                }})
                .catch(error => {{
                    const successMsg = document.getElementById('success-message');
                    successMsg.style.display = 'block';
                    successMsg.style.backgroundColor = '#FFEBEE';
                    successMsg.style.borderLeft = '4px solid #F44336';
                    successMsg.innerHTML = '<strong>Error:</strong> ' + (error.message || 'An unexpected error occurred');
                    
                    // Enable form elements
                    Array.from(form.elements).forEach(element => {{
                        element.disabled = false;
                    }});
                    submitButton.disabled = false;
                    submitButton.textContent = 'Pay Now';
                    isSubmitting = false; // Reset submission state
                }});
            }});
        </script>
    </body>
    </html>
    """
    return html_content
    
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
    
    # Directly print payment receipt if thermal printer is connected
    if thermal_printer_manager.initialized:
        payment_details = [
            f"PAYMENT RECEIVED",
            f"FROM: VibePay User",
            f"AMOUNT: ${amount:.2f}",
            f"REQUEST: {note}",
            "",
            "Generating your app now...",
            time.strftime("%Y-%m-%d %H:%M:%S")
        ]
        
        # Print receipt with payment details
        thermal_printer_manager.print_receipt(
            header_lines=["VIBEPAY PAYMENT", "-------------"],
            body_lines=payment_details,
            footer_lines=["Please wait for your app..."],
            cut=True
        )
    
    # Acquire the generation lock
    start_generation()
    
    # Use the same flow as real Venmo payments to generate the app
    try:
        # Create a payment data structure similar to what venmo_email.py produces
        payment_data = {
            "amount": amount,
            "note": note,
            "sender": "VibePay User",
            "timestamp": time.time(),
            # Add a flag to indicate this was a VibePay request to avoid double generation
            "vibepay_direct": True  
        }
        
        # Generate the app directly 
        # We need to explicitly log that this is VibePay to ensure correct behavior
        add_log(f"Starting app generation for VibePay payment", "info")
        
        generate_app_for_payment(
            note,
            amount,
            "VibePay User"  # This specific user identifier helps track the payment source
        )
        
        # App was generated, update cooldown
        # Note: generate_app_for_payment will have already called end_generation
        
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
    thermal_printer_manager.print_text([
        "VIBE CODER",
        VIBE_CODER_ASCII[0],
        VIBE_CODER_ASCII[1],
        "--------------------",
        f"{payment_service.upper()} QR SCANNED!",
        "User is at the payment step.",
        f"Waiting for {payment_service} payment...",
        "--------------------",
        time.strftime("%m/%d/%Y %H:%M:%S")
    ], align='center', cut=True)
    
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
    
    # Log the current payment mode for debugging
    add_log(f"Current payment mode (from /api/email-status): {PAYMENT_MODE['current_mode']}", "info")
    
    # Get Venmo QR code
    venmo_qr_code = venmo_qr_manager.get_venmo_qr_code()
    
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
        "payment_mode": PAYMENT_MODE["current_mode"],
        "debug_info": {
            "current_mode": PAYMENT_MODE["current_mode"],
            "server_time": time.time(),
            "venmo_url": PAYMENT_MODE["venmo"]["url"],
            "vibepay_url": PAYMENT_MODE["vibepay"]["url"]
        }
    }
    
    return jsonify(status)

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
    
    # Try printing via the lp command (OS level) - a completely different approach
    try:
        # Create a temporary file with our message
        import tempfile
        
        # Create a temporary text file for printing
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            message = f"""
MODE CHANGED
====================

Now in {requested_mode.upper()} mode

Time: {time.strftime('%H:%M:%S')}
====================
"""
            temp_file.write(message)
            temp_path = temp_file.name
            
        # Print via system command
        import subprocess
        add_log(f"Printing via system command to file: {temp_path}", "info")
        result = subprocess.run(['lp', temp_path], capture_output=True, text=True)
        
        if result.returncode == 0:
            add_log(f"System print command successful: {result.stdout}", "info")
        else:
            add_log(f"System print command failed: {result.stderr}", "error")
            
            # If system command fails, try the direct USB approach again
            add_log("Trying direct USB approach as backup", "info")
            from escpos.printer import Usb
            printer = Usb(0x04b8, 0x0e03, 0)
            printer.text(message)
            printer.cut()
        
    except Exception as e:
        add_log(f"All printing methods failed: {e}", "error")
    
    return jsonify({
        "message": f"Payment mode switched to {requested_mode}",
        "payment_mode": requested_mode
    })

@app.route("/api/debug-print", methods=["GET", "POST"])
def debug_print():
    """Ultra simple debug endpoint to test thermal printer directly."""
    add_log("Debug button pressed - trying DIRECT PRINT", "info")
    
    # ULTRA-BASIC DIRECT PRINTING TEST - use the minimum code necessary
    try:
        # Import printer directly
        from escpos.printer import Usb
        
        # Get printer directly
        printer = Usb(0x04b8, 0x0e03, 0)
        
        # Print directly
        printer.text("\n\nTEST PRINT\n\n")
        printer.text("Debug button pressed\n")
        printer.text(f"Time: {time.strftime('%H:%M:%S')}\n\n")
        printer.cut()
        
        add_log("Debug button print successful", "info")
        return jsonify({"success": True, "message": "Print test successful"})
    except Exception as e:
        add_log(f"Debug print failed: {e}", "error")
        return jsonify({"success": False, "error": str(e)}), 500

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
        # Check if we can generate a new app (cooldown and lock mechanism)
        if not can_generate_new_app():
            return jsonify({
                "error": "App generation cooldown in effect or another app is being generated",
                "cooldown_seconds_remaining": max(0, GENERATION_LOCK["cooldown_seconds"] - (time.time() - GENERATION_LOCK["last_generation_time"])),
                "is_generating": GENERATION_LOCK["is_generating"]
            }), 429  # 429 Too Many Requests
        
        # Acquire the generation lock
        start_generation()
        add_log("Starting app generation process...", "info")
        
        try:
            # Check if this is a GET request with a session ID (from Venmo flow)
            if request.method == "GET" and request.args.get("session_id"):
                session_id = request.args.get("session_id")
                session = venmo_qr_manager.get_session(session_id)
                
                if not session:
                    end_generation()  # Release lock on error
                    return jsonify({"error": "Invalid or expired session"}), 400
                    
                if not session.get("paid", False):
                    end_generation()  # Release lock on error
                    return jsonify({"error": "Payment not received yet"}), 400
                    
                # Extract data from the session
                app_type = session.get("app_type", "calculator")
                payment_amount = session.get("amount", 0.25)
                
            # Otherwise, handle as normal POST request with JSON data
            else:
                data = request.get_json()
                if not data or "app_type" not in data or "amount" not in data:
                    end_generation()  # Release lock on error
                    return jsonify({"error": "Missing app_type or amount in request"}), 400

                app_type = data.get("app_type")
                amount_str = data.get("amount")

                # Validate amount
                try:
                    payment_amount = float(amount_str)
                    if payment_amount <= 0:
                        raise ValueError("Amount must be positive")
                except (ValueError, TypeError):
                    end_generation()  # Release lock on error
                    return jsonify({"error": "Invalid amount specified"}), 400
            
            add_log(f"Generating app of type: '{app_type}' with payment amount: ${payment_amount}", "info")

            # Call App Generation Logic (Step 004 - Enhanced)
            generated_app_details = generate_app_files(app_type, payment_amount)
            
            if not generated_app_details:
                # Error logged within generate_app_files
                end_generation()  # Release lock on error
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
            
            add_log(f"App generation completed successfully: App ID {generated_app_details['app_id']}", "info")
            
            # Release the generation lock
            end_generation()
            
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
            # Release the generation lock on any exception
            end_generation()
            raise e  # Re-raise to be caught by outer try/except
    
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
        
        # For Venmo payments, print a receipt - VibePay has its own receipt handling
        # Only print here if this is a Venmo email payment, not a VibePay direct payment
        payment_source = "Venmo" if user_who_paid != "VibePay User" else "VibePay"
        add_log(f"Generating app for {payment_source} payment", "info")
        
        if payment_source == "Venmo" and thermal_printer_manager.initialized:
            # Print payment receipt only for Venmo (VibePay already printed one)
            payment_details = [
                f"User: {user_who_paid}",
                f"Amount: ${payment_amount:.2f}",
                f"Request: {app_type}",
                "Generating your app...",
                time.strftime("%Y-%m-%d %H:%M:%S")
            ]
            
            thermal_printer_manager.print_receipt(
                header_lines=["PAYMENT RECEIVED", "-------------"],
                body_lines=payment_details,
                footer_lines=["Please wait for your app..."],
                cut=False
            )

        try:
            # Call App Generation Logic
            generated_app_details = generate_app_files(app_type, payment_amount)
            
            if not generated_app_details:
                err_msg = f"Failed to generate app for payment: {app_type}"
                add_log(err_msg, "error")
                # Handle error with a cut - since we need to start a new flow
                if thermal_printer_manager.initialized:
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
            local_ip = get_local_ip()
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
            
            # Print the generated app details for ALL payment types
            # Ensure this works for both Venmo and VibePay payments
            if thermal_printer_manager.initialized:
                # We need to print app generation receipt for both Venmo AND VibePay
                payment_source = "Venmo" if user_who_paid != "VibePay User" else "VibePay"
                add_log(f"Printing app receipt for {payment_source} payment", "info")
                
                # App generation header based on payment source
                app_header = [
                    f"APP GENERATED!",
                    f"VIA {payment_source.upper()}",
                    "-----------------",
                ]
                
                # Print the app details with clear header
                thermal_printer_manager.print_receipt(
                    header_lines=app_header,
                    body_lines=app_details,
                    footer_lines=[
                        "Made with ♥ by Vibe Coder",
                        time.strftime("%Y-%m-%d %H:%M:%S")
                    ],
                    cut=False
                )
                
                # Print QR code to access the app
                thermal_printer_manager.print_qr(
                    hosted_url_full,
                    text_above="SCAN TO ACCESS YOUR APP",
                    text_below="App ready to use",
                    cut=True
                )
                
                # After cutting, print a fresh receipt for the next customer
                current_mode = PAYMENT_MODE["current_mode"]
                payment_service = PAYMENT_MODE[current_mode]["name"]
                
                # Get the QR code URL
                payment_url = PAYMENT_MODE[current_mode]["url"]
                if current_mode == "vibepay" and payment_url.startswith("/"):
                    local_ip = get_local_ip()
                    port = int(os.getenv("PORT", 5002))
                    payment_url = f"http://{local_ip}:{port}{payment_url}"
                
                # Print a new receipt for the next customer
                thermal_printer_manager.print_receipt(
                    header_lines=[
                        "VIBE CODER",
                        "App Design as a Commodity",
                        f"{payment_service.upper()} PAYMENT MODE",
                        "-----------------------"
                    ],
                    body_lines=[
                        f"Instructions for {payment_service}:",
                        "- Pay $0.25 for a quick app",
                        "- Pay $1.00 for a high quality app",
                        "",
                        f"In the {payment_service} note,",
                        "describe the app you want.",
                        "",
                        "Scan QR code below to pay:",
                    ],
                    footer_lines=[
                        time.strftime("%m/%d/%Y %H:%M:%S"),
                        "www.haukesand.github.io"
                    ],
                    cut=False
                )
                
                # Print QR code for payment
                thermal_printer_manager.print_qr(
                    payment_url,
                    text_above=f"PAY WITH {payment_service.upper()}",
                    text_below="Include app description in payment note",
                    cut=False
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
    
    if thermal_printer_manager.initialized:
        # Get initial receipt content and print it without cutting
        receipt_content = get_initial_receipt_content()
        
        # Print initial instructions using continuous receipt format
        thermal_printer_manager.print_continuous_receipt(
            initial_setup_lines=receipt_content["initial_setup_lines"],
            venmo_qr_data=receipt_content["venmo_qr_data"],
            cut_after=False
        )
    else:
        print("NOTICE: Thermal printer not initialized. Printing to console only.")
    
    # Use port 5002 for local testing
    port = int(os.getenv("PORT", 5002))
    # Set debug=True for development
    app.run(debug=True, host="0.0.0.0", port=port)