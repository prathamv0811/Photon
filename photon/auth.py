"""
Authentication utilities for LeRobot
"""

import subprocess
import typer
import os
import json
from rich.prompt import Confirm
from photon.config import CONFIG_PATH


def get_stored_credentials() -> tuple[str, str]:
    """
    Get stored HuggingFace username from config.json.
    Returns: (username, token) - token is always empty string as we use HF's token storage
    """
    username = ""
    
    # Try to get username from config.json
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                hf_config = config.get('hugging_face', {})
                username = hf_config.get('username', '')
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    
    return username, ""


def save_username_to_config(username: str) -> None:
    """
    Save HuggingFace username to config.json for future reference.
    """
    try:
        config = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
        
        if 'hugging_face' not in config:
            config['hugging_face'] = {}
        
        config['hugging_face']['username'] = username
        
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        typer.echo(f"⚠️  Warning: Could not save username to config: {e}")


def check_huggingface_login() -> tuple[bool, str]:
    """
    Check if user is logged in to HuggingFace and return (is_logged_in, username)
    Uses the HuggingFace Hub API for reliable username retrieval.
    """
    try:
        from huggingface_hub import whoami, HfFolder
        
        # Get the token from HuggingFace's storage
        token = HfFolder.get_token()
        
        if not token:
            return False, ""
        
        # Use the whoami API to get user info
        user_info = whoami(token)
        username = user_info.get('name', '')
        
        if username:
            return True, username
        else:
            return False, ""
            
    except ImportError:
        typer.echo("❌ huggingface_hub not found. Please install with: pip install huggingface_hub")
        return False, ""
    except Exception:
        # If API fails, user is not logged in or token is invalid
        return False, ""


def authenticate_huggingface() -> tuple[bool, str]:
    """
    Handle HuggingFace authentication flow.
    Returns: (success, username)
    """
    # Check if already logged in
    is_logged_in, username = check_huggingface_login()
    
    if is_logged_in:
        typer.echo(f"✅ Already logged in to HuggingFace as: {username}")
        # Save username to config for future reference
        save_username_to_config(username)
        return True, username
    
    # Check if we have a stored username (even though not logged in)
    stored_username, _ = get_stored_credentials()
    
    # Prompt for login
    typer.echo("🔐 You need to log in to HuggingFace.")
    should_login = Confirm.ask("Would you like to log in now?", default=True)
    
    if not should_login:
        typer.echo("❌ HuggingFace login required.")
        return False, ""
    
    # Perform interactive login
    try:
        typer.echo("Please enter your HuggingFace token when prompted.")
        
        result = subprocess.run(["huggingface-cli", "login"], check=False)
        
        if result.returncode == 0:
            # Check login status again using API
            is_logged_in, username = check_huggingface_login()
            if is_logged_in:
                typer.echo(f"✅ Successfully logged in as: {username}")
                # Save username to config for future reference
                save_username_to_config(username)
                return True, username
            else:
                typer.echo("❌ Login appeared successful but unable to verify username.")
                # If we have a stored username, use it as fallback
                if stored_username:
                    typer.echo(f"ℹ️  Using stored username: {stored_username}")
                    return True, stored_username
                return False, ""
        else:
            typer.echo("❌ Login failed.")
            return False, ""
            
    except FileNotFoundError:
        typer.echo("❌ huggingface-cli not found. Please install with: pip install huggingface_hub[cli]")
        return False, ""
    except Exception as e:
        typer.echo(f"❌ Error during login: {e}")
        return False, ""
