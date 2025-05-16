#!/usr/bin/env python3.11
import os
import uuid
import string
import random
import google.generativeai as genai
import re
import sys
import time
from dotenv import load_dotenv
# Import thermal printer for iteration updates
from thermal_printer import thermal_printer_manager

# Fix import paths
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import central configuration
from config import GENERATED_APPS_DIR, GEMINI_API_KEY, GEMINI_MODELS, APP_TIERS, get_app_tier

# Ensure generated apps directory exists
os.makedirs(GENERATED_APPS_DIR, exist_ok=True)

# Configure the Gemini client
model = None
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODELS["default"])
        print("Gemini API configured successfully.")
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        model = None  # Set model to None if configuration fails

def generate_friendly_app_id():
    """
    Generates a user-friendly app ID that's shorter and easier to read than a UUID.
    Format: 4 letters + 4 digits (e.g., VIBE1234)
    """
    # Use uppercase letters only (avoiding similar looking characters like I, O, etc.)
    letters = ''.join(c for c in string.ascii_uppercase if c not in 'IO')
    digits = ''.join(d for d in string.digits if d not in '01')
    
    # Generate the ID: 4 letters + 4 digits
    letters_part = ''.join(random.choices(letters, k=4))
    digits_part = ''.join(random.choices(digits, k=4))
    
    return f"{letters_part}{digits_part}"

def create_slug_from_title(title):
    """
    Creates a URL-friendly slug from an app title.
    Converts the title to lowercase, replaces spaces with dashes, and removes special characters.
    
    Args:
        title: The app title to convert
        
    Returns:
        A URL-friendly slug (e.g. "my-weather-app")
    """
    import re
    # Convert to lowercase, replace spaces with dashes
    slug = title.lower().replace(' ', '-')
    # Remove special characters
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    # Remove multiple dashes
    slug = re.sub(r'\-+', '-', slug)
    # Limit length to 50 characters
    slug = slug[:50].strip('-')
    # Add random characters if too short
    if len(slug) < 3:
        import random
        import string
        chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        slug = f"app-{chars}" if not slug else f"{slug}-{chars}"
    return slug

def generate_code_with_gemini(app_type: str, tier: str, readme_content: str) -> str | None:
    """Generates HTML/CSS/JS code using Gemini based on app type, tier, and README content."""
    if not model:
        print("Gemini model not configured or configuration failed. Cannot generate code.")
        return None
    
    # Select model based on tier
    model_name = APP_TIERS[tier]["model"]
    model_to_use = genai.GenerativeModel(model_name)
    
    prompt = (
        f"Create a complete, single-file HTML web application based on the following information:\n\n"
        f"ORIGINAL USER REQUEST: \"{app_type}\"\n\n"
        f"README CONTENT:\n{readme_content}\n\n"
        f"Requirements:\n"
        f"- The app MUST implement the functionality described in the ORIGINAL USER REQUEST first and foremost.\n"
        f"- The entire application (HTML structure, CSS styles, and JavaScript logic) MUST be contained within a single HTML file, no usage of external API end-points that might not work.\n"
        f"- CSS should be included in a `<style>` tag within the `<head>`.\n"
        f"- JavaScript should be included in a `<script>` tag, preferably at the end of the `<body>`.\n"
        f"- The application must be functional, ready to use, and accurately reflect the description and features outlined in the provided README.\n"
        f"- Add a small footer that indicates this was made by Vibe Coder.\n"
        f"- Your response MUST contain ONLY the raw HTML code, starting precisely with `<!DOCTYPE html>` and ending precisely with `</html>`.\n"
        f"- Do NOT include any markdown formatting (like ```html), comments, explanations, or any text outside the HTML code itself."
    )

    try:
        print(f"--- Sending prompt to Gemini for {app_type} ({tier} tier) ---")
        response = model_to_use.generate_content(prompt)
        
        # Extract code block if necessary (sometimes LLMs add markdown)
        # Updated regex to optionally match 'html' after ```
        code_match = re.search(r"```(?:html)?\n(.*?)\n```", response.text, re.DOTALL | re.IGNORECASE)
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
        # Safely access response info only if it was defined
        response_var = locals().get('response')
        if response_var:
            if hasattr(response_var, "prompt_feedback"):
                print(f"Prompt Feedback: {response_var.prompt_feedback}")
            if hasattr(response_var, "candidates") and response_var.candidates:
                print(f"Finish Reason: {response_var.candidates[0].finish_reason}")
                print(f"Safety Ratings: {response_var.candidates[0].safety_ratings}")
        return None

