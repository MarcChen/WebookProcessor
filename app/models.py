from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Type

from pydantic import BaseModel, Field


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
    created_at: str = Field(..., alias="createdAt")
    payload: Dict[str, Any]

    @staticmethod
    def output_message(event: "CalWebhookEvent") -> str:
        title = event.payload.get("title", "No Title")
        trigger = event.trigger_event
        organizer = event.payload.get("organizer", {}).get("name", "Unknown")
        return f"Booking '{title}' ({trigger}) created by {organizer}"


class WebhookProcessor(ABC, BaseModel):
    """Abstract base class for all webhook processors."""

    @classmethod
    @abstractmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if this processor can handle the given payload."""
        raise NotImplementedError

    @abstractmethod
    def get_sms_message(self) -> str:
        """Process the payload and return the message to be sent."""
        raise NotImplementedError


# A registry to hold all our webhook processor classes
WEBHOOK_PROCESSORS: list[Type[WebhookProcessor]] = []


def register_processor(cls: Type[WebhookProcessor]) -> Type[WebhookProcessor]:
    """A decorator to register new webhook processor classes."""
    WEBHOOK_PROCESSORS.append(cls)
    return cls
