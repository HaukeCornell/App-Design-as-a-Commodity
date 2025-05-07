#!/usr/bin/env python3
"""Debug script to check application structure."""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({"message": "Hello World!"})

if __name__ == "__main__":
    print("Starting debug app on port 5001...")
    app.run(debug=True, host="0.0.0.0", port=5001)