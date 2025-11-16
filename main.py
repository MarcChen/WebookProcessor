import logging
import os

from fastapi import FastAPI, Request

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


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logger.debug(f"Received payload: {payload}")

        for processor_cls in WEBHOOK_PROCESSORS:
            if processor_cls.can_handle(payload):
                logger.info(f"Using processor: {processor_cls.__name__}")
                processor_cls.model_validate(payload)
                processor_cls.process_workflow()
                logger.info("Event processed successfully.")
                logger.debug(f"Processed event data: {payload}")
                return {"status": "SMS sent", "event": payload}

        return {"status": "error", "event": payload}
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
