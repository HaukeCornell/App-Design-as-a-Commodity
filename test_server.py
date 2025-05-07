#!/usr/bin/env python3
"""
Simple HTTP server test.
"""
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Hello, World!"})

if __name__ == "__main__":
    print("Starting test server...")
    app.run(host="0.0.0.0", port=5005, debug=True)