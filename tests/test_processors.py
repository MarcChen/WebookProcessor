import base64
import json
from unittest.mock import MagicMock, patch

from app.cal_com_handler import CalWebhookEvent
from app.gmail_handler import GmailWebhookProcessor
from app.intervals_handler import IntervalsWebhookProcessor
from app.notion_handler import NotionWebhookProcessor
from app.simple_handler import SimpleWebhookProcessor
from tests.base_test import BaseWebhookTest


class TestProcessors(BaseWebhookTest):
    def test_simple_processor(self):
        payload = {"type": "simple", "message": "Hello World", "token": "valid_token"}
        self.run_processor_test(
            SimpleWebhookProcessor, payload, expected_sms="Hello World"
        )

        payload_invalid = {"type": "simple", "message": "Bad Token", "token": "wrong"}
        self.run_processor_test(
            SimpleWebhookProcessor, payload_invalid, expected_sms=None
        )

    def test_cal_com_processor(self):
        payload = {
            "triggerEvent": "BOOKING_CREATED",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {"title": "Meeting", "organizer": {"name": "Alice"}},
        }
        self.run_processor_test(
            CalWebhookEvent,
            payload,
            expected_sms="Booking 'Meeting' (BOOKING_CREATED) created by Alice",
        )

        payload_ping = {
            "triggerEvent": "PING",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {},
        }
        self.run_processor_test(CalWebhookEvent, payload_ping, expected_sms=None)

    def test_intervals_processor(self):
        payload = {
            "events": [
                {
                    "athlete_id": "i780178",
                    "type": "ACTIVITY_UPLOADED",
                    "id": "i204876551",
                    "start_date_local": "2026-11-01T19:26:47",
                    "activity": {
                        "id": "i204876551",
                        "name": "Dubai Cyclisme virtuel",
                        "type": "VirtualRide",
                    },
                }
            ]
        }

        expected_msg = (
            "New activity on Intervals.icu: i204876551 (Dubai Cyclisme virtuel)"
        )
        self.run_processor_test(
            IntervalsWebhookProcessor,
            payload,
            expected_sms=expected_msg,
            expected_github=True,
        )

        # Test non-activity event (should not trigger github)
        payload_other = {
            "events": [
                {
                    "athlete_id": "i780178",
                    "type": "WELLNESS_UPDATED",
                }
            ]
        }
        self.run_processor_test(
            IntervalsWebhookProcessor,
            payload_other,
            expected_sms=None,
            expected_github=False,
        )

    @patch("app.notion_handler.NotionWebhookProcessor._fetch_page_details")
    def test_notion_processor(self, mock_fetch):
        mock_page = MagicMock()
        mock_page.properties.Today.checkbox = True
        mock_page.properties.Name.title = [{"plain_text": "Task Title"}]
        mock_fetch.return_value = mock_page

        payload = {
            "type": "page.properties_updated",
            "entity": {"id": "page-id", "type": "page"},
            "data": {},
        }

        self.run_processor_test(NotionWebhookProcessor, payload, expected_github=True)

        mock_page.properties.Today.checkbox = False
        self.run_processor_test(NotionWebhookProcessor, payload, expected_github=False)

    def test_gmail_processor(self):
        data_str = json.dumps({"emailAddress": "test@example.com", "historyId": 100})
        b64_data = base64.b64encode(data_str.encode()).decode()

        payload = {
            "message": {
                "data": b64_data,
                "messageId": "msg-id",
                "publishTime": "2024-01-01T00:00:00Z",
            },
            "subscription": "sub-id",
        }

        self.run_processor_test(GmailWebhookProcessor, payload, expected_github=True)

        payload_bad = payload.copy()
        payload_bad["message"] = {
            "data": "bad-base64",
            "messageId": "1",
            "publishTime": "now",
        }
        self.run_processor_test(
            GmailWebhookProcessor, payload_bad, expected_github=False
        )
