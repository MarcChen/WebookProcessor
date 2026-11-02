import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models import (
    GitHubSettings,
    WebhookProcessor,
    create_github_settings,
)

logger = logging.getLogger(__name__)


class IntervalsEvent(BaseModel):
    athlete_id: Optional[str] = None
    type: str  # e.g. "ACTIVITY_UPLOADED", "ACTIVITY_ANALYZED"
    id: Optional[str] = None
    start_date_local: Optional[str] = None
    activity: Optional[Dict[str, Any]] = None

    model_config = {"extra": "allow"}


class IntervalsPayload(BaseModel):
    secret: Optional[str] = None
    events: List[IntervalsEvent] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class IntervalsWebhookProcessor(WebhookProcessor):
    """Processor for Intervals.icu activity upload webhooks."""

    secret: Optional[str] = None
    events: List[IntervalsEvent] = Field(default_factory=list)

    github_settings: GitHubSettings = Field(
        default_factory=lambda: create_github_settings(env_prefix="INTERVALS_")(),
        exclude=True,
    )

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if payload matches Intervals.icu webhook format."""
        if not isinstance(payload, dict):
            return False
        # Intervals webhooks contain an "events" list
        if "events" not in payload or not isinstance(payload["events"], list):
            return False
        try:
            parsed = cls.model_validate(payload)
            # Verify secret if configured in environment
            configured_secret = os.getenv("INTERVALS_WEBHOOK_SECRET")
            if configured_secret and parsed.secret != configured_secret:
                logger.warning("Intervals webhook secret mismatch.")
                return False
            return len(parsed.events) > 0
        except Exception:
            return False

    @classmethod
    def handle_verification(cls, query_params: Dict[str, Any]) -> Any | None:
        """Handle any challenge verification if requested."""
        if "challenge" in query_params:
            return {"challenge": query_params["challenge"]}
        return None

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        """Process incoming events and determine if workflow should trigger."""
        upload_events = [
            e
            for e in self.events
            if e.type in ("ACTIVITY_UPLOADED", "ACTIVITY_ANALYZED")
        ]

        if not upload_events:
            logger.info("No activity upload events found in Intervals.icu payload.")
            self.enable_workflow = False
            return

        # Take the most relevant event
        event = upload_events[0]
        activity_id = event.id
        if not activity_id and event.activity:
            activity_id = event.activity.get("id")

        activity_name = None
        if event.activity:
            activity_name = event.activity.get("name")

        self.enable_workflow = True

        # Pass activity_id to GitHub workflow inputs
        if activity_id:
            self.github_settings.inputs = {"activity_id": str(activity_id)}
            name_suffix = f" ({activity_name})" if activity_name else ""
            self.sms_content = (
                f"New activity on Intervals.icu: {activity_id}{name_suffix}"
            )
        else:
            self.github_settings.inputs = {}
            self.sms_content = "New activity uploaded to Intervals.icu"

        logger.info(
            "Intervals.icu workflow enabled for activity %s. Inputs: %s",
            activity_id,
            self.github_settings.inputs,
        )
