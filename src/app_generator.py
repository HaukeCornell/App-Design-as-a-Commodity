#!/usr/bin/env python3.11
import os
import uuid
import google.generativeai as genai
import re
import sys # Added for path manipulation
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Get the absolute path of the directory containing this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_APPS_DIR = os.path.abspath(os.path.join(_SCRIPT_DIR, "generated_apps"))

# --- IMPORTANT: Load API keys from environment variables --- 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

os.makedirs(GENERATED_APPS_DIR, exist_ok=True)

# Configure the Gemini client
model = None
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-pro-latest") # Using 1.5 Pro as the default model
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        model = None # Set model to None if configuration fails

def generate_code_with_gemini(app_type: str, tier: str, readme_content: str) -> str | None:
    """Generates HTML/CSS/JS code using Gemini based on app type, tier, and README content."""
    if not model:
        print("Gemini model not configured or configuration failed. Cannot generate code.")
        return None
    
    # Select model based on tier
    model_to_use = genai.GenerativeModel("gemini-2.5-pro-preview-03-25") if tier == "high" else genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
    
    prompt = (
        f"Create a complete, single-file HTML web application based on the following README.md content:\n\n"
        f"--- README START ---\n{readme_content}\n--- README END ---\n\n"
        f"The application should be for: \"{app_type}\".\n"
        f"Requirements:\n"
        f"- The entire application (HTML structure, CSS styles, and JavaScript logic) MUST be contained within a single HTML file.\n"
        f"- CSS should be included in a `<style>` tag within the `<head>`.\n"
        f"- JavaScript should be included in a `<script>` tag, preferably at the end of the `<body>`.\n"
        f"- The application must be functional, ready to use, and accurately reflect the description and features outlined in the provided README.\n"
        f"- Your response MUST contain ONLY the raw HTML code, starting precisely with `<!DOCTYPE html>` and ending precisely with `</html>`.\n"
        f"- Do NOT include any markdown formatting (like ```html), comments, explanations, or any text outside the HTML code itself."
    )

    try:
        print(f"--- Sending prompt to Gemini for {app_type} ({tier} tier) ---")
        response = model_to_use.generate_content(prompt)
        
        # Extract code block if necessary (sometimes LLMs add markdown)
        code_match = re.search(r"```html\n(.*?)\n```", response.text, re.DOTALL | re.IGNORECASE)
        if code_match:
            generated_code = code_match.group(1).strip()
        else:
            # Assume the whole response is the code if no markdown block found
            generated_code = response.text.strip()
            
        # Basic validation: Check if it looks like HTML
        if not generated_code.lower().startswith("<!doctype html") and not generated_code.lower().startswith("<html"):
             print("Warning: Gemini response doesn't look like HTML. Using raw response.")
             generated_code = response.text.strip()
             if not generated_code: # If response was empty or only whitespace
                 raise ValueError("Gemini returned empty response.")

        return generated_code

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # Add more detailed error info if available from the response object
        if hasattr(response, "prompt_feedback"):
            print(f"Prompt Feedback: {response.prompt_feedback}")
        if hasattr(response, "candidates") and response.candidates:
             print(f"Finish Reason: {response.candidates[0].finish_reason}")
             print(f"Safety Ratings: {response.candidates[0].safety_ratings}")
        return None

