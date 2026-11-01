import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.error_notifier import (
    MAX_SMS_LENGTH,
    ErrorNotifier,
    FreeSMSErrorLogHandler,
    notify_error,
)


class TestErrorNotifier(unittest.TestCase):
    def setUp(self):
        self.notifier = ErrorNotifier(
            user="test_user",
            password="test_pass",
            cooldown_seconds=10,
        )

    @patch("app.error_notifier.FreeClient")
    def test_send_error_alert_success(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.error.return_value = False
        mock_client.send_sms.return_value = mock_response

        success = self.notifier.send_error_alert(
            error_message="Database connection failed",
            context="DB_SERVICE",
        )

        self.assertTrue(success)
        mock_client.send_sms.assert_called_once()
        sent_text = mock_client.send_sms.call_args[0][0]
        self.assertIn("[WebhookProcessor ERROR]", sent_text)
        self.assertIn("[DB_SERVICE]", sent_text)
        self.assertIn("Database connection failed", sent_text)

    @patch("app.error_notifier.FreeClient")
    def test_send_error_alert_with_exception(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.error.return_value = False
        mock_client.send_sms.return_value = mock_response

        exc = ValueError("Invalid parameter value")
        success = self.notifier.send_error_alert(
            error_message="Validation step failed",
            context="Validator",
            exc=exc,
        )

        self.assertTrue(success)
        sent_text = mock_client.send_sms.call_args[0][0]
        self.assertIn("Validation step failed: Invalid parameter value", sent_text)

    @patch("app.error_notifier.FreeClient")
    def test_message_truncation(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.error.return_value = False
        mock_client.send_sms.return_value = mock_response

        long_error = "A" * 500
        success = self.notifier.send_error_alert(
            error_message=long_error,
            context="LongTest",
        )

        self.assertTrue(success)
        sent_text = mock_client.send_sms.call_args[0][0]
        self.assertLessEqual(len(sent_text), MAX_SMS_LENGTH)
        self.assertTrue(sent_text.endswith("..."))

    @patch("app.error_notifier.FreeClient")
    def test_cooldown_throttling(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.error.return_value = False
        mock_client.send_sms.return_value = mock_response

        # First call succeeds
        first_call = self.notifier.send_error_alert(
            error_message="Crash on worker",
            context="Worker1",
        )
        self.assertTrue(first_call)
        self.assertEqual(mock_client.send_sms.call_count, 1)

        # Immediate second call with identical error is throttled
        second_call = self.notifier.send_error_alert(
            error_message="Crash on worker",
            context="Worker1",
        )
        self.assertFalse(second_call)
        self.assertEqual(mock_client.send_sms.call_count, 1)

        # Different context or error signature is NOT throttled
        diff_call = self.notifier.send_error_alert(
            error_message="Different error entirely",
            context="Worker2",
        )
        self.assertTrue(diff_call)
        self.assertEqual(mock_client.send_sms.call_count, 2)

    def test_missing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            notifier = ErrorNotifier(user=None, password=None)
            success = notifier.send_error_alert("Some error")
            self.assertFalse(success)

    @patch("app.error_notifier.FreeClient")
    def test_free_api_error_response(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.error.return_value = True
        mock_response.status_code = 402  # Rate limit
        mock_client.send_sms.return_value = mock_response

        success = self.notifier.send_error_alert("Some error")
        self.assertFalse(success)

    @patch("app.error_notifier.FreeClient")
    def test_free_api_network_exception_fails_safely(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.send_sms.side_effect = ConnectionError("Network unreachable")

        # Must not raise an exception
        success = self.notifier.send_error_alert("Some error")
        self.assertFalse(success)

    @patch("app.error_notifier.default_error_notifier")
    def test_notify_error_helper(self, mock_default_notifier):
        mock_default_notifier.send_error_alert.return_value = True
        result = notify_error("General failure", context="Main")
        self.assertTrue(result)
        mock_default_notifier.send_error_alert.assert_called_once_with(
            error_message="General failure", context="Main", exc=None
        )

    def test_log_handler_dispatches_error(self):
        mock_notifier = MagicMock()
        handler = FreeSMSErrorLogHandler(notifier=mock_notifier)
        test_logger = logging.getLogger("test_error_log_handler")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.DEBUG)

        # Info should not trigger handler
        test_logger.info("Normal information")
        mock_notifier.send_error_alert.assert_not_called()

        # Error should trigger handler
        test_logger.error("Something went critically wrong")
        mock_notifier.send_error_alert.assert_called_once()
        args, kwargs = mock_notifier.send_error_alert.call_args
        self.assertIn("Something went critically wrong", kwargs["error_message"])
        self.assertEqual(kwargs["context"], "Log:test_error_log_handler")


if __name__ == "__main__":
    unittest.main()
