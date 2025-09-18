from pydantic import BaseModel, Field
from typing import Any, Dict
from enum import Enum

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

class CalWebhookEvent(BaseModel):
    trigger_event: CalTriggerEvent = Field(..., alias="triggerEvent")
    payload: Dict[str, Any]

    @staticmethod
    def output_message(event: "CalWebhookEvent") -> str:
        # Example: customize output using event data
        return f"Booking '{event.payload.get('title')}' created by {event.payload.get('organizer', {}).get('name')} at {event.created_at}"
