import hmac
import logging
import os
from typing import Any, Dict

from pydantic import Field

from app.models import WebhookProcessor

logger = logging.getLogger(__name__)


class SimpleWebhookProcessor(WebhookProcessor):
    """Processor for Simple SMS triggers."""

    type: str = Field(..., pattern="^simple$")
    message: str
    token: str = Field(..., exclude=True)

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is a simple trigger."""
        if not isinstance(payload, dict):
            return False
        return payload.get("type") == "simple"

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        """Validate token and set SMS content."""
        expected_token = os.getenv("SIMPLE_TRIGGER_TOKEN")

        if not expected_token:
            logger.error("SIMPLE_TRIGGER_TOKEN not set in environment variables.")
            self.enable_workflow = False
            self.response_status_code = 500
            self.response_message = "Server authentication configuration error"
            return

        if hmac.compare_digest(self.token, expected_token):
            logger.info("Simple trigger token verified.")
            self.enable_workflow = True
            self.sms_content = self.message
        else:
            logger.warning("Invalid simple trigger token received.")
            self.enable_workflow = False
            self.response_status_code = 401
            self.response_message = "Invalid trigger token"
