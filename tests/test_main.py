import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import status

from main import (
    global_exception_handler,
    healthcheck,
    webhook_listener,
    webhook_verification,
)


class TestMainEndpoints(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env_patcher = patch.dict(
            os.environ,
            {
                "FREE_ID": "test_free_id",
                "FREE_SECRET": "test_free_secret",
                "SIMPLE_TRIGGER_TOKEN": "valid_token",
            },
        )
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    async def test_healthcheck(self):
        result = await healthcheck()
        self.assertEqual(result, {"status": "ok"})

    async def test_webhook_verification_unhandled(self):
        mock_request = MagicMock()
        mock_request.query_params = {"unknown": "param"}
        response = await webhook_verification(mock_request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("main.notify_error")
    @patch("app.models.WebhookProcessor.send_sms")
    async def test_webhook_listener_success(self, mock_send_sms, mock_notify):
        mock_request = MagicMock()
        mock_request.json = AsyncMock(
            return_value={
                "type": "simple",
                "message": "Hello World",
                "token": "valid_token",
            }
        )

        response = await webhook_listener(mock_request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_send_sms.assert_called_once()
        mock_notify.assert_not_called()

    @patch("main.notify_error")
    async def test_webhook_listener_unmatched_payload_alerts_freesms(self, mock_notify):
        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={"unrecognized_key": "some_data"})

        response = await webhook_listener(mock_request)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertIn("No processor found for payload", args[0])
        self.assertEqual(kwargs.get("context"), "POST /webhook")

    @patch("main.notify_error")
    @patch("main.WEBHOOK_PROCESSORS")
    async def test_webhook_listener_exception_alerts_freesms(
        self, mock_processors, mock_notify
    ):
        mock_proc = MagicMock()
        mock_proc.can_handle.return_value = True
        mock_proc.model_validate.side_effect = RuntimeError("Failed validating payload")
        mock_proc.__name__ = "FailingProcessor"
        mock_processors.__iter__.return_value = [mock_proc]

        mock_request = MagicMock()
        mock_request.json = AsyncMock(return_value={"some": "payload"})

        response = await webhook_listener(mock_request)
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertIn("Error processing webhook", args[0])
        self.assertEqual(kwargs.get("context"), "POST /webhook")
        self.assertIsInstance(kwargs.get("exc"), RuntimeError)

    @patch("main.notify_error")
    async def test_global_exception_handler_alerts_freesms(self, mock_notify):
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/webhook"

        exc = ValueError("Fatal crash")
        response = await global_exception_handler(mock_request, exc)

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertIn("Unhandled exception on POST /webhook", args[0])
        self.assertEqual(kwargs.get("context"), "FastAPI")
        self.assertEqual(kwargs.get("exc"), exc)


if __name__ == "__main__":
    unittest.main()
