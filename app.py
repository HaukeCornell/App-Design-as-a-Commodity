#!/usr/bin/env python3
"""
Simple entry point for the Vibe Coder application.
"""
import os
import sys

# Run the app directly from the src module
if __name__ == "__main__":
    # Simply run the main.py script directly
    print("Starting Vibe Coder...")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.system("python3 src/main.py")