from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import requests
from pydantic import Field

from app.models import (
    DEFAULT_REQUEST_TIMEOUT,
    GitHubSettings,
    WebhookProcessor,
    create_github_settings,
)
from tests.base_test import BaseWebhookTest


class DummyProcessor(WebhookProcessor):
    name: str = "dummy"
    secret_field: str = Field(default="classified", exclude=True)

    @classmethod
    def can_handle(cls, payload):
        return isinstance(payload, dict) and payload.get("type") == "dummy"

    def should_enable_workflow(self, payload):
        self.enable_workflow = True


class TestWebhookProcessorBase(BaseWebhookTest):
    def test_create_github_settings_builder(self):
        settings_cls = create_github_settings(
            env_prefix="CAL_", cooldown=timedelta(minutes=1)
        )
        settings = settings_cls()
        self.assertEqual(settings.repo, "dummy")
        self.assertEqual(settings.token, "dummy")
        self.assertEqual(settings.cooldown, timedelta(minutes=1))

    @patch("app.models.requests.get")
    def test_check_cooldown_active(self, mock_get):
        processor = DummyProcessor()
        settings_cls = create_github_settings("CAL_", cooldown=timedelta(minutes=5))
        processor.github_settings = settings_cls()

        # Last run 1 minute ago (cooldown is 5 minutes)
        one_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workflow_runs": [{"created_at": one_min_ago}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.assertFalse(processor._check_cooldown())
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args[1]["timeout"], DEFAULT_REQUEST_TIMEOUT)

    @patch("app.models.requests.get")
    def test_check_cooldown_expired(self, mock_get):
        processor = DummyProcessor()
        settings_cls = create_github_settings("CAL_", cooldown=timedelta(minutes=5))
        processor.github_settings = settings_cls()

        # Last run 10 minutes ago
        ten_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workflow_runs": [{"created_at": ten_min_ago}]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        self.assertTrue(processor._check_cooldown())

    @patch("app.models.requests.get")
    def test_check_cooldown_github_error_fails_closed(self, mock_get):
        processor = DummyProcessor()
        settings_cls = create_github_settings("CAL_")
        processor.github_settings = settings_cls()

        # Simulating GitHub 403 Rate limit or network failure
        mock_get.side_effect = requests.exceptions.RequestException("Rate limited")

        self.assertFalse(processor._check_cooldown())

    @patch("app.models.requests.post")
    @patch.object(WebhookProcessor, "_check_cooldown", return_value=True)
    def test_fire_github_action(self, mock_cooldown, mock_post):
        processor = DummyProcessor()
        processor.github_settings = GitHubSettings(
            token="gh_token",
            repo="org/repo",
            workflow_id="wf.yml",
            ref="main",
            inputs={"key": "val"},
        )

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        processor.fire_github_action()

        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args[1]["timeout"], DEFAULT_REQUEST_TIMEOUT)
        self.assertEqual(
            mock_post.call_args[1]["json"], {"ref": "main", "inputs": {"key": "val"}}
        )

    def test_send_sms_gracefully_handles_empty_content(self):
        processor = DummyProcessor()
        processor.sms_content = None
        # Should not raise exception
        processor.send_sms()

    def test_send_sms_gracefully_handles_client_exception(self):
        processor = DummyProcessor()
        processor.sms_content = "Hello there"
        mock_client = MagicMock()
        mock_client.send_sms.side_effect = ConnectionError("SMS gateway down")
        processor.freesms_client = mock_client

        # Must not raise an exception
        processor.send_sms()

    def test_process_workflow_serialization_excludes_private_fields(self):
        processor = DummyProcessor()
        processor.sms_content = None
        res = processor.process_workflow({"type": "dummy"})

        self.assertEqual(res.status_code, 200)
        import json

        data = json.loads(res.body.decode("utf-8"))
        self.assertIn("name", data["event"])
        self.assertNotIn("secret_field", data["event"])
        self.assertNotIn("freesms_client", data["event"])

    @patch.object(WebhookProcessor, "fire_github_action")
    def test_process_workflow_handles_github_dispatch_failure_without_crash(
        self, mock_fire
    ):
        mock_fire.side_effect = RuntimeError("GitHub API 500 error")

        processor = DummyProcessor()
        processor.sms_content = "Notification message"
        processor.github_settings = GitHubSettings(
            token="gh_token",
            repo="org/repo",
            workflow_id="wf.yml",
        )

        with patch.object(WebhookProcessor, "send_sms"):
            res = processor.process_workflow({"type": "dummy"})

        self.assertEqual(res.status_code, 502)
        import json

        data = json.loads(res.body.decode("utf-8"))
        self.assertIn("GitHub action dispatch failed", data["status"])
