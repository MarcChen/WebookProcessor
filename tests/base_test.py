import unittest
import os
from unittest.mock import MagicMock, patch

# Ensure app modules can be imported
import sys
sys.path.append(os.getcwd())

from app.models import WebhookProcessor

class BaseWebhookTest(unittest.TestCase):
    def setUp(self):
        # Patch environment variables
        self.env_patcher = patch.dict(os.environ, {
            "FREE_ID": "dummy_user",
            "FREE_SECRET": "dummy_pass",
            "SIMPLE_TRIGGER_TOKEN": "valid_token",
            "NOTION_API_TOKEN": "valid_notion_token",
            "NOTION_WEBHOOK_SECRET": "valid_secret", # Added missing secret
            # Add other necessary env vars with dummy values
            "CAL_GITHUB_TOKEN": "dummy", "CAL_GITHUB_REPO": "dummy", "CAL_GITHUB_WORKFLOW_ID": "dummy",
            "STRAVA_GITHUB_TOKEN": "dummy", "STRAVA_GITHUB_REPO": "dummy", "STRAVA_GITHUB_WORKFLOW_ID": "dummy",
            "NOTION_GITHUB_TOKEN": "dummy", "NOTION_GITHUB_REPO": "dummy", "NOTION_GITHUB_WORKFLOW_ID": "dummy",
            "GMAIL_GITHUB_TOKEN": "dummy", "GMAIL_GITHUB_REPO": "dummy", "GMAIL_GITHUB_WORKFLOW_ID": "dummy",
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def run_processor_test(self, processor_cls, payload, expected_sms=None, expected_github=False):
        """
        Generic test runner for processors.

        Args:
            processor_cls: The class of the processor to test.
            payload: The input dictionary payload.
            expected_sms: The expected SMS content string. If None, expects no SMS.
            expected_github: Boolean, whether a GitHub Action trigger is expected.
        """
        # Validate model
        if processor_cls.can_handle(payload):
            processor = processor_cls.model_validate(payload)
        else:
            self.fail(f"{processor_cls.__name__} cannot handle the provided payload.")

        # Mock external calls
        # Patch methods on the class/base class to bypass Pydantic instance constraints
        with patch.object(WebhookProcessor, 'send_sms') as mock_send_sms,              patch.object(WebhookProcessor, 'fire_github_action') as mock_fire_github_action,              patch.object(WebhookProcessor, '_check_cooldown', return_value=True):

            processor.process_workflow(payload)

            # Verify SMS
            if expected_sms:
                mock_send_sms.assert_called()
                # Assuming send_sms implementation uses self.sms_content internally
                # We can also check self.sms_content directly on the processor
                if processor.sms_content:
                    self.assertIn(expected_sms, processor.sms_content)
                else:
                    self.fail("Expected SMS content but none was set.")
            else:
                mock_send_sms.assert_not_called()

            # Verify GitHub Action
            if expected_github:
                mock_fire_github_action.assert_called()
            else:
                mock_fire_github_action.assert_not_called()
