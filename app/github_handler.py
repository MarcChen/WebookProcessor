import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from app.models import WebhookProcessor

logger = logging.getLogger(__name__)


class GitHubRepository(BaseModel):
    full_name: str
    name: str


class GitHubWorkflowRun(BaseModel):
    name: Optional[str] = None
    head_branch: str
    conclusion: Optional[str] = None


class GitHubWorkflowPayload(BaseModel):
    action: str
    workflow_run: GitHubWorkflowRun
    repository: GitHubRepository


class GitHubWorkflowProcessor(WebhookProcessor):
    """Processor for GitHub Workflow failure notifications."""

    action: str
    workflow_run: GitHubWorkflowRun
    repository: GitHubRepository

    @classmethod
    def can_handle(cls, payload: Dict[str, Any]) -> bool:
        """Check if the payload is a GitHub workflow_run event."""
        # GitHub sends 'workflow_run' key in the payload for this event
        if "workflow_run" in payload and "action" in payload:
            return True
        return False

    def should_enable_workflow(self, payload: Dict[str, Any]) -> None:
        """Check for failed workflow runs on main branch."""
        if (
            self.action == "completed"
            and self.workflow_run.conclusion == "failure"
            and self.workflow_run.head_branch == "main"
        ):
            repo_name = self.repository.name
            workflow_name = self.workflow_run.name or "Unknown Workflow"

            logger.info(f"GitHub workflow '{workflow_name}' failed on '{repo_name}'.")
            self.enable_workflow = True
            self.sms_content = f"GitHub Action failed: {repo_name} - {workflow_name}"
        else:
            self.enable_workflow = False
            logger.debug("Ignoring GitHub event (not a failed run on main).")
