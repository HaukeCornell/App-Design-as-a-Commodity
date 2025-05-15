#!/usr/bin/env python3
"""
Simple entry point for the Vibe Coder application.
"""
import os
import sys
import argparse

# Run the app directly from the src module
if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start Vibe Coder application')
    parser.add_argument('-VibePay', action='store_true', help='Start in VibePay mode')
    args = parser.parse_args()
    
    # Set environment variable for the payment mode
    if args.VibePay:
        os.environ['INITIAL_PAYMENT_MODE'] = 'vibepay'
        print("Starting Vibe Coder in VibePay mode...")
    else:
        print("Starting Vibe Coder in default mode...")
    
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.system("python3 src/main.py")