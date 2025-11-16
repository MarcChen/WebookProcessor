import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

import requests
from freesms import FreeClient
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SMS prefix constant
SMS_PREFIX = "Hook2SMS service : \n"


class GitHubSettings(BaseSettings):
    github_token: str = Field(..., alias="GITHUB_TOKEN")
    repo: str = Field(..., alias="GITHUB_REPO")
    workflow_id: str = Field(..., alias="GITHUB_WORKFLOW_ID")
    ref: str = Field(default="main", alias="GITHUB_REF")
    inputs: dict = Field(default_factory=dict, alias="GITHUB_INPUTS")

    def __init__(self, env_prefix: str = "", **data):
        self.model_config = SettingsConfigDict(extra="ignore", env_prefix=env_prefix)
        super().__init__(**data)

    @field_validator("github_token", "repo", "workflow_id")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v


class WebhookProcessor(ABC, BaseModel):
    """Abstract base class for all webhook processors."""

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)

    freesms_client: FreeClient = FreeClient(
        user=os.getenv("FREE_ID"), password=os.getenv("FREE_SECRET")
    )
    sms_content: str | None = Field(
        default=None, description="Content of the SMS to be sent"
    )
    github_settings: GitHubSettings | None = Field(
        default=None,
        description="GitHub action settings, if set then actions will be triggered",
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

    @abstractmethod
    def define_sms_content(self) -> None:
        """Process the payload and return the message to be sent."""
        raise NotImplementedError

    def send_sms(self) -> None:
        self.freesms_client.send_sms(
            message=SMS_PREFIX + self.sms_content,
        )

    def fire_github_action(self) -> None:
        """Trigger any GitHub actions with provided arguments if necessary."""
        # Example implementation: send a POST request to GitHub Actions workflow_dispatch endpoint  # noqa: E501

        url = f"https://api.github.com/repos/{self.github_settings.repo}/actions/workflows/{self.github_settings.workflow_id}/dispatches"
        headers = {
            "Authorization": f"Bearer {self.github_settings.github_token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "ref": self.github_settings.ref,
            "inputs": self.github_settings.inputs,
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

    @abstractmethod
    def process_workflow(self) -> None:
        """Perform the whole workflow: process payload, send SMS, trigger actions, etc."""  # noqa: E501
        self.define_sms_content()
        self.send_sms()
        if self.github_settings:
            self.fire_github_action()


# A registry to hold all our webhook processor classes
WEBHOOK_PROCESSORS: list[Type[WebhookProcessor]] = []


def register_processor(cls: Type[WebhookProcessor]) -> Type[WebhookProcessor]:
    """A decorator to register new webhook processor classes."""
    WEBHOOK_PROCESSORS.append(cls)
    return cls
