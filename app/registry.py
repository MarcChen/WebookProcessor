from typing import Type

from app.cal_com_handler import CalWebhookEvent
from app.github_handler import GitHubWorkflowProcessor
from app.gmail_handler import GmailWebhookProcessor
from app.models import WebhookProcessor
from app.notion_handler import NotionWebhookProcessor
from app.simple_handler import SimpleWebhookProcessor
from app.strava_handler import StravaWebhookProcessor

# A registry to hold all our webhook processor classes
WEBHOOK_PROCESSORS: list[Type[WebhookProcessor]] = [
    CalWebhookEvent,
    StravaWebhookProcessor,
    NotionWebhookProcessor,
    GmailWebhookProcessor,
    SimpleWebhookProcessor,
    GitHubWorkflowProcessor,
]
