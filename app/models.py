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

class WebhookEvent(BaseModel):
    trigger_event: str = Field(..., alias="triggerEvent")
    created_at: str = Field(..., alias="createdAt")
    message: str

    @staticmethod
    def output_message(event: "WebhookEvent") -> str:
        # Default implementation, override in subclasses
        pass

class CalWebhookEvent(WebhookEvent):
    trigger_event: CalTriggerEvent = Field(..., alias="triggerEvent")
    payload: Dict[str, Any]

    @staticmethod
    def output_message(event: "CalWebhookEvent") -> str:
        # Example: customize output using event data
        return f"Booking '{event.payload.get('title')}' created by {event.payload.get('organizer', {}).get('name')} at {event.created_at}"

class DummyWebhookEvent(WebhookEvent):
    payload: Dict[str, Any]

    @staticmethod
    def output_message(event: "DummyWebhookEvent") -> str:
        return f"Dummy event triggered: {event.trigger_event} at {event.created_at} with message '{event.message}'"