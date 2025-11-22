import logging
import os

from fastapi import FastAPI, Request, Response, status

from app.registry import WEBHOOK_PROCESSORS

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


# Healthcheck endpoint
@app.get("/health")
async def healthcheck():
    logger.debug("Healthcheck endpoint called")
    return {"status": "ok"}


@app.get("/webhook")
async def webhook_verification(request: Request):
    """Handle webhook verification challenges."""
    params = dict(request.query_params)
    logger.debug(f"Received verification request with params: {params}")

    for processor_cls in WEBHOOK_PROCESSORS:
        response_data = processor_cls.handle_verification(params)
        if response_data is not None:
            logger.info(
                f"Handled verification using processor: {processor_cls.__name__}"
            )
            return response_data

    logger.warning(f"No processor found for verification request: {params}")
    return Response(
        content="No suitable processor found for verification",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logger.debug(f"Received payload: {payload}")

        for processor_cls in WEBHOOK_PROCESSORS:
            logger.debug(f"Checking processor: {processor_cls.__name__}")
            if processor_cls.can_handle(payload):
                logger.info(f"Using processor: {processor_cls.__name__}")
                processor = processor_cls.model_validate(payload)
                response = processor.process_workflow(payload)
                logger.info("Event processed successfully.")
                logger.debug(f"Processed event data: {payload}")
                return response
            elif processor_cls.handle_verification(payload) is not None:
                logger.info(
                    f"Handled verification using processor: {processor_cls.__name__}"
                )
                response = processor_cls.handle_verification(payload)
                return response

        logger.error(f"No processor found for payload: {payload}")
        return Response(
            content='{"status": "error", "message": "No suitable processor found"}',
            status_code=status.HTTP_400_BAD_REQUEST,
            media_type="application/json",
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return Response(
            content=f'{{"status": "error", "detail": "{str(e)}"}}',
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            media_type="application/json",
        )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level=logging.DEBUG,
    )
