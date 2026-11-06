import logging
import os
import time
from typing import Optional

from freesms import FreeClient

logger = logging.getLogger(__name__)

DEFAULT_COOLDOWN_SECONDS = 60
MAX_SMS_LENGTH = 300
SMS_ERROR_PREFIX = "[WebhookProcessor ERROR]\n"


class ErrorNotifier:
    """Manages sending error alerts via Free Mobile SMS with throttling."""

    def __init__(
        self,
        user: Optional[str] = None,
        password: Optional[str] = None,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        prefix: str = SMS_ERROR_PREFIX,
    ):
        self.user = user
        self.password = password
        self.cooldown_seconds = cooldown_seconds
        self.prefix = prefix
        self._last_sent_times: dict[str, float] = {}

    def _get_client(self) -> Optional[FreeClient]:
        user = self.user or os.getenv("FREE_ID")
        password = self.password or os.getenv("FREE_SECRET")
        if not user or not password:
            return None
        return FreeClient(user=user, password=password)

    def send_error_alert(
        self,
        error_message: str,
        context: Optional[str] = None,
        exc: Optional[Exception] = None,
    ) -> bool:
        """
        Send an error SMS alert via Free Mobile SMS API.
        Never raises exceptions; fails gracefully.

        Returns:
            bool: True if SMS was successfully sent, False otherwise.
        """
        try:
            client = self._get_client()
            if not client:
                logger.warning(
                    "FREE_ID or FREE_SECRET is not configured; "
                    "cannot send error SMS alert."
                )
                return False

            # Format the message
            detail = str(exc) if exc else error_message
            if exc and error_message and error_message != str(exc):
                full_desc = f"{error_message}: {exc}"
            else:
                full_desc = detail

            ctx_str = f"[{context}] " if context else ""
            raw_text = f"{self.prefix}{ctx_str}{full_desc}".strip()

            # Truncate if message exceeds maximum length
            if len(raw_text) > MAX_SMS_LENGTH:
                raw_text = raw_text[: MAX_SMS_LENGTH - 3] + "..."

            # Cooldown check per distinct context/error signature to avoid HTTP 402
            # Base cache key on context and exception type or generic prefix
            # to prevent attacker-controlled payload keys from bypassing throttling
            cache_key = f"{context}:{type(exc).__name__ if exc else 'error'}"
            now = time.time()

            # Bounded cache: keep newest 250 items if cache exceeds 500 items
            if len(self._last_sent_times) > 500:
                sorted_entries = sorted(
                    self._last_sent_times.items(), key=lambda item: item[1]
                )
                self._last_sent_times = dict(sorted_entries[-250:])

            last_time = self._last_sent_times.get(cache_key, 0.0)
            if now - last_time < self.cooldown_seconds:
                logger.warning(
                    f"Throttling error SMS for '{cache_key}' "
                    f"(last sent {now - last_time:.1f}s ago; "
                    f"cooldown is {self.cooldown_seconds}s)."
                )
                return False

            response = client.send_sms(raw_text)
            if response.error():
                logger.error(
                    f"Free Mobile SMS API returned error {response.status_code} "
                    "while sending error alert."
                )
                return False

            self._last_sent_times[cache_key] = now
            logger.info("Error alert SMS successfully sent via Free Mobile SMS.")
            return True

        except Exception as e:
            logger.error(
                f"Unexpected exception caught while attempting to send error SMS alert: {e}",  # noqa: E501
                exc_info=True,
            )
            return False

    def clear_cooldown(self) -> None:
        """Clear cached cooldown timestamps (useful for testing)."""
        self._last_sent_times.clear()


# Global default notifier instance
default_error_notifier = ErrorNotifier()


def notify_error(
    error_message: str,
    context: Optional[str] = None,
    exc: Optional[Exception] = None,
) -> bool:
    """Helper to send error alerts using the default ErrorNotifier singleton."""
    return default_error_notifier.send_error_alert(
        error_message=error_message, context=context, exc=exc
    )


class FreeSMSErrorLogHandler(logging.Handler):
    """Logging handler that dispatches ERROR or CRITICAL log records to FreeSMS."""

    def __init__(
        self,
        notifier: Optional[ErrorNotifier] = None,
        level: int = logging.ERROR,
    ):
        super().__init__(level=level)
        self.notifier = notifier or default_error_notifier
        self._is_sending = False

    def emit(self, record: logging.LogRecord) -> None:
        # Avoid recursion if logging happens inside send_error_alert
        if self._is_sending:
            return

        try:
            self._is_sending = True
            msg = self.format(record)
            self.notifier.send_error_alert(
                error_message=msg,
                context=f"Log:{record.name}",
                exc=record.exc_info[1] if record.exc_info else None,
            )
        except Exception:
            self.handleError(record)
        finally:
            self._is_sending = False
