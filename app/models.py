import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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
    cooldown: timedelta = Field(
        default=timedelta(minutes=3),
        description="Minimum time between workflow triggers",
    )

    @field_validator("token", "repo", "workflow_id")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v


def create_github_settings(
    env_prefix: str, cooldown: timedelta = timedelta(minutes=3)
) -> GitHubSettings:
    class PrefixedGitHubSettings(GitHubSettings):
        model_config = SettingsConfigDict(
            extra="ignore", env_prefix=env_prefix + "GITHUB_"
        )

        cooldown: timedelta = Field(default_factory=lambda: cooldown)

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
    sms_content: Optional[str] = Field(
        default=None, description="Content of the SMS to be sent"
    )
    github_settings: Optional[GitHubSettings] = Field(
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
    def handle_verification(cls, payload: Dict[str, Any]) -> Optional[Any]:
        """
        Handle webhook verification requests (e.g., Strava's GET challenge).
        Returns the response body if the verification is handled, otherwise None.
        """
        return None

    @abstractmethod
    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        """
        Determine whether to proceed with the workflow event based on the input payload.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    def send_sms(self) -> None:
        self.freesms_client.send_sms(
            text=SMS_PREFIX + self.sms_content,
        )

    def _check_cooldown(self) -> bool:
        """
        Internal function to check if the last run was recent.
        Returns True if we should trigger (cooldown passed), False otherwise.
        """
        url = f"https://api.github.com/repos/{self.github_settings.repo}/actions/workflows/{self.github_settings.workflow_id}/runs"

        headers = {
            "Authorization": f"token {self.github_settings.token}",
            "Accept": "application/vnd.github+json",
        }

        params = {"per_page": 1, "exclude_pull_requests": str(True).lower()}

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if not data.get("workflow_runs"):
                logger.debug("No previous workflow runs found. Proceeding.")
                return True

            last_run = data["workflow_runs"][0]
            created_at_str = last_run["created_at"].replace("Z", "+00:00")
            last_run_time = datetime.fromisoformat(created_at_str)

            now = datetime.now(timezone.utc)

            time_diff = now - last_run_time
            cooldown = self.github_settings.cooldown

            if time_diff < cooldown:
                total_seconds = int(time_diff.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                cooldown_str = f"{int(cooldown.total_seconds() // 60)}m {int(cooldown.total_seconds() % 60)}s"  # noqa: E501
                logger.warning(
                    f"Skipping GitHub Action: Last run was {minutes}m {seconds}s ago "
                    f"(Cooldown is {cooldown_str})"
                )
                return False

            logger.info(f"Cooldown check passed. Last run was {time_diff} ago.")
            return True

        except Exception as e:
            logger.error(
                f"Failed to check workflow cooldown: {e}. Defaulting to trigger."
            )
            return True

    def fire_github_action(self) -> None:
        """Trigger any GitHub actions if cooldown has passed."""

        if not self._check_cooldown():
            return

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

    def process_workflow(self, payload: Dict[str, Any]) -> JSONResponse:
        """Perform the whole workflow: process payload, send SMS, trigger actions, etc."""  # noqa: E501
        self.should_enable_workflow(payload)
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
            )
            self.fire_github_action()

        status_message = "SMS sent" if self.sms_content else "No SMS to send"
        return JSONResponse(
            content={
                "status": status_message,
                "event": self.model_dump(exclude_none=True),
            }
        )
