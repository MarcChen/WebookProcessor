import logging
import os

from fastapi import FastAPI, Request
from freesms import FreeClient

from app.models import WEBHOOK_PROCESSORS

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


# Healthcheck endpoint
@app.get("/health")
async def healthcheck():
    logger.debug("Healthcheck endpoint called")
    return {"status": "ok"}


# Configure FreeSMS (replace with your credentials)
freesms_client = FreeClient(
    user=os.getenv("FREE_ID"), password=os.getenv("FREE_SECRET")
)

# SMS prefix constant
SMS_PREFIX = "Hook2SMS service : \n"


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logger.debug(f"Received payload: {payload}")

        sms_text = f"No processor found for this event {payload.get('triggerEvent', 'unknown')}."  # noqa: E501
        event_data = {"payload": payload}

        for processor_cls in WEBHOOK_PROCESSORS:
            if processor_cls.can_handle(payload):
                logger.info(f"Using processor: {processor_cls.__name__}")
                event = processor_cls.model_validate(payload)
                sms_text = event.get_sms_message()
                event_data = event.model_dump()
                logger.info("Event processed successfully.")
                logger.debug(f"Processed event data: {event_data}")
                break
        else:
            logger.warning("No suitable processor found for payload.")

        # Add prefix to SMS text
        full_sms_text = f"{SMS_PREFIX}{sms_text}"

        freesms_client.send_sms(text=full_sms_text)
        logger.info("SMS sent successfully")
        logger.debug(f"SMS text: {full_sms_text}")

        return {"status": "SMS sent", "event": event_data}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
