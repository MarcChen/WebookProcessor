import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

import requests
from fastapi.responses import JSONResponse
from freesms import FreeClient
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SMS prefix constant
SMS_PREFIX = "Hook2SMS service : \n"

logger = logging.getLogger(__name__)


class GitHubSettings(BaseSettings):
    token: str
    repo: str
    workflow_id: str
    ref: str = Field(default="main")
    inputs: dict = Field(default_factory=dict)

    @field_validator("token", "repo", "workflow_id")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v


def create_github_settings(env_prefix: str) -> GitHubSettings:
    class PrefixedGitHubSettings(GitHubSettings):
        model_config = SettingsConfigDict(
            extra="ignore", env_prefix=env_prefix + "GITHUB_"
        )

    return PrefixedGitHubSettings


class WebhookProcessor(ABC, BaseModel):
    """Abstract base class for all webhook processors."""

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    freesms_client: FreeClient = Field(
        default=FreeClient(
            user=os.getenv("FREE_ID"),
            password=os.getenv("FREE_SECRET"),
        ),
        exclude=True,
    )
    sms_content: str | None = Field(
        default=None, description="Content of the SMS to be sent"
    )
    github_settings: GitHubSettings | None = Field(
        default=None,
        description="GitHub action settings, if set then actions will be triggered",
        exclude=True,
    )
    enable_workflow: bool = Field(
        default=True,
        description="Flag to enable or disable the entire processing workflow",
    )

    @classmethod
    @abstractmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if this processor can handle the given payload."""
        raise NotImplementedError

    @classmethod
    def handle_verification(cls, query_params: Dict[str, Any]) -> Any | None:
        """
        Handle webhook verification requests (e.g., Strava's GET challenge).
        Returns the response body if the verification is handled, otherwise None.
        """
        return None

    @abstractmethod
    def define_sms_content(self) -> None:
        """Process the payload and return the message to be sent."""
        raise NotImplementedError

    def send_sms(self) -> None:
        self.freesms_client.send_sms(
            text=SMS_PREFIX + self.sms_content,
        )

    def fire_github_action(self) -> None:
        """Trigger any GitHub actions with provided arguments if necessary."""
        # Example implementation: send a POST request to GitHub Actions workflow_dispatch endpoint  # noqa: E501

        url = f"https://api.github.com/repos/{self.github_settings.repo}/actions/workflows/{self.github_settings.workflow_id}/dispatches"
        headers = {
            "Authorization": f"token {self.github_settings.token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "ref": self.github_settings.ref,
            "inputs": self.github_settings.inputs,
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

    def process_workflow(self) -> JSONResponse:
        """Perform the whole workflow: process payload, send SMS, trigger actions, etc."""  # noqa: E501
        self.define_sms_content()
        logger.debug(f"Defined SMS content: {self.sms_content}")
        if not self.enable_workflow:
            logger.info("Workflow is disabled for this event.")
            return JSONResponse(
                content={"status": "Workflow disabled for this event"},
                status_code=200,
            )

        if self.sms_content:
            logger.info("Sending SMS with content.")
            self.send_sms()
        if self.github_settings:
            logger.info(
                f"Triggering GitHub action for repo: {self.github_settings.repo}"
            )  # noqa: E501
            self.fire_github_action()

        status_message = "SMS sent" if self.sms_content else "No SMS to send"
        return JSONResponse(
            content={
                "status": status_message,
                "event": self.model_dump(exclude_none=True),
            }
        )


# A registry to hold all our webhook processor classes
WEBHOOK_PROCESSORS: list[Type[WebhookProcessor]] = []


def register_processor(cls: Type[WebhookProcessor]) -> Type[WebhookProcessor]:
    """A decorator to register new webhook processor classes."""
    WEBHOOK_PROCESSORS.append(cls)
    return cls
