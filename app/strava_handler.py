from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models import GitHubSettings, WebhookProcessor, register_processor
from app.utils.strava_client import StravaClient


class StravaObjectType(str, Enum):
    ACTIVITY = "activity"
    ATHLETE = "athlete"


class StravaAspectType(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class StravaWebhookEvent(BaseModel):
    object_type: StravaObjectType
    object_id: int
    aspect_type: StravaAspectType
    updates: Optional[Dict[str, Any]] = None
    owner_id: int
    subscription_id: int
    event_time: int


class StravaVerification(BaseModel):
    hub_mode: str = Field(..., alias="hub.mode")
    hub_challenge: str = Field(..., alias="hub.challenge")
    hub_verify_token: str = Field(..., alias="hub.verify_token")


@register_processor
class StravaWebhookProcessor(WebhookProcessor):
    """Processor for Strava webhooks."""

    event: StravaWebhookEvent
    github_settings = GitHubSettings(env_prefix="STRAVA_")

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is from Strava and matches the expected model."""
        try:
            StravaWebhookEvent(**payload)
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
            self.event.object_type == StravaObjectType.ACTIVITY
            and self.event.aspect_type == StravaAspectType.CREATE
        ):
            client = StravaClient()
            is_virtual = client.is_virtual_ride(self.event.object_id)
            if is_virtual:
                activity = client.get_activity(self.event.object_id)
                self.sms_content = f"New activity virtual ride: {activity['name']}, "
            else:
                self.enable_workflow = False
