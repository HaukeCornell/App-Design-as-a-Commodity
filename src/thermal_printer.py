#!/usr/bin/env python3.11
"""
Thermal printer module for Vibe Coder application.
This module handles communication with a thermal receipt printer using ESC/POS commands.
"""
import os
import logging
import sys
import time
from escpos.printer import Usb
from escpos.exceptions import USBNotFoundError, Error as EscposError

# Fix import paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Local imports
from config import PRINTER_CONFIG

# Logger for printer specific messages
printer_logger = logging.getLogger("thermal_printer")

class ThermalPrinter:
    """Class to handle thermal printer operations."""
    
    def __init__(self, vendor_id=None, product_id=None):
        """
        Initialize the thermal printer with specified USB identifiers.
        
        Args:
            vendor_id: USB vendor ID (default: from config)
            product_id: USB product ID (default: from config)
        """
        self.vendor_id = vendor_id if vendor_id is not None else PRINTER_CONFIG["vendor_id"]
        self.product_id = product_id if product_id is not None else PRINTER_CONFIG["product_id"]
        
        # Directly initialize the printer without additional flags
        try:
            self.printer = Usb(self.vendor_id, self.product_id)
            printer_logger.info(
                f"Thermal printer connected successfully: "
                f"Vendor ID 0x{self.vendor_id:04x}, "
                f"Product ID 0x{self.product_id:04x}"
            )
        except USBNotFoundError:
            printer_logger.warning("Thermal printer not found. Printing will be directed to console.")
            self.printer = None
        except Exception as e:
            printer_logger.error(f"Failed to connect to printer: {e}")
            self.printer = None

    def print_text(self, lines, align='center', cut=False):
        """
        Print text lines to the thermal printer.
        
        Args:
            lines: List of strings or single string to print
            align: Text alignment ('left', 'center', 'right')
            cut: Whether to cut the paper after printing
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.printer:
                # Print to console instead
                if isinstance(lines, list):
                    print("[CONSOLE] " + "\n[CONSOLE] ".join(lines))
                else:
                    print(f"[CONSOLE] {lines}")
                return True
            
            # Set alignment
            if align == 'center':
                self.printer.set(align='center')
            elif align == 'right':
                self.printer.set(align='right')
            else:
                self.printer.set(align='left')
            
            # Print text lines
            if isinstance(lines, list):
                for line in lines:
                    self.printer.text(f"{line}\n")
            else:
                self.printer.text(f"{lines}\n")
                
            if cut:
                self.printer.cut()
                
            return True
            
        except Exception as e:
            printer_logger.error(f"Error during text printing: {e}")
            # Print to console as fallback
            if isinstance(lines, list):
                print("[FALLBACK] " + "\n[FALLBACK] ".join(lines))
            else:
                print(f"[FALLBACK] {lines}")
            return False

    def print_qr(self, data, text_above=None, text_below=None, cut=False):
        """
        Print a QR code to the thermal printer with optional text.
        
        Args:
            data: QR code content
            text_above: Text to print above the QR code
            text_below: Text to print below the QR code
            cut: Whether to cut the paper after printing
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.printer:
                # Log to console if printer not available
                qr_message = f"QR Data: {data}"
                if text_above: 
                    qr_message = f"{text_above}\n{qr_message}"
                if text_below: 
                    qr_message = f"{qr_message}\n{text_below}"
                
                print(f"[CONSOLE] {qr_message}")
                return True
            
            self.printer.set(align='center')
            
            if text_above:
                self.printer.text(f"{text_above}\n")
                
            self.printer.qr(data)
            
            if text_below:
                self.printer.text(f"{text_below}\n")
                
            if cut:
                self.printer.cut()
                
            return True
                
        except Exception as e:
            printer_logger.error(f"Error during QR printing: {e}")
            # Fallback to console
            qr_message = f"QR Data: {data}"
            if text_above:
                qr_message = f"{text_above}\n{qr_message}"
            if text_below:
                qr_message = f"{qr_message}\n{text_below}"
            print(f"[FALLBACK] {qr_message}")
            return False

    def cut_paper(self):
        """Cut the paper if the printer supports it."""
        if not self.printer:
            # No action needed in console mode
            return True
            
        try:
            self.printer.cut()
            return True
        except Exception as e:
            printer_logger.error(f"Error cutting paper: {e}")
            return False

    def close(self):
        """Close the connection to the printer."""
        if not self.printer:
            return True
            
        try:
            self.printer = None
            printer_logger.info("Thermal printer connection closed")
            return True
        except Exception as e:
            printer_logger.error(f"Error closing printer connection: {e}")
            return False

# Create singleton instance for importing in other modules
thermal_printer_manager = ThermalPrinter()