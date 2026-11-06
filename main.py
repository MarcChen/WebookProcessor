import inspect
import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from app.error_notifier import notify_error
from app.notion_handler import NotionWebhookProcessor
from app.registry import WEBHOOK_PROCESSORS

# Logging setup
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions across all endpoints and alert via FreeSMS."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    await run_in_threadpool(
        notify_error,
        f"Unhandled exception on {request.method} {request.url.path}",
        context="FastAPI",
        exc=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"status": "error", "detail": str(exc)},
    )


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
            if isinstance(response_data, Response):
                return response_data
            return JSONResponse(content=response_data)

    logger.warning(f"No processor found for verification request: {params}")
    return Response(
        content="No suitable processor found for verification",
        status_code=status.HTTP_400_BAD_REQUEST,
    )


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        body_call = request.body() if hasattr(request, "body") else b""
        raw_body = (
            (await body_call)
            if inspect.isawaitable(body_call)
            else (body_call if isinstance(body_call, bytes) else b"")
        )

        try:
            json_call = request.json() if hasattr(request, "json") else {}
            payload = (await json_call) if inspect.isawaitable(json_call) else json_call
        except Exception as json_err:
            logger.warning(
                f"Malformed or non-JSON webhook payload received: {json_err}"
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"status": "error", "message": "Invalid JSON payload"},
            )

        logger.debug(f"Received payload: {payload}")

        for processor_cls in WEBHOOK_PROCESSORS:
            logger.debug(f"Checking processor: {processor_cls.__name__}")
            if processor_cls.can_handle(payload):
                logger.info(f"Using processor: {processor_cls.__name__}")

                # Optional Notion HMAC signature verification if configured
                if processor_cls is NotionWebhookProcessor:
                    notion_secret = os.getenv("NOTION_WEBHOOK_SECRET")
                    if notion_secret:
                        signature_header = request.headers.get(
                            "X-Notion-Signature"
                        ) or request.headers.get("x-notion-signature")
                        if (
                            not signature_header
                            or not NotionWebhookProcessor.verify_signature(
                                raw_body, signature_header, notion_secret
                            )
                        ):
                            logger.warning(
                                "Missing or invalid Notion signature header received."
                            )
                            return JSONResponse(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                content={
                                    "status": "error",
                                    "message": "Missing or invalid Notion signature",
                                },
                            )

                processor = processor_cls.model_validate(payload)
                response = await run_in_threadpool(processor.process_workflow, payload)
                logger.info("Event processed successfully.")
                logger.debug(f"Processed event data: {payload}")
                return response

            verification_res = processor_cls.handle_verification(payload)
            if verification_res is not None:
                logger.info(
                    f"Handled verification using processor: {processor_cls.__name__}"
                )
                if isinstance(verification_res, Response):
                    return verification_res
                return JSONResponse(content=verification_res)

        logger.error(f"No processor found for payload: {payload}")
        payload_keys = (
            list(payload.keys())
            if isinstance(payload, dict)
            else type(payload).__name__
        )
        await run_in_threadpool(
            notify_error,
            f"No processor found for payload (keys: {payload_keys})",
            context="POST /webhook",
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "message": "No suitable processor found"},
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        await run_in_threadpool(
            notify_error,
            f"Error processing webhook: {e}",
            context="POST /webhook",
            exc=e,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "detail": str(e)},
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