def generate_readme_with_gemini(app_type: str, amount: float, tier: str, app_id: str) -> str | None:
    """Generates a README.md for the application using Gemini Flash."""
    if not model:
        print("Gemini model not configured or configuration failed. Cannot generate README.")
        return None
    
    # Always use Flash for README generation as per requirements
    model_to_use = genai.GenerativeModel(GEMINI_MODELS["readme"])
    
    # Get current date in readable format
    current_date = time.strftime("%B %d, %Y")
    
    prompt = (
        f"Create a detailed README.md file for a web application with the following information:\n\n"
        f"Original User Request: \"{app_type}\"\n"
        f"Payment Amount: ${amount:.2f}\n"
        f"AI Model Used: Gemini {'Pro' if tier == 'high' else 'Flash'}\n"
        f"App ID: {app_id}\n"
        f"Created On: {current_date}\n\n"
        f"Include the following sections:\n"
        f"1. Introduction - Brief description of the app that starts with the original user request\n"
        f"2. App Requirements - List the specific requirements based on the original user request\n"
        f"3. Features - Bullet points of what the app can do\n"
        f"4. How to Use - Step-by-step instructions\n"
        f"5. Technical Details - Mention it's a single-file HTML app using Gemini AI\n"
        f"6. Credits - Include a thank you message to the user for their payment\n\n"
        f"Make sure the README title includes the kind of app clearly at the beginning.\n"
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
            f"## Original User Request\n\n"
            f"```\n{app_type}\n```\n\n"
            f"## Features\n\n"
            f"- Single-file HTML application\n"
            f"- Generated using AI based on the user request\n\n"
            f"## How to Use\n\n"
            f"1. Interact with the app using your browser\n"
            f"2. Refresh the page to reset if needed\n\n"
            f"## Technical Details\n\n"
            f"- Created using Gemini {'Pro' if tier == 'high' else 'Flash'} AI\n"
            f"- App ID: {app_id}\n"
            f"- Created on: {time.strftime('%B %d, %Y')}\n\n"
            f"## Credits\n\n"
            f"Thank you for your payment of ${amount:.2f}!\n"
            f"Made by Vibe Coder\n"
        )

def update_slug_mapping(app_id, slug):
    """
    Updates a JSON file that maps slugs to app IDs.
    This allows looking up apps by their friendly URL slug.
    
    Args:
        app_id: The unique ID of the app
        slug: The URL-friendly slug for the app
    """
    import json
    import os
    
    # Skip if no slug provided
    if not slug:
        return
        
    # Path to the mapping file
    mapping_file = os.path.join(GENERATED_APPS_DIR, "slug_mapping.json")
    
    # Load existing mapping or create new one
    mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
        except Exception as e:
            print(f"Error loading slug mapping: {e}")
    
    # Add or update the mapping
    mapping[slug] = app_id
    
    # Save the updated mapping
    try:
        with open(mapping_file, 'w') as f:
            json.dump(mapping, f, indent=2)
        print(f"Updated slug mapping: {slug} -> {app_id}")
    except Exception as e:
        print(f"Error saving slug mapping: {e}")

