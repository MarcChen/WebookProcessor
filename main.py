import os
import logging
from fastapi import FastAPI, Request
from app.models import CalWebhookEvent, DummyWebhookEvent, CalTriggerEvent
from freesms import FreeClient

# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Healthcheck endpoint
@app.get("/health")
async def healthcheck():
    logger.debug("Healthcheck endpoint called")
    return {"status": "ok"}

# Configure FreeSMS (replace with your credentials)
freesms_client = FreeClient(user=os.getenv("FREE_ID"), password=os.getenv("FREE_SECRET"))

# SMS prefix constant
SMS_PREFIX = "Hook2SMS service : \n"

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logger.debug(f"Received payload: {payload}")

        event_type = payload.get("triggerEvent")
        logger.info(f"Event type: {event_type}")

        if event_type in CalTriggerEvent.__members__:
            event = CalWebhookEvent.model_validate(payload)
            sms_text = CalWebhookEvent.output_message(event)
            logger.info("Processed CalTriggerEvent")
            logger.debug(f"CalWebhookEvent: {event}")
        else:
            sms_text = payload.get("message", "No message provided")
            event = {"triggerEvent": event_type, "message": sms_text}
            logger.warning(f"Unknown event type: {event_type}")
            logger.debug(f"Fallback event: {event}")

        # Add prefix to SMS text
        sms_text = f"{SMS_PREFIX}{sms_text}"

        freesms_client.send_sms(text=sms_text)
        logger.info("SMS sent successfully")
        logger.debug(f"SMS text: {sms_text}")

        # Use .dict() if event is a pydantic model, else just event
        event_dict = event.dict() if hasattr(event, "dict") else event
        return {"status": "SMS sent", "event": event_dict}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
