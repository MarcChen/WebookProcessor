from unittest.mock import patch, MagicMock
from tests.base_test import BaseWebhookTest
from app.simple_handler import SimpleWebhookProcessor
from app.cal_com_handler import CalWebhookEvent
from app.strava_handler import StravaWebhookProcessor
from app.notion_handler import NotionWebhookProcessor, NotionPage
from app.gmail_handler import GmailWebhookProcessor

class TestProcessors(BaseWebhookTest):

    def test_simple_processor(self):
        payload = {"type": "simple", "message": "Hello World", "token": "valid_token"}
        self.run_processor_test(SimpleWebhookProcessor, payload, expected_sms="Hello World")

        payload_invalid = {"type": "simple", "message": "Bad Token", "token": "wrong"}
        self.run_processor_test(SimpleWebhookProcessor, payload_invalid, expected_sms=None)

    def test_cal_com_processor(self):
        payload = {
            "triggerEvent": "BOOKING_CREATED",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {
                "title": "Meeting",
                "organizer": {"name": "Alice"}
            }
        }
        self.run_processor_test(CalWebhookEvent, payload, expected_sms="Booking 'Meeting' (BOOKING_CREATED) created by Alice")

        payload_ping = {
            "triggerEvent": "PING",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {}
        }
        self.run_processor_test(CalWebhookEvent, payload_ping, expected_sms=None)

    @patch('app.strava_handler.StravaClient')
    def test_strava_processor(self, mock_client_cls):
        # Mock StravaClient
        mock_client = mock_client_cls.return_value
        mock_client.is_virtual_ride.return_value = True
        mock_client.get_activity.return_value = {"name": "Virtual Ride"}

        payload = {
            "aspect_type": "create",
            "event_time": 1234567890,
            "object_id": 123,
            "object_type": "activity",
            "owner_id": 456,
            "subscription_id": 789,
            "updates": {}
        }

        # Strava processor triggers both SMS (if virtual) and GitHub action (if env vars set)
        self.run_processor_test(StravaWebhookProcessor, payload, expected_sms="New activity virtual ride: Virtual Ride", expected_github=True)

        # Test non-virtual ride
        mock_client.is_virtual_ride.return_value = False
        self.run_processor_test(StravaWebhookProcessor, payload, expected_sms=None, expected_github=False)

    @patch('app.notion_handler.NotionWebhookProcessor._fetch_page_details')
    def test_notion_processor(self, mock_fetch):
        # Mock Page response with Today=True
        mock_page = MagicMock()
        mock_page.properties.Today.checkbox = True
        mock_page.properties.Name.title = [{"plain_text": "Task Title"}]
        mock_fetch.return_value = mock_page

        payload = {
            "type": "page.properties_updated",
            "entity": {"id": "page-id", "type": "page"},
            "data": {} # Minimal needed
        }

        # Test with expected GitHub trigger
        self.run_processor_test(NotionWebhookProcessor, payload, expected_github=True)

        # Mock Page response with Today=False
        mock_page.properties.Today.checkbox = False
        self.run_processor_test(NotionWebhookProcessor, payload, expected_github=False)

    def test_gmail_processor(self):
        # Valid pubsub message with base64 data
        # {"emailAddress": "test@example.com", "historyId": 100} -> base64
        import base64
        import json
        data_str = json.dumps({"emailAddress": "test@example.com", "historyId": 100})
        b64_data = base64.b64encode(data_str.encode()).decode()

        payload = {
            "message": {
                "data": b64_data,
                "messageId": "msg-id",
                "publishTime": "2024-01-01T00:00:00Z"
            },
            "subscription": "sub-id"
        }

        # Gmail processor always enables workflow if decode is successful
        self.run_processor_test(GmailWebhookProcessor, payload, expected_github=True)

        # Invalid data
        payload_bad = payload.copy()
        payload_bad["message"] = {"data": "bad-base64", "messageId": "1", "publishTime": "now"}
        self.run_processor_test(GmailWebhookProcessor, payload_bad, expected_github=False)
