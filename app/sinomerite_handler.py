"""Sinomerite admin-alert SMS route.

Implements the generic relay contract the Sinomerite `process-jobs` worker
speaks (ADR-017) and maps it to Free Mobile:

    POST /sinomerite/sms
    Authorization: Bearer <SINOMERITE_SMS_TOKEN>
    {"message": "...", "sender": ..., "type": "transactional",
     "contact": {...}, "idempotency_key": "sms:<uuid>", "metadata": {...}}

Free Mobile can only text the account owner, so this relay owns the
recipient: Sinomerite sends no phone number, and `sender` (or a legacy `to`)
is accepted but ignored. The body is never logged because `contact` carries PII.

Responses (as the Sinomerite worker interprets them):
    200 {"id": <idempotency_key>}      sent
    409 {"code": "duplicate"}          already sent for this idempotency key
    400 {"code": "invalid_payload"}    malformed body (permanent)
    401 {"code": "unauthorized"}       missing/wrong Bearer token (permanent)
    429 {"code": "rate_limited"}       Free Mobile throttled us (retryable)
    503 {"code": "provider_unavailable"} Free Mobile or config failure (retryable)
"""

import hmac
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from freesms import FreeClient
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_MESSAGE_LENGTH = 480
MAX_IDEMPOTENCY_KEY_LENGTH = 200
# Sinomerite retries for at most ~1 hour; keep keys for a day.
IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60
FREE_TIMEOUT_SECONDS = 8.0


class IdempotencyStore:
    """In-memory, TTL-bounded record of keys already sent.

    Render's free plan restarts the process when idle, which clears this
    store. Sinomerite only retries a row after a failed/unknown result, so a
    restart can at worst cause one duplicate SMS for a retry that straddles it.
    """

    def __init__(self, ttl_seconds: int = IDEMPOTENCY_TTL_SECONDS):
        self._ttl = ttl_seconds
        self._sent: Dict[str, float] = {}
        self._in_flight: set = set()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        expired = [key for key, at in self._sent.items() if now - at > self._ttl]
        for key in expired:
            del self._sent[key]

    def begin(self, key: str) -> bool:
        """Reserve a key. False if it was already sent or is being sent."""
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if key in self._sent or key in self._in_flight:
                return False
            self._in_flight.add(key)
            return True

    def finish(self, key: str, sent: bool) -> None:
        with self._lock:
            self._in_flight.discard(key)
            if sent:
                self._sent[key] = time.monotonic()

    def clear(self) -> None:
        with self._lock:
            self._sent.clear()
            self._in_flight.clear()


idempotency_store = IdempotencyStore()


def _error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code})


def _expected_token() -> Optional[str]:
    token = os.getenv("SINOMERITE_SMS_TOKEN") or os.getenv("SIMPLE_TRIGGER_TOKEN")
    return token.strip() if token and token.strip() else None


def _bearer_token(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _send_free_sms(message: str) -> int:
    """Send through Free Mobile; return its HTTP status (0 on network error)."""
    client = FreeClient(user=os.getenv("FREE_ID"), password=os.getenv("FREE_SECRET"))
    try:
        response = client.send_sms(text=message, timeout=FREE_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.error("Sinomerite SMS: Free Mobile request failed (%s)", type(exc).__name__)
        return 0
    return response.status_code


@router.post("/sinomerite/sms")
async def sinomerite_sms(request: Request) -> JSONResponse:
    expected = _expected_token()
    if expected is None:
        logger.error("Sinomerite SMS: SINOMERITE_SMS_TOKEN is not configured.")
        return _error(503, "provider_unavailable")

    if not os.getenv("FREE_ID") or not os.getenv("FREE_SECRET"):
        logger.error("Sinomerite SMS: FREE_ID/FREE_SECRET are not configured.")
        return _error(503, "provider_unavailable")

    presented = _bearer_token(request)
    if presented is None or not hmac.compare_digest(presented, expected):
        logger.warning("Sinomerite SMS: missing or invalid Bearer token.")
        return _error(401, "unauthorized")

    try:
        payload: Any = await request.json()
    except Exception:
        return _error(400, "invalid_payload")

    if not isinstance(payload, dict):
        return _error(400, "invalid_payload")

    message = payload.get("message")
    key = payload.get("idempotency_key") or request.headers.get("idempotency-key")

    if (
        not isinstance(message, str)
        or not message.strip()
        or len(message) > MAX_MESSAGE_LENGTH
        or not isinstance(key, str)
        or not key.strip()
        or len(key) > MAX_IDEMPOTENCY_KEY_LENGTH
    ):
        return _error(400, "invalid_payload")

    if not idempotency_store.begin(key):
        logger.info("Sinomerite SMS: duplicate idempotency key ignored.")
        return _error(409, "duplicate")

    sent = False
    try:
        status_code = await run_in_threadpool(_send_free_sms, message)
        sent = 200 <= status_code < 300
    finally:
        idempotency_store.finish(key, sent)

    if sent:
        logger.info("Sinomerite SMS: sent.")
        return JSONResponse(status_code=200, content={"id": key})

    logger.error("Sinomerite SMS: Free Mobile returned status %s.", status_code)

    # Free Mobile: 402 = too many SMS sent in a short time.
    if status_code == 402:
        return _error(429, "rate_limited")

    # 400/403 (bad params, service disabled or wrong credentials) and 5xx are
    # relay-side problems the owner must fix; report them as retryable so the
    # alert is not lost while the relay is repaired.
    return _error(503, "provider_unavailable")
