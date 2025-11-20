import hashlib
import hmac
import logging
import os
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import requests
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models import GitHubSettings, WebhookProcessor, create_github_settings

logger = logging.getLogger(__name__)


class NotionSettings(BaseSettings):
    """Settings specifically for Notion API interaction."""

    webhook_secret: str
    api_token: str
    model_config = SettingsConfigDict(extra="ignore", env_prefix="NOTION_")


# --- 2. Data Models (API Fetch) ---
# These models represent the data we fetch FROM Notion API to check the "Today" column.


class NotionCheckboxProperty(BaseModel):
    """Represents a Checkbox property in a Notion Page."""

    type: str = "checkbox"
    checkbox: bool


class NotionPageProperties(BaseModel):
    """
    Represents the properties of a page.
    We use extra='ignore' to handle the dynamic nature of Notion pages,
    but we strictly define 'Today' to validate our specific requirement.
    """

    Today: Optional[NotionCheckboxProperty]

    model_config = {"extra": "ignore"}


class NotionPage(BaseModel):
    """Represents the simplified Page object returned by Notion API."""

    id: str
    object: str = "page"
    properties: NotionPageProperties


# --- 3. Webhook Payload Models ---
# These models represent the incoming data FROM the Webhook.


class NotionEventType(str, Enum):
    PAGE_CREATED = "page.created"
    PAGE_UPDATED = "page.properties_updated"
    PAGE_CONTENT_UPDATED = "page.content_updated"
    # We define others to allow parsing, but we might filter them out later
    PAGE_DELETED = "page.deleted"
    UNKNOWN = "unknown"


class NotionEntity(BaseModel):
    id: str
    type: str  # e.g., "page", "database"


class NotionWebhookPayload(BaseModel):
    """
    Strict model for the incoming Webhook Payload.
    Includes the verification_token which is only present during the handshake.
    """

    type: str
    entity: NotionEntity
    verification_token: Optional[str] = None
    # We capture the rest to avoid validation errors on fields we don't need
    model_config = {"extra": "ignore"}


class NotionWebhookProcessor(WebhookProcessor):
    # Instance fields populated during validation
    event_type: str
    entity_id: str

    # Settings
    notion_settings: NotionSettings = Field(
        default_factory=NotionSettings, exclude=True
    )
    github_settings: GitHubSettings = Field(
        default_factory=lambda: create_github_settings(env_prefix="NOTION_")(),
        exclude=True,
    )

    @classmethod
    def verify_signature(
        cls, body_bytes: bytes, signature_header: str, secret: str
    ) -> bool:
        """
        Verifies X-Notion-Signature header.
        Algo: HMAC-SHA256(body, secret)
        """
        if not signature_header or not secret:
            return False

        if signature_header.startswith("sha256="):
            signature_header = signature_header.split("=")[1]

        mac = hmac.new(
            key=secret.encode("utf-8"), msg=body_bytes, digestmod=hashlib.sha256
        )
        computed_signature = mac.hexdigest()

        return hmac.compare_digest(computed_signature, signature_header)

    @classmethod
    def handle_verification(cls, payload: Dict[str, Any]) -> Any | None:
        """
        Phase 1: The Handshake.
        If Notion sends a verification_token, we log it.
        The user must copy this from logs/console to Notion UI.
        """
        if "verification_token" in payload:
            token = payload["verification_token"]
            logger.critical(f"NOTION VERIFICATION TOKEN RECEIVED: {token}")
            logger.critical(
                "Please paste this token into your Notion Integration Settings UI."
            )
            # We return 200 OK with the token or simple text to acknowledge receipt
            return {"status": "received", "verification_token": token}
        return None

    @classmethod
    def _fetch_page_details(cls, page_id: str, api_token: str) -> Optional[NotionPage]:
        """
        Synchronously fetches the page properties from Notion API.
        """
        url = f"https://api.notion.com/v1/pages/{page_id}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return NotionPage.model_validate(response.json())
        except Exception as e:
            logger.error(f"Failed to fetch Notion page {page_id}: {e}")
            return None

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """
        Logic:
        1. Validate basic structure.
        2. Filter for PAGE_CREATED or PAGE_UPDATED.
        3. Call API to check if 'Today' column is checked.
        """
        try:
            # 1. Structure Check
            model = NotionWebhookPayload.model_validate(payload)

            # 2. Type Check
            valid_types = [
                NotionEventType.PAGE_CREATED.value,
                NotionEventType.PAGE_UPDATED.value,
                NotionEventType.PAGE_CONTENT_UPDATED.value,
            ]

            if model.type not in valid_types or model.entity.type != "page":
                return False

            # 3. The "Today" Column Check (API Call)
            if not cls.notion_settings.api_token:
                logger.error("Missing NOTION_API_TOKEN cannot verify 'Today' status.")
                return False

            page_data = cls._fetch_page_details(
                model.entity.id, cls.notion_settings.api_token
            )

            if not page_data:
                return False

            # Check specifically for the 'Today' property
            if (
                page_data.properties.Today
                and page_data.properties.Today.checkbox is True
            ):
                logger.info(
                    f"Notion Page {model.entity.id} has 'Today' checked. Accepting."
                )
                return True
            else:
                logger.debug(
                    f"Notion Page {model.entity.id} 'Today' is False/Missing. Ignoring."
                )
                return False

        except ValidationError:
            # Not a Notion payload
            return False
        except Exception as e:
            logger.error(f"Error in Notion can_handle: {e}")
            return False

    def define_sms_content(self) -> None:
        self.sms_content = None

    # Override model_validate to map the flat payload to our internal fields
    @classmethod
    def model_validate(cls, obj: Any) -> "NotionWebhookProcessor":
        # Parse the inner event data
        payload = NotionWebhookPayload.model_validate(obj.get("event", obj))

        instance = cls(event_type=payload.type, entity_id=payload.entity.id)
        return instance


if __name__ == "__main__":
    # --- Test Mock ---
    import os

    # Mock Env
    os.environ["NOTION_WEBHOOK_SECRET"] = "secret_123"
    os.environ["NOTION_API_TOKEN"] = "secret_api_token"
    os.environ["NOTION_GITHUB_TOKEN"] = "gh_token"
    os.environ["NOTION_GITHUB_REPO"] = "my/repo"
    os.environ["NOTION_GITHUB_WORKFLOW_ID"] = "123"

    # Mock Payload (What Notion sends)
    sample_payload = {
        "type": "page.properties_updated",
        "timestamp": "2024-12-05T23:57:05.379Z",
        "entity": {"id": "1782edd6-a853-4d4a-b02c-9c8c16f28e53", "type": "page"},
        "data": {
            # Notion sends limited data here
        },
    }

    # NOTE: In a real run, can_handle will fail here because it tries
    # to hit the real Notion API with a fake ID/Token.
    # But this demonstrates the instantiation.

    if NotionWebhookProcessor.can_handle(sample_payload):
        processor = NotionWebhookProcessor.model_validate(sample_payload)
        processor.define_sms_content()
        print(processor.sms_content)
    else:
        print("Payload rejected (likely due to API check failure in this mock script)")
