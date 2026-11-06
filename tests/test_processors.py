import base64
import json
from unittest.mock import MagicMock, patch

from app.cal_com_handler import CalWebhookEvent
from app.gmail_handler import GmailWebhookProcessor
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

    def test_simple_processor_security_and_edge_cases(self):
        # 1. Verify token is excluded from serialization (no credential leak)
        payload = {"type": "simple", "message": "Secret alert", "token": "valid_token"}
        processor = SimpleWebhookProcessor.model_validate(payload)
        dumped = processor.model_dump()
        self.assertNotIn("token", dumped)

        # 2. Verify invalid token returns HTTP 401 status in response
        payload_invalid = {"type": "simple", "message": "Unauthorized", "token": "bad"}
        proc_invalid = SimpleWebhookProcessor.model_validate(payload_invalid)
        res = proc_invalid.process_workflow(payload_invalid)
        self.assertEqual(res.status_code, 401)
        self.assertFalse(proc_invalid.enable_workflow)

        # 3. Missing SIMPLE_TRIGGER_TOKEN in environment returns 500
        with patch.dict("os.environ", {}, clear=True):
            proc_no_env = SimpleWebhookProcessor.model_validate(payload)
            res_no_env = proc_no_env.process_workflow(payload)
            self.assertEqual(res_no_env.status_code, 500)
            self.assertFalse(proc_no_env.enable_workflow)

        # 4. Non-dict payload in can_handle returns False
        self.assertFalse(SimpleWebhookProcessor.can_handle(["simple"]))
        self.assertFalse(SimpleWebhookProcessor.can_handle("simple"))

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

    def test_cal_com_null_safety_and_edge_cases(self):
        # Null organizer should not crash
        payload_null_organizer = {
            "triggerEvent": "BOOKING_CREATED",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {"title": "Meeting", "organizer": None},
        }
        self.run_processor_test(
            CalWebhookEvent,
            payload_null_organizer,
            expected_sms="Booking 'Meeting' (BOOKING_CREATED) created by Unknown",
        )

        # Null title should not crash
        payload_null_title = {
            "triggerEvent": "BOOKING_CREATED",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": {"title": None, "organizer": {"name": "Bob"}},
        }
        self.run_processor_test(
            CalWebhookEvent,
            payload_null_title,
            expected_sms="Booking 'No Title' (BOOKING_CREATED) created by Bob",
        )

        # Null payload entirely (payload=None) should validate and not crash
        payload_none = {
            "triggerEvent": "BOOKING_CREATED",
            "createdAt": "2024-01-01T00:00:00Z",
            "payload": None,
        }
        cal_proc = CalWebhookEvent.model_validate(payload_none)
        self.assertIsNotNone(cal_proc)
        self.run_processor_test(
            CalWebhookEvent,
            payload_none,
            expected_sms="Booking 'No Title' (BOOKING_CREATED) created by Unknown",
        )

        # Non-dict payload in can_handle returns False
        self.assertFalse(CalWebhookEvent.can_handle(["triggerEvent"]))
        self.assertFalse(CalWebhookEvent.can_handle("not a dict"))

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

    def test_notion_title_extraction_with_real_pydantic_model(self):
        # Test real Notion API response model validation preserves extra title field
        from app.notion_handler import NotionPage

        raw_api_data = {
            "id": "page-123",
            "object": "page",
            "properties": {
                "Today": {"type": "checkbox", "checkbox": True},
                "Name": {
                    "id": "title",
                    "type": "title",
                    "title": [
                        {
                            "type": "text",
                            "text": {"content": "Real Task Title"},
                            "plain_text": "Real Task Title",
                        }
                    ],
                },
            },
        }

        page = NotionPage.model_validate(raw_api_data)
        self.assertTrue(page.properties.Today.checkbox)
        self.assertEqual(page.properties.extract_title(), "Real Task Title")

        # Test string title (does not crash with builtin str.title method)
        raw_string_title = {
            "id": "page-456",
            "object": "page",
            "properties": {
                "Today": {"type": "checkbox", "checkbox": True},
                "Name": "A Plain String Title",
            },
        }
        page_str = NotionPage.model_validate(raw_string_title)
        self.assertEqual(page_str.properties.extract_title(), "A Plain String Title")

    def test_notion_signature_verification(self):
        secret = "super_secret_notion_key"
        body = b'{"type": "page.created"}'
        import hashlib
        import hmac

        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        # Valid with sha256= prefix
        self.assertTrue(
            NotionWebhookProcessor.verify_signature(body, f"sha256={valid_sig}", secret)
        )
        # Valid raw hex
        self.assertTrue(
            NotionWebhookProcessor.verify_signature(body, valid_sig, secret)
        )
        # Invalid signature
        self.assertFalse(
            NotionWebhookProcessor.verify_signature(body, "wrong_sig", secret)
        )
        # Empty inputs
        self.assertFalse(NotionWebhookProcessor.verify_signature(body, "", secret))
        self.assertFalse(NotionWebhookProcessor.verify_signature(body, valid_sig, ""))

    def test_notion_handle_verification(self):
        # Notion verification handshake
        payload = {"verification_token": "token_abc_123"}
        res = NotionWebhookProcessor.handle_verification(payload)
        self.assertEqual(
            res, {"status": "received", "verification_token": "token_abc_123"}
        )

        res_none = NotionWebhookProcessor.handle_verification({})
        self.assertIsNone(res_none)

        # Non-dict payload in can_handle returns False
        self.assertFalse(NotionWebhookProcessor.can_handle(["page.created"]))

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

    def test_gmail_processor_edge_cases(self):
        # Non-dict in can_handle returns False
        self.assertFalse(GmailWebhookProcessor.can_handle(["message"]))

        # Non-dict decoded data inside base64
        non_dict_str = json.dumps(["not", "a", "dict"])
        b64_non_dict = base64.b64encode(non_dict_str.encode()).decode()
        payload = {
            "message": {
                "data": b64_non_dict,
                "messageId": "msg-id",
                "publishTime": "2024-01-01T00:00:00Z",
            }
        }
        processor = GmailWebhookProcessor.model_validate(payload)
        self.assertIsNone(processor._decode_message_data())
        processor.should_enable_workflow(payload)
        self.assertFalse(processor.enable_workflow)