def generate_app_files(app_type: str, amount: float) -> dict | None:
    """Generates app files using Gemini, saves them, and returns details."""
    
    # Generate a user-friendly app ID instead of UUID
    app_id = generate_friendly_app_id()  # Shorter, more user-friendly ID
    app_dir = os.path.join(GENERATED_APPS_DIR, app_id)
    os.makedirs(app_dir, exist_ok=True)
    output_path = os.path.join(app_dir, "index.html")
    readme_path = os.path.join(app_dir, "README.md")

    # Determine tier and iterations based on amount
    from config import calculate_iterations
    tier = get_app_tier(amount)
    iterations = calculate_iterations(amount, tier)

    # Generate README.md using Gemini Flash first
    generated_readme = generate_readme_with_gemini(app_type, amount, tier, app_id)

    if not generated_readme:
        print(f"Failed to generate README.md for {app_type}. Aborting app generation.")
        # Clean up directory if README generation failed
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None
        
    # Try to extract a title from the README
    app_title = app_type  # Default to app_type if we can't find a title
    try:
        import re
        # Look for the first markdown heading (# Title)
        title_match = re.search(r'^#\s+(.+)$', generated_readme, re.MULTILINE)
        if title_match:
            app_title = title_match.group(1).strip()
            
            # Clean up the title if it contains "Web Application" or similar at the end
            app_title = re.sub(r'\s+(Web\s+)?(App(lication)?|Project)$', '', app_title, flags=re.IGNORECASE)
            
            # If the title doesn't include the app_type anywhere, add it to make searching easier
            if app_type.lower() not in app_title.lower() and len(app_title) < 40:
                app_title = f"{app_title}: {app_type}"
    except Exception as e:
        print(f"Error extracting title from README: {e}")
    
    # Create a URL-friendly slug from the title
    app_slug = create_slug_from_title(app_title)
    
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
        # Save README.md file with information about iterations
        if iterations > 1:
            # Add information about iterations to the README
            generated_readme += f"\n\n## Generation Process\n\nThis app was created with {iterations} iterations of AI improvement based on your payment of ${amount:.2f}.\n"
        
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(generated_readme)

        # Perform iterative improvements if applicable
        current_html = generated_html
        iteration_history = [current_html]  # Keep track of each iteration
        
        if iterations > 1:
            print(f"Starting iterative improvement: {iterations} iterations requested")
            
            # Create a versions directory to store each iteration
            versions_dir = os.path.join(app_dir, "versions")
            os.makedirs(versions_dir, exist_ok=True)
            
            # Print initial receipt message about iterations
            thermal_printer_manager.print_text([
                "GENERATING APP WITH ITERATIONS",
                f"App ID: {app_id}",
                f"Request: {app_type}",
                f"Total iterations: {iterations}",
                f"Starting generation...",
                "--------------------"
            ], align='left', cut=False)
            
            # Save the initial version
            with open(os.path.join(versions_dir, "version_0.html"), "w", encoding="utf-8") as f:
                f.write(current_html)
            
            # Run through the requested number of iterations
            for i in range(1, iterations):
                print(f"Performing improvement iteration {i} of {iterations-1}...")
                
                # Determine focus area based on iteration number
                focus_area = "Core functionality"
                if i <= 2:
                    focus_area = "Core functionality & UX"
                elif i <= 4:
                    focus_area = "Visual design & UI"
                else:
                    focus_area = "Advanced features & polish"
                
                # Print iteration update to receipt
                thermal_printer_manager.print_text([
                    f"Iteration {i} of {iterations-1} starting...",
                    f"Enhancing app: {app_title}",
                    f"Focus: {focus_area}"
                ], align='left', cut=False)
                
                # Improve the app
                improved_html = improve_app_iteratively(
                    current_html, app_type, tier, i, iterations-1
                )
                
                # Save this iteration
                with open(os.path.join(versions_dir, f"version_{i}.html"), "w", encoding="utf-8") as f:
                    f.write(improved_html)
                
                # Print iteration completion to receipt
                thermal_printer_manager.print_text([
                    f"Iteration {i} completed!",
                    "--------------------"
                ], align='left', cut=False)
                
                # Update current HTML for next iteration
                current_html = improved_html
                iteration_history.append(current_html)
        
        # Save the final HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(current_html)
        
        # Update slug mapping
        update_slug_mapping(app_id, app_slug)
        
        # Print completion message for iterations
        if iterations > 1:
            thermal_printer_manager.print_text([
                "ALL ITERATIONS COMPLETE!",
                f"App {app_id} successfully enhanced",
                f"Total iterations performed: {iterations}",
                f"Final version saved to index.html",
                "--------------------"
            ], align='left', cut=False)
        
        print(f"Generated app {app_id} at {output_path} with {iterations} iterations")
        
        return {
            "app_id": app_id,
            "app_type": app_type,
            "title": app_title,        # The extracted title from README
            "slug": app_slug,          # URL-friendly version of the title
            "amount": amount,
            "tier": tier,
            "iterations": iterations,   # Number of iterations performed
            "path": app_dir,           # Directory containing the generated app (index.html)
            "file_path": output_path,  # Specific path to the index.html file
            "readme_path": readme_path, # Path to the README.md file
            "iteration_history": len(iteration_history)  # Number of versions saved
        }

    except Exception as e:
        print(f"Error saving generated app {app_id} ({app_type}): {e}")
        # Clean up potentially partially created directory
        if os.path.exists(app_dir):
            import shutil
            shutil.rmtree(app_dir)
        return None

