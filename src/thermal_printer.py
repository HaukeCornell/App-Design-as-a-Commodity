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

# Import error handling
try:
    from error_handling import (
        PrinterError, 
        ErrorCodes, 
        exception_handler
    )
except ImportError:
    # Fallback error handling if module not found
    class PrinterError(Exception):
        pass
    
    class ErrorCodes:
        PRINTER_CONNECTION_ERROR = 3000
        PRINTER_COMMUNICATION_ERROR = 3001
    
    def exception_handler(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                print(f"Error in {func.__name__}: {e}")
                return None
        return wrapper

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
        self.printer = None
        self.vendor_id = vendor_id if vendor_id is not None else PRINTER_CONFIG["vendor_id"]
        self.product_id = product_id if product_id is not None else PRINTER_CONFIG["product_id"]
        self.initialized = False
        
    @exception_handler
    def initialize(self):
        """
        Initialize connection to the thermal printer with profile fallbacks.
        
        Returns:
            True if successfully initialized, False otherwise
            
        Raises:
            PrinterError: If printer initialization fails
        """
        # Try different printer profiles in case one works better than others
        printer_profiles_to_try = PRINTER_CONFIG.get("profiles", ["default"])

        for profile_name in printer_profiles_to_try:
            try:
                printer_logger.info(
                    f"Attempting to connect to thermal printer: "
                    f"Vendor ID 0x{self.vendor_id:04x}, "
                    f"Product ID 0x{self.product_id:04x}, "
                    f"Profile: {profile_name}"
                )
                
                self.printer = Usb(self.vendor_id, self.product_id, 0, profile=profile_name)
                
                # Initialize the printer hardware
                self.printer.hw("INIT")
                printer_logger.info(f"Thermal printer connected and initialized successfully (Profile: {profile_name}).")
                
                # Set default formatting
                self.printer.set(align='center', width=1, height=1, density=9)
                
                self.initialized = True
                return True
                
            except USBNotFoundError as e:
                printer_logger.error(
                    "Thermal printer not found by USB system. "
                    "Please ensure it is connected, powered on, and Vendor/Product IDs are correct."
                )
                self.printer = None
                
                if profile_name == printer_profiles_to_try[-1]:
                    # Only raise exception if we've tried all profiles
                    raise PrinterError(
                        "Thermal printer not found by USB system",
                        code=ErrorCodes.PRINTER_CONNECTION_ERROR,
                        details={
                            'vendor_id': f"0x{self.vendor_id:04x}", 
                            'product_id': f"0x{self.product_id:04x}"
                        },
                        original_exception=e
                    )
                return False
                
            except EscposError as e:
                printer_logger.warning(f"ESC/POS error with profile '{profile_name}': {e}")
                self.printer = None
                # Continue to the next profile
                
            except Exception as e:
                printer_logger.warning(f"Failed to connect or initialize with profile '{profile_name}': {e}")
                self.printer = None
                # Continue to the next profile in the list

        if not self.initialized:
            printer_logger.error(
                "Could not connect to thermal printer with the specified profiles. "
                "Check USB connection, IDs, and ensure libusb is installed if necessary."
            )
            return False
            
        return False

    @exception_handler
    def print_text(self, lines, align='center', cut=False, width=1, height=1):
        """
        Print text lines to the thermal printer.
        
        Args:
            lines: List of strings to print
            align: Text alignment ('left', 'center', 'right')
            cut: Whether to cut the paper after printing
            width: Text width multiplier
            height: Text height multiplier
        
        Returns:
            True if successful, False otherwise
            
        Raises:
            PrinterError: If printing fails
        """
        if not self.initialized or not self.printer:
            # Log to console if printer not available
            print("[NO PRINTER] " + "\n[NO PRINTER] ".join(lines))
            printer_logger.warning("Thermal printer not available, skipping text print. Logged to console.")
            return False
            
        try:
            self.printer.set(align=align, width=width, height=height)
            
            for line in lines:
                self.printer.textln(line)
                
            if cut:
                self.printer.cut()
                
            return True
            
        except EscposError as e:
            raise PrinterError(
                f"ESC/POS library error during text printing: {e}",
                code=ErrorCodes.PRINTER_COMMUNICATION_ERROR,
                details={'lines_count': len(lines)},
                original_exception=e
            )
            
        except Exception as e:
            raise PrinterError(
                f"Unexpected error during text printing: {e}",
                code=ErrorCodes.PRINTER_COMMUNICATION_ERROR,
                details={'lines_count': len(lines)},
                original_exception=e
            )

    def print_qr(self, data, text_above=None, text_below=None, align='center', size=6, cut=False):
        """
        Print a QR code to the thermal printer with optional text.
        
        Args:
            data: QR code content
            text_above: Text to print above the QR code
            text_below: Text to print below the QR code
            align: Text alignment ('left', 'center', 'right')
            size: QR code size (1-16)
            cut: Whether to cut the paper after printing
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.printer:
            # Log to console if printer not available
            qr_message = f"QR Data: {data}"
            if text_above: 
                qr_message = f"{text_above}\n{qr_message}"
            if text_below: 
                qr_message = f"{qr_message}\n{text_below}"
            
            print(f"[NO PRINTER] {qr_message}")
            printer_logger.warning("Thermal printer not available, skipping QR print. Logged to console.")
            return False
            
        try:
            self.printer.set(align=align)
            
            if text_above:
                self.printer.textln(text_above)
                
            self.printer.qr(data, size=size)
            
            if text_below:
                self.printer.textln(text_below)
                
            if cut:
                self.printer.cut()
                
            return True
                
        except EscposError as e:
            printer_logger.error(f"ESC/POS library error during QR printing: {e}")
            return False
            
        except Exception as e:
            printer_logger.error(f"Unexpected error during QR printing: {e}")
            return False

    def print_receipt(self, header_lines, body_lines, footer_lines, cut=True):
        """
        Print a complete receipt with header, body, and footer sections.
        
        Args:
            header_lines: List of strings for the receipt header
            body_lines: List of strings for the receipt body
            footer_lines: List of strings for the receipt footer
            cut: Whether to cut the paper after printing
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.printer:
            # Log to console if printer not available
            combined_lines = header_lines + ["---"] + body_lines + ["---"] + footer_lines
            print("[NO PRINTER] " + "\n[NO PRINTER] ".join(combined_lines))
            printer_logger.warning("Thermal printer not available, skipping receipt print. Logged to console.")
            return False
            
        try:
            # Print header centered, possibly larger
            self.printer.set(align='center', width=1, height=1)
            for line in header_lines:
                self.printer.textln(line)
                
            # Separator line
            self.printer.text("--------------------\n")
                
            # Print body left-aligned, normal size
            self.printer.set(align='left', width=1, height=1)
            for line in body_lines:
                self.printer.textln(line)
                
            # Separator line
            self.printer.text("--------------------\n")
                
            # Print footer centered, normal size
            self.printer.set(align='center', width=1, height=1)
            for line in footer_lines:
                self.printer.textln(line)
                
            if cut:
                self.printer.cut()
                
            return True
                
        except EscposError as e:
            printer_logger.error(f"ESC/POS library error during receipt printing: {e}")
            return False
            
        except Exception as e:
            printer_logger.error(f"Unexpected error during receipt printing: {e}")
            return False
            
    def print_continuous_receipt(self, initial_setup_lines=None, payment_received_lines=None, app_generated_lines=None, venmo_qr_data=None, cut_after=False):
        """
        Print a full receipt as one continuous slip with multiple sections that are appended as processing progresses.
        
        This method can be called multiple times to add new sections to an ongoing receipt.
        Only cut the paper when all sections have been printed.
        
        Args:
            initial_setup_lines: List of strings for initial instructions (can be None if not at starting phase)
            payment_received_lines: List of strings for payment confirmation (can be None if not at payment phase)
            app_generated_lines: List of strings for app generation details (can be None if not at app generation phase)
            venmo_qr_data: Data for the Venmo QR code to print (can be None if not needed)
            cut_after: Whether to cut the paper after printing (set to True only after all sections are printed)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized or not self.printer:
            # Log to console if printer not available
            combined_lines = []
            if initial_setup_lines:
                combined_lines.extend(initial_setup_lines)
                if venmo_qr_data:
                    combined_lines.extend(["--- VENMO QR CODE ---", f"QR Data: {venmo_qr_data}"])
            if payment_received_lines:
                combined_lines.extend(["--- PAYMENT RECEIVED ---"] + payment_received_lines)
            if app_generated_lines:
                combined_lines.extend(["--- APP GENERATED ---"] + app_generated_lines)
                
            print("[NO PRINTER] " + "\n[NO PRINTER] ".join(combined_lines))
            printer_logger.warning("Thermal printer not available, skipping continuous receipt print. Logged to console.")
            return False
            
        try:
            # Print initial setup if provided (only at the start of the flow)
            if initial_setup_lines:
                self.printer.set(align='center', width=1, height=1)
                for line in initial_setup_lines:
                    self.printer.textln(line)
                
                # Add a bit of space
                self.printer.text("\n")
                
                # If Venmo QR data is provided, print it as part of the initial setup
                if venmo_qr_data:
                    self.printer.set(align='center')
                    self.printer.textln("SCAN TO PAY WITH VENMO:")
                    self.printer.qr(venmo_qr_data, size=6)
                    self.printer.textln("Include app description and amount in your payment")
                    self.printer.text("\n")
                
            # Print payment received section if provided (during payment phase)
            if payment_received_lines:
                # Header for payment section
                self.printer.set(align='center', width=1, height=1)
                self.printer.textln("PAYMENT RECEIVED!")
                self.printer.text("--------------------\n")
                
                # Payment details
                self.printer.set(align='left', width=1, height=1)
                for line in payment_received_lines:
                    self.printer.textln(line)
                    
                # Add a bit of space
                self.printer.text("\n")
                
            # Print app generated section if provided (during app generation phase)
            if app_generated_lines:
                # Header for app generation section
                self.printer.set(align='center', width=1, height=1)
                self.printer.textln("APP GENERATED!")
                self.printer.text("--------------------\n")
                
                # App generation details
                self.printer.set(align='left', width=1, height=1)
                for line in app_generated_lines:
                    self.printer.textln(line)
                    
                # Thank you message at the end
                self.printer.set(align='center', width=1, height=1)
                self.printer.text("\n--------------------\n")
                self.printer.textln("Thank you for using Vibe Coder!")
                self.printer.textln(time.strftime("%Y-%m-%d %H:%M:%S"))
                
            # Only cut if explicitly requested (typically only after all sections are printed)
            if cut_after:
                self.printer.cut()
                
            return True
                
        except EscposError as e:
            printer_logger.error(f"ESC/POS library error during continuous receipt printing: {e}")
            return False
            
        except Exception as e:
            printer_logger.error(f"Unexpected error during continuous receipt printing: {e}")
            return False

    def close(self):
        """Close the connection to the printer."""
        try:
            if self.printer:
                # No explicit close method in escpos, but we can reset some settings
                self.printer.hw('INIT')
                self.printer = None
                self.initialized = False
                printer_logger.info("Thermal printer connection closed")
                return True
        except Exception as e:
            printer_logger.error(f"Error closing printer connection: {e}")
        
        return False

# Create singleton instance for importing in other modules
thermal_printer_manager = ThermalPrinter()