import os
from fastapi import FastAPI, Request
from app.models import WebhookEvent, CalWebhookEvent, DummyWebhookEvent
from freesms import FreeClient

app = FastAPI()

# Configure FreeSMS (replace with your credentials)
freesms_client = FreeClient(user=os.getenv("FREE_ID"), password=os.getenv("FREE_SECRET"))

@app.post("/webhook")
async def webhook_listener(request: Request):
    payload = await request.json()

    event_type = payload.get("triggerEvent")
    if event_type == "BOOKING_CREATED":
        event = CalWebhookEvent.model_validate(payload)
        sms_text = CalWebhookEvent.output_message(event)
    elif event_type == "DUMMY_EVENT":
        event = DummyWebhookEvent.model_validate(payload)
        sms_text = DummyWebhookEvent.output_message(event)
    else:
        event = WebhookEvent.model_validate(payload)
        sms_text = WebhookEvent.output_message(event)

    freesms_client.send_sms(text=sms_text)
    return {"status": "SMS sent", "event": event.dict()}

if __name__ == "__main__":
    # You can run: uvicorn main:app --reload
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)