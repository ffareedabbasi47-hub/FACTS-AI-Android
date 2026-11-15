#!/usr/bin/env python3
"""
FACTS AI - Standalone One-Time OAuth Setup Tool
===============================================
Authorizes your YouTube channel using Google's OAuth 2.0 flow.
Strictly requests the minimum required permission: 'https://www.googleapis.com/auth/youtube.upload'.

Run this script ONCE interactively on your desktop computer:
    python setup_oauth.py --secrets client_secrets.json

It generates the standard JSON credentials payload and prints a base64-encoded string
to be safely added to your GitHub Repository Secrets as: YOUTUBE_TOKEN_JSON
"""

import os
import sys
import json
import argparse
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

# STRICT LEAST-PRIVILEGE SCOPE: Upload access only
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def mask_string(s: str, show_start: int = 4, show_end: int = 4) -> str:
    """Masks sensitive strings for safe terminal display."""
    if not s or len(s) <= (show_start + show_end):
        return "***"
    return f"{s[:show_start]}...{s[-show_end:]}"

def main():
    parser = argparse.ArgumentParser(description="Authorize YouTube Channel for FACTS AI")
    parser.add_argument(
        "--secrets",
        type=str,
        default="client_secrets.json",
        help="Path to the client_secrets.json file downloaded from Google Cloud Console"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="youtube_credentials.json",
        help="Local file path to save authorized user credentials"
    )
    args = parser.parse_args()

    secrets_path = Path(args.secrets)
    if not secrets_path.exists():
        print(f"\n[ERROR] Client secrets file not found: {secrets_path.resolve()}")
        print("Please download your OAuth 2.0 Desktop Client JSON from Google Cloud Console,")
        print("rename it to 'client_secrets.json', and place it in this directory.\n")
        sys.exit(1)

    print("\n=======================================================")
    print("  FACTS AI - YouTube Channel Authorization (One-Time)  ")
    print("=======================================================")
    print(f"Requesting Scope : {SCOPES[0]}")
    print("Launching browser for interactive authorization...")
    print("Please log in with the YouTube channel owner's Google account.\n")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    except Exception as e:
        print(f"\n[ERROR] Authorization failed: {e}")
        sys.exit(1)

    if not creds.refresh_token:
        print("\n[WARNING] No refresh token returned by Google.")
        print("This usually happens if access was already granted. Try removing application access at:")
        print("https://myaccount.google.com/permissions and run this script again with prompt='consent'.\n")

    # Serialize credentials to standard authorized_user JSON
    creds_data = json.loads(creds.to_json())
    
    # Save local JSON file with restricted permissions (0600)
    output_path = Path(args.output)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(str(output_path), flags, mode)
        with open(fd, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)
    except Exception:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)

    client_id_masked = mask_string(creds_data.get("client_id", ""))
    refresh_token_masked = mask_string(creds_data.get("refresh_token", ""))

    print("\n[SUCCESS] Channel authorization successful!")
    print(f"Credentials saved locally to : {output_path.resolve()}")
    print("Permissions set to            : 0600 (owner read/write only)")
    print(f"Client ID                     : {client_id_masked}")
    print(f"Refresh Token Captured        : {refresh_token_masked}")
    print("\n-------------------------------------------------------")
    print("NEXT STEP FOR GITHUB ACTIONS CI/CD:")
    print("1. Go to your GitHub Repository -> Settings -> Secrets and variables -> Actions")
    print("2. Click 'New repository secret'")
    print("3. Name: YOUTUBE_TOKEN_JSON")
    print(f"4. Value: Copy the entire contents of '{output_path.name}' and paste it there.")
    print("   Or via GitHub CLI:")
    print(f"   gh secret set YOUTUBE_TOKEN_JSON < {output_path.name}")
    print("-------------------------------------------------------\n")

if __name__ == "__main__":
    main()
