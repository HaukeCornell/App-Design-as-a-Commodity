#!/usr/bin/env python3
"""Test application to isolate routing issues."""
import os
import sys
from flask import Flask, jsonify, Blueprint, send_from_directory

# Create app
app = Flask(__name__)

# Create a simple blueprint
bp = Blueprint('api', __name__)

@bp.route('/')
def index():
    return jsonify({"message": "Hello from blueprint!"})

@bp.route('/api/test')
def test_api():
    return jsonify({"status": "API working"})

# Register blueprint
app.register_blueprint(bp)

if __name__ == "__main__":
    print("Starting test app on port 5003...")
    app.run(debug=True, host="0.0.0.0", port=5003)