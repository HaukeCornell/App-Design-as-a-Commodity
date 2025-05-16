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
        printer_logger.info(f"Thermal printer configured with Vendor ID 0x{self.vendor_id:04x}, Product ID 0x{self.product_id:04x}")
    
    def _execute_with_printer(self, operation_func):
        """
        Execute an operation with a fresh printer connection and ensure it's properly closed.
        
        Args:
            operation_func: Function that takes a printer object and performs operations
            
        Returns:
            True if successful, False otherwise
        """
        printer = None
        try:
            # Create fresh connection
            printer = Usb(self.vendor_id, self.product_id)
            
            # Execute the operation
            result = operation_func(printer)
            
            # Explicitly close
            if hasattr(printer, 'close'):
                printer.close()
            
            # Give the system some time to release the resource
            time.sleep(0.1)
            
            return result
        except Exception as e:
            printer_logger.error(f"Printer operation error: {e}")
            # Try to close if it exists
            if printer and hasattr(printer, 'close'):
                try:
                    printer.close()
                except:
                    pass
            return False

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
        def _print_operation(printer):
            # Set alignment
            if align == 'center':
                printer.set(align='center')
            elif align == 'right':
                printer.set(align='right')
            else:
                printer.set(align='left')
            
            # Print text lines
            if isinstance(lines, list):
                for line in lines:
                    printer.text(f"{line}\n")
            else:
                printer.text(f"{lines}\n")
                
            if cut:
                printer.cut()
            
            return True
        
        # Execute with a fresh printer connection
        success = self._execute_with_printer(_print_operation)
        
        if not success:
            # Print to console as fallback
            if isinstance(lines, list):
                print("[CONSOLE] " + "\n[CONSOLE] ".join(lines))
            else:
                print(f"[CONSOLE] {lines}")
        
        return True

    def print_qr(self, data, text_above=None, text_below=None, cut=False, size=6):
        """
        Print a QR code to the thermal printer with optional text.
        
        Args:
            data: QR code content
            text_above: Text to print above the QR code
            text_below: Text to print below the QR code
            cut: Whether to cut the paper after printing
            size: Size of the QR code (default: 6)
            
        Returns:
            True if successful, False otherwise
        """
        def _qr_operation(printer):
            printer.set(align='center')
            
            if text_above:
                printer.text(f"{text_above}\n")
                
            printer.qr(data, size=size)
            
            if text_below:
                printer.text(f"{text_below}\n")
                
            if cut:
                printer.cut()
            
            return True
        
        # Execute with a fresh printer connection
        success = self._execute_with_printer(_qr_operation)
        
        if not success:
            # Fallback to console
            qr_message = f"QR Data: {data}"
            if text_above:
                qr_message = f"{text_above}\n{qr_message}"
            if text_below:
                qr_message = f"{qr_message}\n{text_below}"
            print(f"[CONSOLE] {qr_message}")
            
        return True

    def cut_paper(self):
        """Cut the paper if the printer supports it."""
        # Get a fresh printer connection
        def _cut_operation(printer):
            printer.cut()
            return True
            
        return self._execute_with_printer(_cut_operation)

    def close(self):
        """Close the connection to the printer."""
        # Nothing to do as we use fresh connections for each operation
        printer_logger.info("Thermal printer manager closed")
        return True

# Create singleton instance for importing in other modules
thermal_printer_manager = ThermalPrinter()