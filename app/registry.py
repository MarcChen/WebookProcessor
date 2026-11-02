from typing import Type

from app.cal_com_handler import CalWebhookEvent
from app.gmail_handler import GmailWebhookProcessor
from app.models import WebhookProcessor
from app.notion_handler import NotionWebhookProcessor
from app.simple_handler import SimpleWebhookProcessor

# A registry to hold all our webhook processor classes
WEBHOOK_PROCESSORS: list[Type[WebhookProcessor]] = [
    CalWebhookEvent,
    NotionWebhookProcessor,
    GmailWebhookProcessor,
    SimpleWebhookProcessor,
]
