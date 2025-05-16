#!/usr/bin/env python3
"""
Simple entry point for the Vibe Coder application.
"""
import os
import sys
import argparse
import time

def print_banner():
    """Print an ASCII art banner for Vibe Coder."""
    banner = """
    \u001b[36m
    \\  /o|_  _   /   _  _| _  _     
     \\/ ||_)(-`  \\__(_)(_|(-`|    
    \u001b[0m
    App Design as a Commodity - Interactive Art Installation
    """
    print(banner)

# Run the app directly from the src module
if __name__ == "__main__":
    print_banner()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start Vibe Coder application')
    parser.add_argument('-VibePay', action='store_true', help='Start in VibePay mode')
    parser.add_argument('--sudo', action='store_true', help='Try running printer with sudo (may require password)')
    args = parser.parse_args()
    
    # Set environment variable for the payment mode
    if args.VibePay:
        os.environ['INITIAL_PAYMENT_MODE'] = 'vibepay'
        print("Starting Vibe Coder in VibePay mode...")
    else:
        print("Starting Vibe Coder in default (Venmo) mode...")
    
    # Change to the script's directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Start the application
    if args.sudo:
        print("\nAttempting to run with sudo for printer permissions...")
        print("You may be prompted for your password.\n")
        os.system("sudo python3 src/main.py")
    else:
        print("\nStarting without sudo permissions for printer...")
        print("If you see printer permission errors, try running with --sudo\n")
        time.sleep(1)  # Give user a moment to read the message
        os.system("python3 src/main.py")