#!/usr/bin/env python3
"""
Gmail Watch Renewal Script

This script renews the Gmail watch for push notifications.
Gmail watches expire after 7 days (or less), so this must be run periodically.

Usage:
    # Set environment variables
    export GMAIL_SERVICE_ACCOUNT_KEY="<base64-encoded-service-account-json>"
    export GMAIL_USER_EMAIL="your-email@gmail.com"
    export GMAIL_PUBSUB_TOPIC="projects/YOUR_PROJECT/topics/gmail-webhook-notifications"

    # Run the script
    python app/utils/gmail/renew_gmail_watch.py

For GitHub Actions, the GMAIL_SERVICE_ACCOUNT_KEY should be stored as a secret.
"""

import base64
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailSettings(BaseSettings):
    """Gmail configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="GMAIL_",
        extra="ignore",
        env_file=Path(__file__).parent.parent.parent.parent / ".env",
    )

    service_account_key: Optional[str] = Field(
        default=None, description="Base64 encoded service account JSON"
    )
    user_email: str = Field(..., description="Gmail address to watch")
    pubsub_topic: str = Field(..., description="Pub/Sub topic for notifications")

    # OAuth2 settings (for personal Gmail)
    refresh_token: Optional[str] = Field(
        default=None, description="OAuth2 refresh token"
    )
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")


def get_credentials(settings: GmailSettings):
    """Get credentials for Gmail API (Service Account or OAuth2)."""
    # Try OAuth2 first (for personal Gmail accounts)
    if settings.refresh_token and settings.client_id and settings.client_secret:
        logger.info("Using OAuth2 credentials (personal Gmail account)")
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            None,  # No access token initially
            refresh_token=settings.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            scopes=SCOPES,
        )
        # Refresh to get an access token
        creds.refresh(Request())
        return creds

    # Fallback to Service Account (for Google Workspace with domain-wide delegation)
    if settings.service_account_key:
        logger.info("Using Service Account credentials (Google Workspace)")
        try:
            # Decode base64-encoded service account JSON
            service_account_json = base64.b64decode(
                settings.service_account_key
            ).decode("utf-8")
            service_account_info = json.loads(service_account_json)

            # Create credentials
            credentials = service_account.Credentials.from_service_account_info(
                service_account_info, scopes=SCOPES
            )
            return credentials
        except Exception as e:
            logger.error(f"Failed to load service account credentials: {e}")
            sys.exit(1)

    logger.error(
        "No valid credentials found. Set GMAIL_REFRESH_TOKEN (personal) or GMAIL_SERVICE_ACCOUNT_KEY (workspace)."  # noqa: E501
    )
    sys.exit(1)


def renew_gmail_watch():
    """Renew the Gmail watch for push notifications."""
    try:
        settings = GmailSettings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)

    logger.info(f"Renewing Gmail watch for: {settings.user_email}")
    logger.info(f"Using Pub/Sub topic: {settings.pubsub_topic}")

    try:
        # Get credentials
        credentials = get_credentials(settings)

        # Delegate credentials to the user email ONLY if using Service Account
        # (OAuth2 credentials are already tied to the user)
        if hasattr(credentials, "with_subject") and not settings.refresh_token:
            delegated_credentials = credentials.with_subject(settings.user_email)
            service = build("gmail", "v1", credentials=delegated_credentials)
        else:
            # For OAuth2, use credentials directly
            service = build("gmail", "v1", credentials=credentials)

        # Set up watch request
        request_body = {
            "labelIds": ["UNREAD"],  # Watch unread only
            "topicName": settings.pubsub_topic,
        }

        # Call the watch API
        watch_response = service.users().watch(userId="me", body=request_body).execute()

        # Log success
        history_id = watch_response.get("historyId")
        expiration = watch_response.get("expiration")

        logger.info("✅ Gmail watch renewed successfully!")
        logger.info(f"   History ID: {history_id}")

        # Convert expiration from milliseconds to readable format
        if expiration:
            expiration_timestamp = int(expiration) / 1000
            expiration_datetime = datetime.fromtimestamp(
                expiration_timestamp, tz=timezone.utc
            )
            logger.info(f"   Expires at: {expiration_datetime.isoformat()}")
            logger.info(
                f"   Time until expiration: ~{(expiration_timestamp - datetime.now(timezone.utc).timestamp()) / 86400:.1f} days"  # noqa: E501
            )

        return watch_response

    except Exception as e:
        logger.error(f"❌ Failed to renew Gmail watch: {e}")
        sys.exit(1)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Gmail Watch Renewal Script")
    logger.info("=" * 60)
    renew_gmail_watch()
    logger.info("=" * 60)
    logger.info("Renewal completed successfully!")
    logger.info("=" * 60)
