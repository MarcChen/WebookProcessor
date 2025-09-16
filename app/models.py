from pydantic import BaseModel, Field
from typing import Any, Dict

class WebhookEvent(BaseModel):
    trigger_event: str = Field(..., alias="triggerEvent")
    created_at: str = Field(..., alias="createdAt")
    message: str

    @staticmethod
    def output_message(event: "WebhookEvent") -> str:
        # Default implementation, override in subclasses
        pass

class CalWebhookEvent(WebhookEvent):
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