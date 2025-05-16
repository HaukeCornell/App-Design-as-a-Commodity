"""
Receipt Manager - Handles the thermal printer workflow for generating receipts
through different stages of the app purchase transaction.
"""
import time
import logging
from thermal_printer import thermal_printer_manager

# ASCII art for VIBE CODER
VIBE_CODER_ASCII = [
    "\\  /o|_  _   /   _  _| _  _",
    " \\/ ||_)(-`  \\__(_)(_|(-`| "
]

class ReceiptManager:
    """Manages the printing of receipts for the app purchase workflow."""
    
    def __init__(self):
        # Simplified - printer is always considered available (will print to console if not)
        self.current_transaction_in_progress = False
        # Configure logger
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def print_payment_header(self, payment_mode, payment_url):
        """
        Print the initial receipt header when waiting for payment.
        Always cuts the paper and prints a new header when called.
        
        Args:
            payment_mode: The payment mode name (e.g., "Venmo" or "VibePay")
            payment_url: The URL to use for the payment QR code
        """
        # Always cut the paper before printing a new header
        thermal_printer_manager.cut_paper()
        
        # Always mark that we're starting a new transaction
        self.current_transaction_in_progress = True
        
        # Header lines to print
        header_lines = [
            "App Design as a Commodity",
            "Interactive Art Installation",
            time.strftime("%m/%d/%Y"),
            "www.haukesand.github.io",
            "",
            "",
            "",
            VIBE_CODER_ASCII[0],
            VIBE_CODER_ASCII[1],
            "",
            "ITEM:",
            "CUSTOM APP DEVELOPMENT",
            "",
            "- Pay $0.25 for a quick app",
            "- Pay $1.00 for a high quality app",
            "",
            f"In the {payment_mode} description,",
            "describe the app you want.",
            "",
            "Your app will be automatically",
            "generated after payment.",
            "--------------------",
            f"Scan QR code to pay with {payment_mode}:",
            "",
        ]
        
        try:
            # Print the header
            thermal_printer_manager.print_text(header_lines, align='center', cut=False)
            
            # Print the payment QR code - with larger size
            thermal_printer_manager.print_qr(
                payment_url, 
                text_above=f"PAY WITH {payment_mode.upper()}", 
                text_below="Include app description in payment note",
                cut=False,
                size=10  # Increase QR code size (default is usually 3-4)
            )
            
            # Add a waiting message
            thermal_printer_manager.print_text([
                "",
                "WAITING FOR PAYMENT...",
                time.strftime("%H:%M:%S"),
                "",
                "",
            ], align='center', cut=False)
            
            self.logger.info(f"Payment header printed for {payment_mode}")
            return True
        except Exception as e:
            self.logger.error(f"Error printing payment header: {e}")
            
            # Print debugging info to console
            self.logger.info("\n----- PAYMENT HEADER (ERROR FALLBACK) -----")
            for line in header_lines:
                self.logger.info(line)
            self.logger.info(f"QR CODE URL: {payment_url}")
            self.logger.info(f"WAITING FOR PAYMENT... ({time.strftime('%H:%M:%S')})")
            self.logger.info("----------------------------------------")
            
            # Still consider this a successful print for flow purposes
            return True
    
    def print_payment_confirmation(self, payment_details):
        """
        Print the payment confirmation section of the receipt.
        
        Args:
            payment_details: Dict with payment information including:
                - amount: Payment amount
                - note: App description
                - sender: Name of the person who paid
        """
        if not self.current_transaction_in_progress:
            self.logger.warning("No transaction in progress - starting a new one for payment confirmation")
            # Force start a new transaction
            self.current_transaction_in_progress = True
        
        try:
            # Format the payment details
            amount = payment_details.get("amount", 0)
            note = payment_details.get("note", "")
            sender = payment_details.get("sender", "Customer")
            
            # Payment confirmation section
            confirmation_lines = [
                "--------------------",
                "PAYMENT RECEIVED!",
                "--------------------",
                f"FROM: {sender}",
                f"AMOUNT: ${float(amount):.2f}",
                f"REQUEST: {note}",
                "",
                "Generating your app now...",
                "Please wait",
                time.strftime("%Y-%m-%d %H:%M:%S"),
                "",
                "",
            ]
            
            # Print to thermal printer - simplified implementation
            thermal_printer_manager.print_text(confirmation_lines, align='left', cut=False)
            self.logger.info("Payment confirmation printed")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error printing payment confirmation: {e}")
            return False
    
    def print_app_completion(self, app_details, hosted_url_full):
        """
        Print the app completion section with QR code, and cut the paper.
        
        Args:
            app_details: Dict with app information
            hosted_url_full: URL where the app is hosted (for QR code)
        """
        if not self.current_transaction_in_progress:
            self.logger.warning("No transaction in progress - starting a new one for app completion")
            # Force start a new transaction
            self.current_transaction_in_progress = True
        
        try:
            # Get required app details with defaults
            app_id = app_details.get("app_id", "unknown")
            app_type = app_details.get("app_type", "unknown")
            app_tier = app_details.get("tier", "unknown")
            github_url = app_details.get("github_url", "Not available")
            
            # Format GitHub URL message
            if "Error:" in github_url or "not found" in github_url or "denied" in github_url:
                github_message = ["GITHUB PUSH FAILED.", "App was generated locally."]
            else:
                github_message = ["GitHub Repository:", github_url]
            
            # App completion section
            completion_lines = [
                "--------------------",
                "APP GENERATED SUCCESSFULLY!",
                "--------------------",
                f"App Type: {app_type}",
                f"Tier: {app_tier}",
                f"ID: {app_id}",
                ""
            ]
            completion_lines.extend(github_message)
            completion_lines.extend([
                "",
                "Access your app at:",
                hosted_url_full,
                "",
                "SCAN QR CODE TO USE YOUR APP:",
            ])
            
            thank_you_lines = [
                "",
                "Thank you for supporting",
                "App Design as a Commodity",
                "",
                "Made with ♥ by Vibe Coder",
                time.strftime("%Y-%m-%d %H:%M:%S"),
                "",
                "",
            ]
            
            # Print to thermal printer - completion message
            thermal_printer_manager.print_text(completion_lines, align='left', cut=False)
            
            # Print the QR code to access the app
            try:
                thermal_printer_manager.print_qr(
                    hosted_url_full,
                    text_above="YOUR APP IS READY",
                    text_below="Thank you for using Vibe Coder!",
                    cut=False,
                    size=10  # Increase QR code size
                )
            
                # Add a final thank you message and cut the paper
                thermal_printer_manager.print_text(thank_you_lines, align='center', cut=True)
                
                self.logger.info("App completion receipt printed and paper cut")
            except Exception as e:
                self.logger.error(f"Error printing QR code: {e}")
                # Print URL as fallback
                thermal_printer_manager.print_text([
                    "QR CODE ERROR - USE URL BELOW:",
                    hosted_url_full,
                ], align='center', cut=False)
                
                # Console debugging info
                self.logger.info("\n----- APP COMPLETION (ERROR FALLBACK) -----")
                for line in completion_lines:
                    self.logger.info(line)
                self.logger.info(f"QR CODE URL: {hosted_url_full}")
                for line in thank_you_lines:
                    self.logger.info(line)
                self.logger.info("----------------------------------------")
            
            # Transaction is complete
            self.current_transaction_in_progress = False
            return True
            
        except Exception as e:
            self.logger.error(f"Error printing app completion: {e}")
            return False

    def _cut_paper(self):
        """Cut the paper if the printer supports it."""
        try:
            thermal_printer_manager.cut_paper()
            return True
        except Exception as e:
            self.logger.error(f"Error cutting paper: {e}")
            return False

# Create a global instance for easy import from other modules
receipt_manager = ReceiptManager()
