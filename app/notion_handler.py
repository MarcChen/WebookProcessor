import hashlib
import hmac
import logging
from datetime import timedelta
from enum import Enum
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field
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
    github_settings: GitHubSettings = Field(
        default_factory=lambda: create_github_settings(
            env_prefix="NOTION_", cooldown=timedelta(seconds=5)
        )(),
        exclude=True,
    )

    # Override model_validate to map the flat payload to our internal fields
    @classmethod
    def model_validate(cls, obj: Any) -> "NotionWebhookProcessor":
        # Parse the inner event data
        payload = NotionWebhookPayload.model_validate(obj.get("event", obj))

        instance = cls(event_type=payload.type, entity_id=payload.entity.id)
        return instance

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
    def handle_verification(cls, payload: Dict[str, Any]) -> Optional[Any]:
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
        logger.debug(f"Fetching Notion page details for page ID: {page_id}")
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
        try:
            model = NotionWebhookPayload.model_validate(payload)

            # 2. Type Check
            valid_types = [
                NotionEventType.PAGE_CREATED.value,
                NotionEventType.PAGE_UPDATED.value,
                NotionEventType.PAGE_CONTENT_UPDATED.value,
            ]

            if model.type not in valid_types or model.entity.type != "page":
                return False
            else:
                return True
        except Exception:
            return False

    def should_enable_workflow(self, payload: Dict[str, Any]) -> bool:
        model = NotionWebhookPayload.model_validate(payload)
        notion_settings = NotionSettings()

        # The "Today" Column Check (API Call)
        if not notion_settings.api_token:
            logger.error("Missing NOTION_API_TOKEN cannot verify 'Today' status.")
            return False

        page_data = self._fetch_page_details(model.entity.id, notion_settings.api_token)

        if not page_data:
            return False

        # Check specifically for the 'Today' property
        if page_data.properties.Today and page_data.properties.Today.checkbox is True:
            logger.info(
                f"Notion Page {model.entity.id} has 'Today' checked. Accepting."
            )
            self.enable_workflow = True

            # Extract page title if available
            page_title = "Unknown Title"
            if hasattr(page_data.properties, "Name") and page_data.properties.Name:
                # Notion title properties have a specific structure
                title_prop = getattr(page_data.properties, "Name", None)
                if title_prop and hasattr(title_prop, "title") and title_prop.title:
                    page_title = title_prop.title[0].get("plain_text", "Unknown Title")

            # Set workflow inputs for GitHub Action
            self.github_settings.inputs = {
                "page_id": model.entity.id,
                "page_title": page_title,
            }

        else:
            logger.debug(
                f"Notion Page {model.entity.id} 'Today' is False/Missing. Ignoring."
            )
            self.enable_workflow = False


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    notion_payload = {
        "id": "905251bb-a324-4814-946a-bbf2fba8bd9f",
        "timestamp": "2025-11-22T14:47:01.525Z",
        "workspace_id": "c8cdf654-652d-4606-8209-78ad7631275f",
        "workspace_name": "Kems's Notion",
        "subscription_id": "2b1d872b-594c-81bd-a29a-0099adf0bc92",
        "integration_id": "15ed872b-594c-811c-ab1a-003763100ec5",
        "authors": [{"id": "6f842ce2-9cc9-405f-979d-85a0c3672d5f", "type": "person"}],
        "attempt_number": 2,
        "api_version": "2025-09-03",
        "entity": {"id": "2b319fda-9f9d-80d8-94b9-ffb360c9d095", "type": "page"},
        "type": "page.created",
        "data": {
            "parent": {
                "id": "2614254e-32d1-4d5e-9d91-00b029fb31bb",
                "type": "database",
                "data_source_id": "4908fae5-c779-4b48-8b9e-36033376ab04",
            }
        },
    }

    if NotionWebhookProcessor.can_handle(notion_payload):
        processor = NotionWebhookProcessor.model_validate(notion_payload)
        processor.process_workflow(notion_payload)
        print(processor.sms_content)