def improve_app_iteratively(html_content, app_type, tier, iteration_num, total_iterations):
    """
    Improves an existing app through iterative refinement.
    
    Args:
        html_content: The current HTML content of the app
        app_type: The type of application requested
        tier: The app tier (low, high, premium)
        iteration_num: The current iteration number
        total_iterations: The total number of iterations to be performed
        
    Returns:
        Improved HTML content
    """
    if not model:
        print("Gemini model not configured or configuration failed. Cannot improve app.")
        # Print error to receipt
        thermal_printer_manager.print_text([
            f"ITERATION {iteration_num} ERROR:",
            "Gemini model not configured",
            "Using previous version"
        ], align='left', cut=False)
        return html_content
    
    # Use the premium model for iterative improvement
    model_name = APP_TIERS["premium"]["model"]
    model_to_use = genai.GenerativeModel(model_name)
    
    prompt = (
        f"You are improving a single-file web application through iteration {iteration_num} of {total_iterations}.\n\n"
        f"ORIGINAL USER REQUEST: \"{app_type}\"\n\n"
        f"CURRENT HTML CONTENT: \n```html\n{html_content}\n```\n\n"
        f"Instructions for improvement (iteration {iteration_num}/{total_iterations}):\n"
        f"1. Analyze the current app and identify opportunities for enhancement\n"
        f"2. For this iteration, focus on the following aspects:\n"
        f"   - Iteration 1-2: Core functionality and user experience improvements\n"
        f"   - Iteration 3-4: Visual design and UI refinements\n"
        f"   - Iteration 5+: Advanced features and polish\n"
        f"3. Implement meaningful improvements while maintaining all existing functionality\n"
        f"4. Keep all the original features but enhance them\n"
        f"5. Provide a complete, updated version of the single HTML file\n\n"
        f"Return ONLY the improved HTML code without any explanation or markdown formatting. "
        f"Start with <!DOCTYPE html> and end with </html>."
    )
    
    try:
        print(f"--- Sending Gemini prompt for app improvement (Iteration {iteration_num}/{total_iterations}) ---")
        response = model_to_use.generate_content(prompt)
        
        # Extract code from response
        code_match = re.search(r"```(?:html)?\n(.*?)\n```", response.text, re.DOTALL | re.IGNORECASE)
        if code_match:
            improved_code = code_match.group(1).strip()
        else:
            # Assume the whole response is the code if no markdown block found
            improved_code = response.text.strip()
        
        # Basic validation to ensure it's HTML
        if not improved_code.lower().startswith("<!doctype html") and not improved_code.lower().startswith("<html"):
            print(f"Warning: Improved code doesn't look like HTML. Using previous version.")
            # Print warning to receipt
            thermal_printer_manager.print_text([
                f"ITERATION {iteration_num} WARNING:",
                "Generated code is not valid HTML",
                "Using previous version"
            ], align='left', cut=False)
            return html_content
            
        print(f"Successfully improved app (Iteration {iteration_num}/{total_iterations})")
        
        # Calculate rough file size change as a metric of improvement
        original_size = len(html_content)
        new_size = len(improved_code)
        size_diff = new_size - original_size
        size_change = f"{'+' if size_diff > 0 else ''}{size_diff} bytes"
        
        # Print success to receipt with some basic stats
        thermal_printer_manager.print_text([
            f"Iteration {iteration_num} successful:",
            f"Code size change: {size_change}",
            f"Enhancements applied!"
        ], align='left', cut=False)
        
        return improved_code
        
    except Exception as e:
        print(f"Error improving app in iteration {iteration_num}: {e}")
        # Safely access response info only if it was defined
        response_var = locals().get('response')
        if response_var and hasattr(response_var, "text"):
            print(f"Response text starts with: {response_var.text[:100]}...")
        
        # Print error to receipt
        thermal_printer_manager.print_text([
            f"ITERATION {iteration_num} ERROR:",
            f"{str(e)[:40]}...",
            "Using previous version"
        ], align='left', cut=False)
        
        # Return original content on error
        return html_content

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

