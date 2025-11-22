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

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        if (
            self.object_type == StravaObjectType.ACTIVITY
            and self.aspect_type == StravaAspectType.CREATE
        ):
            client = StravaClient()
            is_virtual = client.is_virtual_ride(self.object_id)
            if not is_virtual:
                self.enable_workflow = False
            else:
                self.enable_workflow = True
                activity = client.get_activity(self.object_id)
                self.sms_content = f"New activity virtual ride: {activity['name']}, "
        else:
            self.enable_workflow = False


if __name__ == "__main__":
    sample_update_payload = {
        "aspect_type": "update",
        "event_time": 1763821976,
        "object_id": 16457839651,
        "object_type": "activity",
        "owner_id": 142429376,
        "subscription_id": 315652,
        "updates": {"private": "true", "visibility": "only_me"},
    }
    strava_create_payload = {
        "aspect_type": "create",
        "event_time": 1763662369,
        "object_id": 16517081124,
        "object_type": "activity",
        "owner_id": 142429376,
        "subscription_id": 315652,
        "updates": {},
    }

    processor = StravaWebhookProcessor.model_validate(sample_update_payload)
    response = processor.process_workflow(sample_update_payload)
    print(response)
    print(f"SMS Content: {processor.sms_content}")

    processor = StravaWebhookProcessor.model_validate(strava_create_payload)
    response = processor.process_workflow(strava_create_payload)
    print(response)
    print(f"SMS Content: {processor.sms_content}")
