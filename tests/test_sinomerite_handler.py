import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from starlette.requests import Request

from app import sinomerite_handler
from app.sinomerite_handler import idempotency_store, sinomerite_sms
from main import app

TOKEN = "s" * 40


def make_request(body, token=TOKEN, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    headers = [(b"content-type", b"application/json")]
    if token is not None:
        headers.append((b"authorization", f"Bearer {token}".encode()))

    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.disconnect"}
        sent["done"] = True
        return {"type": "http.request", "body": data, "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/sinomerite/sms",
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope, receive)


def body(key="sms:event-1", message="Sinomerite: nouvelle candidature. Admin: https://x.test"):
    return {
        "to": "+33600000000",
        "message": message,
        "sender": "SINOMERITE",
        "type": "transactional",
        "contact": {"id": "t-1", "role": "teacher", "name": "Jean", "email": "j@x.test"},
        "idempotency_key": key,
        "metadata": {"event_id": "event-1", "form": "teacher_recruitment", "source": "process-jobs"},
    }


def decode(response):
    return response.status_code, json.loads(response.body)


class TestSinomeriteSms(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        idempotency_store.clear()
        self.env = patch.dict(
            os.environ,
            {"FREE_ID": "id", "FREE_SECRET": "secret", "SINOMERITE_SMS_TOKEN": TOKEN},
        )
        self.env.start()
        self.send = patch.object(sinomerite_handler, "_send_free_sms", return_value=200)
        self.mock_send = self.send.start()

    def tearDown(self):
        self.send.stop()
        self.env.stop()

    def test_route_is_registered(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/sinomerite/sms", paths)

    async def test_sends_message_and_returns_id(self):
        status, payload = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"id": "sms:event-1"})
        self.mock_send.assert_called_once_with(body()["message"])

    async def test_duplicate_key_returns_409_without_resending(self):
        await sinomerite_sms(make_request(body()))
        status, payload = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual((status, payload), (409, {"code": "duplicate"}))
        self.assertEqual(self.mock_send.call_count, 1)

    async def test_failed_send_can_be_retried_with_same_key(self):
        self.mock_send.return_value = 500
        status, _ = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual(status, 503)
        self.mock_send.return_value = 200
        status, _ = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual(status, 200)

    async def test_rejects_missing_or_wrong_token(self):
        for token in (None, "wrong"):
            status, payload = decode(await sinomerite_sms(make_request(body(), token=token)))
            self.assertEqual((status, payload), (401, {"code": "unauthorized"}))
        self.mock_send.assert_not_called()

    async def test_falls_back_to_simple_trigger_token(self):
        with patch.dict(os.environ, {"SIMPLE_TRIGGER_TOKEN": TOKEN}):
            del os.environ["SINOMERITE_SMS_TOKEN"]
            status, _ = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual(status, 200)

    async def test_missing_server_config_is_retryable(self):
        del os.environ["SINOMERITE_SMS_TOKEN"]
        os.environ.pop("SIMPLE_TRIGGER_TOKEN", None)
        status, payload = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual((status, payload), (503, {"code": "provider_unavailable"}))

    async def test_invalid_payloads_are_400(self):
        cases = [
            make_request(None, raw=b"not json"),
            make_request(["list"]),
            make_request(body(message="")),
            make_request(body(message="x" * 481)),
            make_request(body(key="")),
        ]
        for request in cases:
            status, payload = decode(await sinomerite_sms(request))
            self.assertEqual((status, payload), (400, {"code": "invalid_payload"}))
        self.mock_send.assert_not_called()

    async def test_free_mobile_throttle_maps_to_429(self):
        self.mock_send.return_value = 402
        status, payload = decode(await sinomerite_sms(make_request(body())))
        self.assertEqual((status, payload), (429, {"code": "rate_limited"}))

    def test_network_error_returns_zero(self):
        with patch.object(
            sinomerite_handler.FreeClient, "send_sms", side_effect=requests.ConnectionError()
        ):
            self.send.stop()
            try:
                self.assertEqual(sinomerite_handler._send_free_sms("hi"), 0)
            finally:
                self.mock_send = self.send.start()


if __name__ == "__main__":
    unittest.main()
