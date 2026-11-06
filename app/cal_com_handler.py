import logging
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import Field

from app.models import WebhookProcessor

logger = logging.getLogger(__name__)


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
    PING = "PING"


class CalWebhookEvent(WebhookProcessor):
    trigger_event: CalTriggerEvent = Field(..., alias="triggerEvent")
    created_at: str = Field(..., alias="createdAt")
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is from Cal.com by looking for 'triggerEvent'."""
        if not isinstance(payload, dict):
            return False
        trigger_event = payload.get("triggerEvent")
        return (
            isinstance(trigger_event, str)
            and trigger_event in CalTriggerEvent.__members__
        )

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        if self.trigger_event == CalTriggerEvent.PING:
            self.enable_workflow = False
            logger.info("Disabling workflow for PING event.")
        else:
            self.enable_workflow = True
            payload_data = self.payload if isinstance(self.payload, dict) else {}
            title = payload_data.get("title") or "No Title"
            organizer_data = payload_data.get("organizer")
            if isinstance(organizer_data, dict):
                organizer = organizer_data.get("name") or "Unknown"
            else:
                organizer = "Unknown"

            self.sms_content = (
                f"Booking '{title}' ({self.trigger_event.value}) created by {organizer}"
            )


if __name__ == "__main__":
    sample_payload = {
        "triggerEvent": "BOOKING_CREATED",
        "createdAt": "2024-10-01T12:00:00Z",
        "payload": {
            "title": "Consultation Meeting",
            "organizer": {"name": "John Doe"},
        },
    }

    processor = CalWebhookEvent.model_validate(sample_payload)
    processor.process_workflow(sample_payload)
    print(f"SMS Content: {processor.sms_content}")
    sample_ping_payload = {
        "triggerEvent": "PING",
        "createdAt": "2025-11-22T14:40:26.232Z",
        "payload": {
            "type": "Test",
            "title": "Test trigger event",
            "startTime": "2025-11-22T14:40:26.232Z",
            "endTime": "2025-11-22T14:40:26.232Z",
            "attendees": [
                {
                    "email": "jdoe@example.com",
                    "name": "John Doe",
                    "timeZone": "Europe/London",
                    "language": {"locale": "en"},
                    "utcOffset": 0,
                }
            ],
            "organizer": {
                "name": "Cal",
                "email": "no-reply@cal.com",
                "timeZone": "Europe/London",
                "language": {"locale": "en"},
                "utcOffset": 0,
            },
        },
    }
    processor_ping = CalWebhookEvent.model_validate(sample_ping_payload)
    processor_ping.process_workflow(sample_ping_payload)
    print(f"SMS Content: {processor_ping.sms_content}")
