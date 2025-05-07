#!/usr/bin/env python3
"""
Production entry point for the Vibe Coder application.
This file sets up the minimal necessary configuration to run the app.
"""
import os
import sys

# Add the root directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify

# Create a simple Flask app
app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({
        "message": "Vibe Coder is running",
        "status": "ok"
    })

# Set up the static route to serve index.html
@app.route('/static')
def static_index():
    return app.send_static_file('index.html')

if __name__ == "__main__":
    print("Starting Vibe Coder on port 8080")
    app.run(host='localhost', port=8080, debug=True)