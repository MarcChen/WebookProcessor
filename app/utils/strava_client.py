"""
Minimal Strava API client with OAuth authentication and token management.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class StravaSettings(BaseSettings):
    """Configuration settings for Strava API client loaded from .env file."""

    client_id: str = Field(..., description="Strava API Client ID")
    client_secret: SecretStr = Field(..., description="Strava API Client Secret")

    # Optional: initial tokens (can be omitted if doing fresh auth)
    access_token: Optional[SecretStr] = Field(default=None)
    refresh_token: Optional[SecretStr] = Field(default=None)
    expires_in: Optional[int] = Field(default=None)
    expires_at: Optional[int] = Field(default=None)

    # API endpoints
    token_url: str = "https://www.strava.com/oauth/token"
    auth_base_url: str = "https://www.strava.com/oauth/authorize"

    # File paths
    token_file: Path = Path(__file__).parent.parent.parent / "strava_tokens.json"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_prefix="STRAVA_",
        extra="ignore",
    )

    def model_post_init(self, __context: Any) -> None:
        """Create necessary files if they don't exist."""
        # Create token file if it doesn't exist
        token_path = self.token_file
        # Only dump selected fields to token file if it doesn't exist
        if not token_path.exists():
            token_data = {
                "token_type": "Bearer",
                "access_token": str(self.access_token.get_secret_value()),
                "expires_at": self.expires_at,
                "expires_in": self.expires_in,
                "refresh_token": str(self.refresh_token.get_secret_value()),
            }
            token_path.write_text(json.dumps(token_data))


class TokenData(BaseModel):
    """Model for storing Strava API token data."""

    access_token: str
    refresh_token: str
    expires_at: int
    token_type: str = "Bearer"

    @classmethod
    def from_json(cls, data: dict):
        """Create TokenData from API response."""
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if access token is expired (with 5min buffer)."""
        return time.time() >= (self.expires_at - 300)


class StravaAuth:
    """Handles Strava OAuth2 authentication and token management."""

    def __init__(self, settings: StravaSettings):
        self.settings = settings
        self.token_data: Optional[TokenData] = None
        self._load_tokens()

    def _load_tokens(self) -> bool:
        """Load tokens from file if it exists."""
        if self.settings.token_file.exists():
            with open(self.settings.token_file, "r") as f:
                data = json.load(f)
            self.token_data = TokenData.from_json(data)
            return True
        return False

    def _save_tokens(self, token_data: dict) -> None:
        """Save tokens to file and update instance."""
        self.settings.token_file.write_text(json.dumps(token_data, indent=2))
        self.token_data = TokenData.from_json(token_data)

    def get_access_token(self) -> str:
        """Get valid access token, refreshing if necessary."""
        if not self.token_data or self.token_data.is_expired():
            if self.token_data and self.token_data.refresh_token:
                self.refresh_access_token()
            else:
                self.perform_initial_auth()

        return self.token_data.access_token

    def perform_initial_auth(self) -> None:
        """Perform initial OAuth authorization flow."""
        # Build authorization URL
        auth_url = (
            f"{self.settings.auth_base_url}?"
            f"client_id={self.settings.client_id}&"
            "response_type=code&"
            "redirect_uri=http://localhost/exchange_token&"
            "scope=activity:read_all"
        )

        print(f"\n🔗 Open this URL in your browser:\n{auth_url}\n")
        redirect_url = input("📋 Paste the redirect URL you were sent to: ")

        # Extract authorization code
        parsed = urlparse(redirect_url)
        code = parse_qs(parsed.query).get("code")

        if not code:
            raise ValueError("No authorization code found in URL")

        # Exchange code for tokens
        response = requests.post(
            self.settings.token_url,
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret.get_secret_value(),
                "code": code[0],
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        self._save_tokens(response.json())
        logger.info("✅ Initial authentication successful")

    def refresh_access_token(self) -> None:
        """Refresh access token using refresh token."""
        if not self.token_data or not self.token_data.refresh_token:
            raise ValueError("No refresh token available")

        logger.info("🔄 Refreshing access token...")
        response = requests.post(
            self.settings.token_url,
            data={
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret.get_secret_value(),
                "grant_type": "refresh_token",
                "refresh_token": self.token_data.refresh_token,
            },
        )
        response.raise_for_status()
        self._save_tokens(response.json())
        logger.info("✅ Token refreshed successfully")


class StravaClient:
    """Main Strava API client."""

    def __init__(self):
        self.settings = StravaSettings()
        self.auth = StravaAuth(self.settings)
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        """Get authorization headers with valid token."""
        token = self.auth.get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def get_activity(self, activity_id: int) -> dict:
        """Get activity details by ID."""
        response = self.session.get(
            f"https://www.strava.com/api/v3/activities/{activity_id}",
            headers=self._get_headers(),
        )
        response.raise_for_status()
        return response.json()

    def is_virtual_ride(self, activity_id: int) -> bool:
        """Check if activity is a VirtualRide."""
        activity = self.get_activity(activity_id)
        return activity.get("type") == "VirtualRide"

    def get_activities(self, per_page: int = 30, page: int = 1) -> list[dict]:
        """Get list of athlete activities."""
        response = self.session.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=self._get_headers(),
            params={"per_page": per_page, "page": page},
        )
        response.raise_for_status()
        return response.json()


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Create client (automatically handles auth)
    client = StravaClient()

    # Get recent activities
    activities = client.get_activities(per_page=10)
    for activity in activities:
        print(f"{activity['name']} - {activity['type']}, ID: {activity['id']}")

    # Check if specific activity is virtual ride
    activity_ids_to_check = [
        16469147497,  # Basket en soirée - Workout
        16457839651,  # Entraînement aux poids en soirée - WeightTraining
        16448104498,  # MyWhoosh - The Seven Gems - VirtualRide
        16439586008,  # Entraînement de nuit - Workout
    ]
    print(client.get_activity(16457839651))

    for activity_id in activity_ids_to_check:
        try:
            if client.is_virtual_ride(activity_id):
                print(f"✅ Activity {activity_id} is a VirtualRide")
            else:
                print(f"❌ Activity {activity_id} is NOT a VirtualRide")
        except Exception as e:
            print(f"Could not check activity {activity_id}: {e}")
