#!/usr/bin/env python3.11
"""
GitHub integration service for Vibe Coder application.
This module handles repository creation and code pushing.
"""
import os
import time
import subprocess
import shutil
import logging
import requests
from typing import Dict, Optional, Any

# Import configuration
from src.config import GITHUB_CONFIG, GITHUB_PAT

# Import error handling
from src.error_handling import (
    GitHubError, 
    ErrorCodes, 
    exception_handler, 
    log_and_raise
)

# Set up logging
logger = logging.getLogger("github_service")

class GitHubService:
    """Service class for handling GitHub repository operations."""
    
    def __init__(self, github_pat=None, username=None):
        """
        Initialize GitHub service with credentials.
        
        Args:
            github_pat: GitHub Personal Access Token (defaults to env variable)
            username: GitHub username (defaults to config)
        """
        self.github_pat = github_pat or GITHUB_PAT
        self.username = username or GITHUB_CONFIG["username"]
        self.repo_prefix = GITHUB_CONFIG["repo_prefix"]
        
        # Log warning if PAT not set
        if not self.github_pat:
            logger.warning("GitHub PAT not set. GitHub integration will likely fail.")
    
    @exception_handler
    def create_repository(self, repo_name: str) -> bool:
        """
        Create a new GitHub repository using GitHub API.
        
        Args:
            repo_name: Name of the repository to create
            
        Returns:
            True if creation successful or repo already exists, False otherwise
            
        Raises:
            GitHubError: If repository creation fails
        """
        if not self.github_pat:
            log_and_raise(
                GitHubError, 
                "GitHub Personal Access Token not set", 
                code=ErrorCodes.GITHUB_AUTHENTICATION_ERROR
            )
            
        # Log creation attempt
        logger.info(f"Creating repository: {repo_name} for user: {self.username}")
        
        # Set up the authorization headers
        headers = {
            "Authorization": f"token {self.github_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Repository data
        data = {
            "name": repo_name,
            "description": GITHUB_CONFIG["description_template"].format(timestamp=time.strftime('%Y-%m-%d')),
            "private": False,
            "auto_init": False,  # Don't initialize with README
            "has_issues": True,
            "has_projects": False,
            "has_wiki": False
        }
        
        try:
            # Create repository using GitHub API
            response = requests.post(GITHUB_CONFIG["create_repo_api"], headers=headers, json=data)
            
            # Check response
            if response.status_code == 201:
                logger.info(f"Successfully created repository: {repo_name}")
                logger.info(f"Repository URL: https://github.com/{self.username}/{repo_name}")
                return True
            
            # If there's a 422 error, the repo might already exist
            if response.status_code == 422 and "already exists" in response.text:
                logger.info(f"Repository already exists, will attempt to push anyway.")
                return True
                
            # Handle other error cases
            error_details = {
                'status_code': response.status_code,
                'response': response.text,
                'repo_name': repo_name
            }
            
            log_and_raise(
                GitHubError,
                f"Failed to create repository: {repo_name}. Status code: {response.status_code}",
                code=ErrorCodes.GITHUB_REPO_CREATION_ERROR,
                details=error_details
            )
            
        except requests.RequestException as e:
            log_and_raise(
                GitHubError,
                f"GitHub API error during repository creation: {str(e)}",
                code=ErrorCodes.GITHUB_API_ERROR,
                details={'repo_name': repo_name},
                original_exception=e
            )
    
    @exception_handler
    def push_to_github(self, app_path: str, app_id: str, app_type: str) -> str:
        """
        Push the generated app code to a GitHub repository.
        
        Args:
            app_path: Local path to the app code
            app_id: Unique ID for the app
            app_type: Type of app being pushed
            
        Returns:
            Repository URL if successful, error message otherwise
            
        Raises:
            GitHubError: If GitHub operations fail
        """
        if not self.github_pat:
            return "https://github.com/error/pat-not-set"
            
        # Generate repository name from app_id
        repo_name = f"{self.repo_prefix}{app_id}"
        repo_url = f"https://github.com/{self.username}/{repo_name}"
        git_url = f"{repo_url}.git"
        
        # Use PAT for authentication in the URL
        authenticated_repo_url = f"https://{self.username}:{self.github_pat}@github.com/{self.username}/{repo_name}.git"
        commit_message = f"Add {app_type} app ({app_id}) generated by Vibe Coder"
        
        logger.info(f"Attempting to push code from {app_path} to {repo_url}")
        logger.info(f"Using account: {self.username}")
        
        # First create the repository
        try:
            repo_created = self.create_repository(repo_name)
        except GitHubError as e:
            logger.warning(f"Could not create repository {repo_name}. Will attempt to push anyway: {e.message}")
            # Continue with the push attempt even if repo creation failed
        
        git_dir = os.path.join(app_path, ".git")
        
        try:
            # Check if git is initialized, if so, remove .git dir to avoid nesting issues
            if os.path.exists(git_dir):
                logger.info("Removing existing .git directory.")
                shutil.rmtree(git_dir)
                time.sleep(0.5)  # Small delay to ensure directory is removed
                
            # Initialize git repo
            logger.info("Initializing git repository...")
            try:
                subprocess.run(["git", "init"], cwd=app_path, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                log_and_raise(
                    GitHubError,
                    "Failed to initialize git repository",
                    code=ErrorCodes.GIT_COMMAND_ERROR,
                    details={'command': 'git init', 'stdout': e.stdout, 'stderr': e.stderr},
                    original_exception=e
                )
            
            # Configure git user (temporary for this repo)
            subprocess.run(["git", "config", "user.name", "Vibe Coder Bot"], cwd=app_path, check=True)
            subprocess.run(["git", "config", "user.email", "noreply@vibe.coder"], cwd=app_path, check=True)
            
            # Add files
            logger.info("Adding files...")
            try:
                subprocess.run(["git", "add", "."], cwd=app_path, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                log_and_raise(
                    GitHubError,
                    "Failed to add files to git repository",
                    code=ErrorCodes.GIT_COMMAND_ERROR,
                    details={'command': 'git add .', 'stdout': e.stdout, 'stderr': e.stderr},
                    original_exception=e
                )
            
            # Commit
            logger.info("Committing files...")
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message], 
                cwd=app_path, 
                check=False, 
                capture_output=True, 
                text=True
            )
            
            if commit_result.returncode != 0:
                if "nothing to commit" in commit_result.stdout.lower() or "nothing to commit" in commit_result.stderr.lower():
                    logger.info("Nothing to commit. Adding empty README to force commit.")
                    with open(os.path.join(app_path, "README.md"), "a") as f:
                        f.write("\n\nGenerated at: " + time.strftime("%Y-%m-%d %H:%M:%S"))
                    
                    subprocess.run(["git", "add", "README.md"], cwd=app_path, check=True, capture_output=True, text=True)
                    
                    commit_retry = subprocess.run(
                        ["git", "commit", "-m", commit_message], 
                        cwd=app_path, 
                        check=False, 
                        capture_output=True, 
                        text=True
                    )
                    
                    if commit_retry.returncode != 0:
                        log_and_raise(
                            GitHubError,
                            "Failed to commit files, even after adding README update",
                            code=ErrorCodes.GIT_COMMAND_ERROR,
                            details={
                                'command': 'git commit', 
                                'stdout': commit_retry.stdout, 
                                'stderr': commit_retry.stderr
                            }
                        )
                else:
                    log_and_raise(
                        GitHubError,
                        "Failed to commit files to git repository",
                        code=ErrorCodes.GIT_COMMAND_ERROR,
                        details={
                            'command': 'git commit', 
                            'stdout': commit_result.stdout, 
                            'stderr': commit_result.stderr
                        }
                    )
                    
            # Rename branch to main
            subprocess.run(["git", "branch", "-M", "main"], cwd=app_path, check=True, capture_output=True, text=True)
            
            # Add remote origin
            logger.info(f"Adding remote origin: {git_url}")
            # Remove existing remote origin if it exists to avoid error
            subprocess.run(["git", "remote", "remove", "origin"], cwd=app_path, check=False, capture_output=True, text=True)
            
            try:
                subprocess.run(
                    ["git", "remote", "add", "origin", authenticated_repo_url], 
                    cwd=app_path, 
                    check=True, 
                    capture_output=True, 
                    text=True
                )
            except subprocess.CalledProcessError as e:
                log_and_raise(
                    GitHubError,
                    "Failed to add remote origin",
                    code=ErrorCodes.GIT_COMMAND_ERROR,
                    details={'command': 'git remote add origin', 'stderr': e.stderr},
                    original_exception=e
                )
            
            # Push to GitHub
            logger.info("Pushing to GitHub...")
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", "main"], 
                cwd=app_path, 
                check=False, 
                capture_output=True, 
                text=True
            )
            
            if push_result.returncode != 0:
                if "repository not found" in push_result.stderr.lower():
                    logger.error(f"Repository {repo_url} not found. Please verify the GitHub account and token.")
                    return f"{repo_url} (Repo not found - please verify account permissions)"
                elif "permission to" in push_result.stderr.lower() and "denied" in push_result.stderr.lower():
                    logger.error(f"Permission denied. Please verify the GitHub token has correct permissions.")
                    return f"{repo_url} (Permission denied - check token permissions)"
                else:
                    log_and_raise(
                        GitHubError,
                        "Failed to push to GitHub",
                        code=ErrorCodes.GIT_COMMAND_ERROR,
                        details={
                            'command': 'git push', 
                            'stdout': push_result.stdout, 
                            'stderr': push_result.stderr
                        }
                    )
            
            logger.info(f"Successfully pushed {app_id} to {repo_url}")
            return repo_url
            
        except FileNotFoundError as e:
            logger.error("Git command not found. Ensure git is installed and in PATH.")
            return f"{repo_url} (Error: git command not found)"
            
        except GitHubError:
            # Re-raise GitHub errors from our error handling
            raise
            
        except Exception as e:
            # Convert any other exceptions to our standard format
            logger.error(f"Unexpected error during GitHub push: {str(e)}")
            return f"{repo_url} (Error: {str(e)[:50]})"
            
        finally:
            # Clean up .git directory after push to prevent issues if run again in same dir
            if os.path.exists(git_dir):
                try:
                    shutil.rmtree(git_dir)
                    logger.info("Cleaned up .git directory.")
                except Exception as e:
                    logger.warning(f"Failed to clean up .git directory: {e}")
                    
    def test_connection(self) -> Dict:
        """
        Test GitHub API connection and token validity.
        
        Returns:
            Dict with connection status and error message if any
        """
        if not self.github_pat:
            return {
                "status": "error",
                "message": "GitHub PAT not set"
            }
            
        try:
            # Check the user endpoint to test authentication
            headers = {
                "Authorization": f"token {self.github_pat}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            response = requests.get("https://api.github.com/user", headers=headers)
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "ok",
                    "username": user_data.get("login"),
                    "repos_url": user_data.get("repos_url"),
                    "rate_limit": response.headers.get("X-RateLimit-Remaining")
                }
            else:
                return {
                    "status": "error",
                    "message": f"API connection failed with status {response.status_code}",
                    "details": response.json()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": f"Connection test failed: {str(e)}"
            }

# Create singleton instance for app-wide use
github_service = GitHubService()