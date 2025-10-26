from fastapi import FastAPI, Request, HTTPException, Query
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


@app.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """Verification endpoint for Meta webhook setup"""
    print("Verification request received:")
    print(f"  hub.mode: {hub_mode}")
    print(f"  hub.challenge: {hub_challenge}")
    print(f"  hub.verify_token: {hub_verify_token}")
    print(f"  Expected token: {VERIFY_TOKEN}")
    
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("✅ Verification successful!")
        return int(hub_challenge)
    
    print("❌ Verification failed!")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_message(request: Request):
    """Receive messages from WhatsApp and echo them back"""
    data = await request.json()

    # Defensive checks
    try:
        value = data["entry"][0]["changes"][0]["value"]
        message = value["messages"][0]
        from_number = message["from"]
        text = message["text"]["body"]
        message_id = message.get("id", "unknown")
        timestamp = message.get("timestamp", "unknown")
        
        # Get sender's profile name if available
        contacts = value.get("contacts", [])
        sender_name = "Unknown"
        if contacts and len(contacts) > 0:
            sender_name = contacts[0].get("profile", {}).get("name", "Unknown")
        
        # Log received message details
        print("\n📱 Message received:")
        print(f"  From: {from_number}")
        print(f"  Name: {sender_name}")
        print(f"  Text: {text}")
        print(f"  Message ID: {message_id}")
        print(f"  Timestamp: {timestamp}")
        
    except KeyError:
        return {"status": "ignored"}

    # Send same text back to sender
    async with httpx.AsyncClient() as client:
        url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {"body": f"You said: {text}"}
        }
        await client.post(url, headers=headers, json=payload)

    return {"status": "message echoed"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8759,
        reload=False
    )



@app.get("/")
def read_root():
    return {"message": "Hello, World!"}