#!/usr/bin/env python3
"""
Simple HTTP server for thermal printer testing.
"""
from flask import Flask, jsonify
import os
import time

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({"message": "Thermal printer test"})

@app.route('/test-printer')
def test_printer():
    # Run the thermal printer test command
    test_output = os.popen("echo 'THERMAL PRINTER TEST\nLine 1\nLine 2\n' > /tmp/test-print.txt").read()
    return jsonify({
        "message": "Thermal printer test sent",
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    })

if __name__ == "__main__":
    print("Starting simple thermal printer test server...")
    app.run(host="localhost", port=5050, debug=True)