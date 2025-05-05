# App Design as a Commodity
## Vibe Coder Art Installation - README


## Project Concept

_App Design as a Commodity_ is an interactive art installation exploring the intersection of value, labor, automation, and ethics in software creation. It manifests as a system where participants can commission small, custom web applications by sending a payment via a Venmo donation along with a description of the desired app.

This project illustrates how app development, once a high-status job, has become just another industrialized commodity. Software is treated as a transactional good through algorithmic labor. 

## System Workflow

1.  **Request:** A user initiates a request, specifying the desired app (e.g., "Simple Calculator", "Coffee Shop Landing Page") and sending a payment (currently simulated via a web form, potentially triggered by Venmo email confirmation in the future).
2.  **Processing:** The backend system receives the request and payment amount.
3.  **Vibe Coding (LLM Generation):** The system determines the workload based on the payment amount. It then prompts an LLM (Gemini 1.5 Flash) to generate the HTML/CSS/JS code for the requested app.
4.  **GitHub Deployment:** The generated code is automatically pushed to a new, unique repository created under a designated GitHub account ([sandvibe](https://github.com/sandvibe)).
5.  **Web Hosting:** The generated app (single `index.html` file) is hosted temporarily on the server running the installation.
6.  **Output:** 
    *   A QR code linking to the temporarily hosted web app is generated.
    *   The URL for the hosted app is displayed.
    *   The URL for the permanent GitHub repository is provided.
    *   (Future) A physical receipt is printed containing the QR code, URLs, and other details.

## Target Audience & Interaction

The installation invites participants to reflect on the value they assign to software, the implications of automated creative labor, and how economic factors can influence the ethical design of digital tools.

## LLM Context

This README provides context for an LLM involved in the project, particularly for the `app_generator.py` module. The LLM should understand:

*   **Goal:** Generate single-file HTML/CSS/JS web applications based on user requests.
*   **Input:** App description (e.g., "timer", "calculator".
*   **Output Format:** Complete, self-contained HTML file only. No extra text or markdown.

## Future Enhancements (See TODO.md)

*   Real Venmo email monitoring trigger.
*   Automatic GitHub repository creation via API.
*   Multi-iteration code generation/refinement (potentially using tools like `aider.chat`).
*   Physical receipt printing.
*   Deployment on a Raspberry Pi for the physical installation.

