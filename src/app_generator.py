#!/usr/bin/env python3.11
import os
import uuid
import google.generativeai as genai
import re
import sys # Added for path manipulation

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
        model = genai.GenerativeModel("gemini-1.5-flash-latest") # Using 1.5 flash as requested
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        model = None # Set model to None if configuration fails

def generate_code_with_gemini(app_type: str, tier: str) -> str | None:
    """Generates HTML/CSS/JS code using Gemini based on app type and tier."""
    if not model:
        print("Gemini model not configured or configuration failed. Cannot generate code.")
        return None
        
    tier_description = "High Tier (\"bright\" / \"autonomy-supporting\"): Implement all reasonable features for the app type. Use a clean, bright, user-friendly interface (light background, clear text, good contrast)."
    if tier == "low":
        tier_description = "Low Tier (\"dark\" / \"autonomy-blocking\"): Implement only the most basic functionality. Use a darker, potentially less intuitive interface (dark background, maybe slightly lower contrast text). For example, a low-tier calculator might lack advanced functions, or a low-tier timer might not allow custom time input."

    prompt = (
        f"Create a complete, single-file HTML web application for: \"{app_type}\".\n"
        f"The application's features and visual style must correspond to this ethical tier:\n"
        f"Tier: {tier.upper()}\n"
        f"Description: {tier_description}\n\n"
        f"Requirements:\n"
        f"- The entire application (HTML structure, CSS styles, and JavaScript logic) MUST be contained within a single HTML file.\n"
        f"- CSS should be included in a `<style>` tag within the `<head>`.\n"
        f"- JavaScript should be included in a `<script>` tag, preferably at the end of the `<body>`.\n"
        f"- The application must be functional and ready to use.\n"
        f"- Your response MUST contain ONLY the raw HTML code, starting precisely with `<!DOCTYPE html>` and ending precisely with `</html>`.\n"
        f"- Do NOT include any markdown formatting (like ```html), comments, explanations, or any text outside the HTML code itself."
    )

    try:
        print(f"--- Sending prompt to Gemini for {app_type} ({tier} tier) ---")
        response = model.generate_content(prompt)
        
        # Extract code block if necessary (sometimes LLMs add markdown)
        code_match = re.search(r"```html\n(.*?)\n```", response.text, re.DOTALL | re.IGNORECASE)
        if code_match:
            generated_code = code_match.group(1).strip()
        else:
            # Assume the whole response is the code if no markdown block found
            generated_code = response.text.strip()
            
        # Basic validation: Check if it looks like HTML
        if not generated_code.lower().startswith("<!doctype html") and not generated_code.lower().startswith("<html"):
             print("Warning: Gemini response doesn\"t look like HTML. Using raw response.")
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

def generate_app_files(app_type: str, amount: float) -> dict | None:
    """Generates app files using Gemini, saves them, and returns details."""
    
    app_id = str(uuid.uuid4()) # Unique ID for this app instance
    app_dir = os.path.join(GENERATED_APPS_DIR, app_id)
    os.makedirs(app_dir, exist_ok=True)
    output_path = os.path.join(app_dir, "index.html")

    # Determine tier based on amount
    tier = "high" if amount >= 5.0 else "low"

    # Generate code using Gemini
    generated_html = generate_code_with_gemini(app_type, tier)

    if not generated_html:
        print(f"Failed to generate code from Gemini for {app_type} ({tier} tier).")
        # Clean up directory if generation failed
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None

    # --- Save Generated Code ---
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(generated_html)
            
        print(f"Generated app 	{app_id}	 at 	{output_path}")
        
        return {
            "app_id": app_id,
            "app_type": app_type,
            "amount": amount,
            "tier": tier,
            "path": app_dir, # Directory containing the generated app (index.html)
            "file_path": output_path # Specific path to the index.html file
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

