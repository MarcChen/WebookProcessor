from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models import (
    GitHubSettings,
    WebhookProcessor,
    create_github_settings,
)
from app.utils.strava_client import StravaClient


class StravaObjectType(str, Enum):
    ACTIVITY = "activity"
    ATHLETE = "athlete"


class StravaAspectType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class StravaVerification(BaseModel):
    hub_mode: str = Field(..., alias="hub.mode")
    hub_challenge: str = Field(..., alias="hub.challenge")
    hub_verify_token: str = Field(..., alias="hub.verify_token")


class StravaWebhookProcessor(WebhookProcessor):
    """Processor for Strava webhooks."""

    object_type: StravaObjectType
    object_id: int
    aspect_type: StravaAspectType
    updates: Optional[Dict[str, Any]] = None
    owner_id: int
    subscription_id: int
    event_time: int

    github_settings: GitHubSettings = Field(
        default_factory=lambda: create_github_settings(env_prefix="STRAVA_")(),
        exclude=True,
    )

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is from Strava and matches the expected model."""
        try:
            cls.model_validate(payload)
            return True
        except Exception:
            return False

    @classmethod
    def handle_verification(cls, query_params: Dict[str, Any]) -> Any | None:
        """Handle Strava webhook subscription verification."""
        try:
            verification = StravaVerification.model_validate(query_params)
            if (
                verification.hub_mode == "subscribe"
                and verification.hub_verify_token == "STRAVA"
            ):
                return {"hub.challenge": verification.hub_challenge}
        except Exception:
            return None
        return None

    def define_sms_content(self) -> None:
        """Generate an SMS message from a Strava webhook event."""
        if (
            self.object_type == StravaObjectType.ACTIVITY
            and self.aspect_type == StravaAspectType.CREATE
        ):
            client = StravaClient()
            is_virtual = client.is_virtual_ride(self.object_id)
            if is_virtual:
                activity = client.get_activity(self.object_id)
                self.sms_content = f"New activity virtual ride: {activity['name']}, "
            else:
                self.enable_workflow = False
        else:
            self.enable_workflow = False


if __name__ == "__main__":
    sample_payload = {
        "object_type": "activity",
        "object_id": 123456789,
        "aspect_type": "create",
        "owner_id": 987654321,
        "subscription_id": 111222333,
        "event_time": 1617181920,
    }
    import os

    os.environ["STRAVA_GITHUB_TOKEN"] = "your_github_token"
    os.environ["STRAVA_GITHUB_REPO"] = "your_repo"
    os.environ["STRAVA_GITHUB_WORKFLOW_ID"] = "your_workflow_id"
    os.environ["STRAVA_GITHUB_REF"] = "main"
    os.environ["STRAVA_GITHUB_INPUTS"] = "{}"

    processor = StravaWebhookProcessor.model_validate({"event": sample_payload})
    processor.define_sms_content()
    print(processor.sms_content)
