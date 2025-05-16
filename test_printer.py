#!/usr/bin/env python3
from escpos.printer import Usb

# Updated values based on your lsusb output
vendor_id = 0x04b8  # Epson
product_id = 0x0e03  # Your TM-T20 product ID

try:
    # Try to connect and print
    printer = Usb(vendor_id, product_id)
    printer.text("Hello from Raspberry Pi!\n")
    printer.cut()
    print("Print test successful!")
except Exception as e:
    print(f"Error: {str(e)}")