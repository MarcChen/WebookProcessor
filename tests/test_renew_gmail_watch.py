import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.utils.gmail.renew_gmail_watch import renew_gmail_watch


class TestRenewGmailWatch(unittest.TestCase):
    @patch("app.utils.gmail.renew_gmail_watch.notify_error")
    @patch("app.utils.gmail.renew_gmail_watch.GmailSettings")
    def test_renew_gmail_watch_settings_error_alerts_freesms(
        self, mock_settings_cls, mock_notify
    ):
        mock_settings_cls.side_effect = RuntimeError("Config file missing")

        with self.assertRaises(SystemExit):
            renew_gmail_watch()

        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertIn("Failed to load settings", args[0])
        self.assertEqual(kwargs.get("context"), "renew_gmail_watch")

    @patch("app.utils.gmail.renew_gmail_watch.notify_error")
    @patch("app.utils.gmail.renew_gmail_watch.GmailSettings")
    @patch("app.utils.gmail.renew_gmail_watch.get_credentials")
    def test_renew_gmail_watch_api_error_alerts_freesms(
        self, mock_creds, mock_settings_cls, mock_notify
    ):
        mock_settings = MagicMock()
        mock_settings.user_email = "test@example.com"
        mock_settings.pubsub_topic = "test-topic"
        mock_settings.refresh_token = "dummy_token"
        mock_settings_cls.return_value = mock_settings

        mock_creds.side_effect = Exception("Failed Google Auth API")

        with self.assertRaises(SystemExit):
            renew_gmail_watch()

        mock_notify.assert_called_once()
        args, kwargs = mock_notify.call_args
        self.assertIn("Failed to renew Gmail watch", args[0])
        self.assertEqual(kwargs.get("context"), "renew_gmail_watch")

    def test_gmail_settings_supports_service_account_without_oauth(self):
        from app.utils.gmail.renew_gmail_watch import GmailSettings

        with patch.dict(
            os.environ,
            {
                "GMAIL_SERVICE_ACCOUNT_KEY": "dummy_base64_key",
                "GMAIL_USER_EMAIL": "user@example.com",
                "GMAIL_PUBSUB_TOPIC": "projects/my-proj/topics/my-topic",
            },
            clear=True,
        ):
            settings = GmailSettings()
            self.assertEqual(settings.user_email, "user@example.com")
            self.assertEqual(settings.pubsub_topic, "projects/my-proj/topics/my-topic")
            self.assertEqual(settings.service_account_key, "dummy_base64_key")
            self.assertIsNone(settings.client_id)
            self.assertIsNone(settings.client_secret)
            self.assertIsNone(settings.refresh_token)


if __name__ == "__main__":
    unittest.main()