def generate_readme_with_gemini(app_type: str, amount: float, tier: str, app_id: str) -> str | None:
    """Generates a README.md for the application using Gemini Flash."""
    if not model:
        print("Gemini model not configured or configuration failed. Cannot generate README.")
        return None
    
    # Always use Flash for README generation as per requirements
    model_to_use = genai.GenerativeModel("gemini-1.5-flash-latest")
    
    # Get current date in readable format
    current_date = time.strftime("%B %d, %Y")
    
    prompt = (
        f"Create a detailed README.md file for a web application with the following information:\n\n"
        f"App Type: {app_type}\n"
        f"Payment Amount: ${amount:.2f}\n"
        f"AI Model Used: Gemini {'Pro' if tier == 'high' else 'Flash'}\n"
        f"App ID: {app_id}\n"
        f"Created On: {current_date}\n\n"
        f"Include the following sections:\n"
        f"1. Introduction - Brief description of the app\n"
        f"2. Features - Bullet points of what the app can do\n"
        f"3. How to Use - Step-by-step instructions\n"
        f"4. Technical Details - Mention it's a single-file HTML app using Gemini AI\n"
        f"5. Credits - Include a thank you message to testuser for their venmo payment\n\n"
        f"Format it as proper markdown, including headers, lists, and emphasis where appropriate."
    )

    try:
        print(f"--- Sending prompt to Gemini Flash for README generation ---")
        response = model_to_use.generate_content(prompt)
        
        # Extract markdown content
        generated_readme = response.text.strip()
        
        if not generated_readme:
            raise ValueError("Gemini returned empty response for README.")

        return generated_readme

    except Exception as e:
        print(f"Error calling Gemini API for README: {e}")
        # Fallback README if generation fails
        return (
            f"# {app_type} Web Application\n\n"
            f"This app was generated by Vibe Coder using Gemini {'Pro' if tier == 'high' else 'Flash'}.\n\n"
            f"## Features\n\n"
            f"- Single-file HTML application\n"
            f"- Generated using AI\n\n"
            f"## Credits\n\n"
            f"Thank you to testuser for the Venmo payment of ${amount:.2f}!\n"
        )

def generate_app_files(app_type: str, amount: float) -> dict | None:
    """Generates app files using Gemini, saves them, and returns details."""
    
    app_id = str(uuid.uuid4()) # Unique ID for this app instance
    app_dir = os.path.join(GENERATED_APPS_DIR, app_id)
    os.makedirs(app_dir, exist_ok=True)
    output_path = os.path.join(app_dir, "index.html")
    readme_path = os.path.join(app_dir, "README.md")

    # Determine tier based on amount
    tier = "high" if amount >= 5.0 else "low"

    # Generate README.md using Gemini Flash first
    generated_readme = generate_readme_with_gemini(app_type, amount, tier, app_id)

    if not generated_readme:
        print(f"Failed to generate README.md for {app_type}. Aborting app generation.")
        # Clean up directory if README generation failed
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None

    # Generate code using Gemini, now including the generated_readme
    generated_html = generate_code_with_gemini(app_type, tier, generated_readme)

    if not generated_html:
        print(f"Failed to generate code from Gemini for {app_type} ({tier} tier) using the generated README.")
        # Clean up directory if code generation failed
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None

    # --- Save Generated Files ---
    try:
        # Save README.md file
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(generated_readme)

        # Save HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(generated_html)
            
        print(f"Generated app 	{app_id}	 at 	{output_path}")
        
        return {
            "app_id": app_id,
            "app_type": app_type,
            "amount": amount,
            "tier": tier,
            "path": app_dir, # Directory containing the generated app (index.html)
            "file_path": output_path, # Specific path to the index.html file
            "readme_path": readme_path # Path to the README.md file
        }

    except Exception as e:
        print(f"Error saving generated app {app_id} ({app_type}): {e}")
        # Clean up potentially partially created directory
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None

# Example usage (for testing - requires GEMINI_API_KEY env var):
if __name__ == "__main__":
    if not model:
        print("Cannot run example: Gemini model not configured.")
    else:
        print("\n--- Testing Low Tier Calculator ---")
        details_low = generate_app_files("Simple Calculator", 2.50)
        if details_low:
            with open(details_low["file_path"], "r") as f:
                print(f.read()[:500] + "...") # Print start of generated file
        
        print("\n--- Testing High Tier Timer ---")
        details_high = generate_app_files("Basic Timer with custom duration input", 10.00)
        if details_high:
             with open(details_high["file_path"], "r") as f:
                print(f.read()[:500] + "...") # Print start of generated file

