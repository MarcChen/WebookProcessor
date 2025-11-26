import base64
import json
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models import (
    GitHubSettings,
    WebhookProcessor,
    create_github_settings,
)

logger = logging.getLogger(__name__)


class PubSubMessage(BaseModel):
    """Pub/Sub message structure."""

    data: str  # Base64-encoded data
    message_id: str = Field(alias="messageId")
    publish_time: Optional[str] = Field(default=None, alias="publishTime")


class GmailNotificationData(BaseModel):
    """Gmail notification data structure (decoded from Pub/Sub message)."""

    emailAddress: str
    historyId: int


class GmailWebhookProcessor(WebhookProcessor):
    """Processor for Gmail push notifications via Pub/Sub."""

    message: PubSubMessage
    subscription: Optional[str] = None

    github_settings: GitHubSettings = Field(
        default_factory=lambda: create_github_settings(
            env_prefix="GMAIL_", cooldown=timedelta(minutes=5)
        )(),
        exclude=True,
    )

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is a Pub/Sub message from Gmail."""
        try:
            # Pub/Sub messages have a 'message' field with 'data' inside
            if "message" not in payload:
                return False

            # Validate the structure
            cls.model_validate(payload)
            return True
        except Exception as e:
            logger.debug(f"GmailWebhookProcessor cannot handle payload: {e}")
            return False

    def _decode_message_data(self) -> Optional[GmailNotificationData]:
        """Decode the base64-encoded Pub/Sub message data."""
        try:
            # Decode base64 data
            decoded_bytes = base64.b64decode(self.message.data)
            decoded_str = decoded_bytes.decode("utf-8")
            data = json.loads(decoded_str)

            logger.info(f"Decoded Gmail notification: {data}")

            # Validate against Gmail notification structure
            notification = GmailNotificationData.model_validate(data)
            return notification
        except Exception as e:
            logger.error(f"Failed to decode Pub/Sub message data: {e}")
            return None

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        """Determine whether to trigger the workflow based on the notification."""
        # Decode the message to get Gmail notification data
        notification = self._decode_message_data()

        if notification is None:
            logger.warning("Could not decode Gmail notification, disabling workflow")
            self.enable_workflow = False
            return

        # Log the notification details
        logger.info(
            f"Gmail notification received for {notification.emailAddress} "
            f"with historyId: {notification.historyId}"
        )

        # Since the user wants to trigger workflow for ANY incoming email,
        # we always enable the workflow when we successfully decode the notification
        self.enable_workflow = True


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG)

    # Set dummy env vars for validation
    os.environ["GMAIL_GITHUB_TOKEN"] = "dummy_token"
    os.environ["GMAIL_GITHUB_REPO"] = "dummy_repo"
    os.environ["GMAIL_GITHUB_WORKFLOW_ID"] = "dummy_workflow_id"

    # Sample Pub/Sub payload from Gmail push notification
    sample_payload = {
        "message": {
            "data": "eyJlbWFpbEFkZHJlc3MiOiJrZW1hcjk4NzQxNUBnbzfpBC5jb20iLCJoaXN0b3J5SWQiOjMxMjU2Nn0=",  # noqa: E501
            "messageId": "17307692776715457",
            "message_id": "17307692776715457",
            "publishTime": "2025-11-24T13:15:15.925Z",
            "publish_time": "2025-11-24T13:15:15.925Z",
        },
        "subscription": "projects/a-dummy-project/subscriptions/gmail-webhook-notifications-subscription",  # noqa: E501
    }  # noqa: E501

    # Test the processor
    if GmailWebhookProcessor.can_handle(sample_payload):
        processor = GmailWebhookProcessor.model_validate(sample_payload)
        processor.should_enable_workflow(sample_payload)
        print(f"Enable workflow: {processor.enable_workflow}")
        print(f"SMS content: {processor.sms_content}")
    else:
        print("Processor cannot handle the payload")
