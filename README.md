# WhatsApp Echo Bot

A minimal WhatsApp bot that echoes back any text message you send to it.

## Setup

### 1. Install Dependencies

Using uv (recommended):
```bash
uv add fastapi uvicorn httpx python-dotenv
```

Or using pip:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Edit `.env` file and add your credentials:

```bash
WHATSAPP_TOKEN=EAA...  # Your permanent access token from Meta Developer Console
PHONE_NUMBER_ID=123456789012345  # Your Phone Number ID from API Setup tab
VERIFY_TOKEN=my_verify_token  # Any string you choose (must match webhook config)
```

### 3. Run the Bot

```bash
uv run main.py
```

Or without uv:
```bash
uvicorn main:app --reload --port 8759
```

### 4. Expose Your Local Server

Use serveo.net (no installation or signup required):
```bash
ssh -R 80:localhost:8759 serveo.net
```

Copy the `https://xxxxx.serveo.net` URL from the output.

### 5. Configure Webhook in Meta Dashboard

1. Go to Meta Developer Console → Your App → WhatsApp → Configuration
2. Set **Callback URL**: `https://xxxxx.serveo.net/webhook`
3. Set **Verify token**: `my_verify_token` (same as in your .env)
4. Subscribe to **messages** events
5. Click "Verify and Save"

### 6. Test It!

Send a message to your WhatsApp test number from your phone.
The bot will reply with: "You said: <your message>"

## How It Works

1. **GET /webhook** - Verifies your webhook with Meta (one-time setup)
2. **POST /webhook** - Receives incoming messages and sends echo responses

## Troubleshooting

- Make sure your recipient number is added in the Meta Dashboard "To" field
- Check that serveo.net tunnel is still running (connection may drop occasionally)
- Verify all environment variables are set correctly in `.env` file
- Check server logs for any errors
- If serveo.net disconnects, just run the ssh command again to get a new URL

