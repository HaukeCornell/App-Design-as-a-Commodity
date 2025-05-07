#!/usr/bin/env python3
"""
Simplified entry point for the Vibe Coder application.
"""
import os
import sys
import time
from flask import Flask, jsonify, send_from_directory

# Create app
app = Flask(__name__, static_folder="src/static", static_url_path="")

@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory(app.static_folder, "index.html")

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": time.time()
    })

if __name__ == "__main__":
    # Start the Flask application
    print("Starting simplified Vibe Coder app...")
    app.run(debug=True, host="0.0.0.0", port=5004)