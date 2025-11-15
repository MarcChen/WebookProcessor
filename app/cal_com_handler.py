from enum import Enum
from typing import Any, Dict

from pydantic import Field

from .models import WebhookProcessor, register_processor


class CalTriggerEvent(str, Enum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    MEETING_ENDED = "MEETING_ENDED"
    BOOKING_REJECTED = "BOOKING_REJECTED"
    BOOKING_REQUESTED = "BOOKING_REQUESTED"
    BOOKING_PAYMENT_INITIATED = "BOOKING_PAYMENT_INITIATED"
    BOOKING_PAID = "BOOKING_PAID"
    MEETING_STARTED = "MEETING_STARTED"
    RECORDING_READY = "RECORDING_READY"
    FORM_SUBMITTED = "FORM_SUBMITTED"


@register_processor
class CalWebhookEvent(WebhookProcessor):
    trigger_event: CalTriggerEvent = Field(..., alias="triggerEvent")
    created_at: str = Field(..., alias="createdAt")
    payload: Dict[str, Any]

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is from Cal.com by looking for 'triggerEvent'."""
        return (
            "triggerEvent" in payload
            and payload["triggerEvent"] in CalTriggerEvent.__members__
        )

    def get_sms_message(self) -> str:
        """Formats the SMS message for a Cal.com event."""
        title = self.payload.get("title", "No Title")
        organizer = self.payload.get("organizer", {}).get("name", "Unknown")
        return f"Booking '{title}' ({self.trigger_event.value}) created by {organizer}"
