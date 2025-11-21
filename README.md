# WhatsApp Bot Backend

A scalable WhatsApp bot backend built with FastAPI, SQLModel, Pydantic, and PydanticAI.

## Features

- 🤖 **AI-Powered**: Uses PydanticAI for intelligent conversation handling
- 🔧 **Tool System**: Modular tool architecture with subscription-based access control
- 💬 **WhatsApp Integration**: Full webhook support for WhatsApp Business API
- 📊 **Admin Panel**: RESTful API endpoints for user and tool management
- 🗄️ **Database**: SQLModel for clean, type-safe database operations
- 🔐 **Subscription Tiers**: Free, Plus, and Pro tiers with different tool access

## Project Structure

```
app/
├── main.py                  # FastAPI application entry point
├── core/
│   ├── config.py           # Application settings
│   └── logging.py          # Logging configuration
├── db/
│   ├── session.py          # Database session management
│   └── init_db.py          # Database initialization
├── models/
│   ├── user.py             # User model
│   ├── conversation.py     # Conversation model
│   ├── message.py          # Message model
│   └── tool.py             # Tool configuration model
├── schemas/
│   └── admin.py            # Admin API schemas
├── tools/
│   ├── base.py             # BaseTool abstract class
│   ├── registry.py         # Tool registry
│   └── builtin/
│       ├── my_tool.py      # Example tool
│       └── calculator.py   # Calculator tool
├── services/
│   ├── whatsapp_service.py # WhatsApp webhook handler
│   ├── whatsapp_client.py  # WhatsApp API client
│   ├── conversation_service.py
│   ├── subscription_service.py
│   └── ai_router.py        # AI response generation
├── agents/
│   └── whatsapp_agent.py   # PydanticAI agent builder
├── api/
│   └── routes/
│       ├── whatsapp.py     # WhatsApp webhook endpoints
│       ├── admin.py        # Admin API endpoints
│       └── health.py       # Health check
└── utils/
    └── auth.py             # Admin authentication
```

## Installation

1. **Install dependencies using uv**:
```bash
uv sync
```

2. **Set up environment variables**:
```bash
cp env.example .env
```

3. **Configure your `.env` file** with the following variables:

```bash
# Application Settings
APP_NAME=WhatsApp Bot
DEBUG=False

# Database (SQLite by default, use PostgreSQL for production)
DATABASE_URL=sqlite:///./whatsapp_bot.db

# WhatsApp Business API Configuration
WHATSAPP_VERIFY_TOKEN=your_unique_verify_token_here
WHATSAPP_TOKEN=your_whatsapp_business_api_access_token
WHATSAPP_PHONE_ID=your_whatsapp_phone_number_id

# Admin Panel Authentication
ADMIN_API_KEY=your_secure_admin_api_key_here

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here
```

**Environment Variables Explained:**

- **APP_NAME**: Your application name (cosmetic)
- **DEBUG**: Set to `True` for development, `False` for production
- **DATABASE_URL**: Database connection string (SQLite or PostgreSQL)
- **WHATSAPP_VERIFY_TOKEN**: A secret token you create for webhook verification (any random string)
- **WHATSAPP_TOKEN**: Access token from WhatsApp Business API dashboard
- **WHATSAPP_PHONE_ID**: Phone number ID from WhatsApp Business API dashboard
- **ADMIN_API_KEY**: Secret key for accessing admin endpoints (create a strong random string)
- **OPENAI_API_KEY**: Your OpenAI API key (get from https://platform.openai.com/api-keys)

## Quick Start

Run the application with automatic public URL setup:

```bash
./start.sh
```

This script will:
- Check your `.env` configuration
- Install dependencies
- Start the FastAPI server
- Create a public URL using serveo.net for WhatsApp webhook

## Manual Start

**Development mode with auto-reload**:
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Production mode**:
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Expose Your Local Server

After running the app, expose it to the internet using **serveo.net** (no installation required):

```bash
ssh -R 80:localhost:7349 serveo.net
```

You'll get a public URL like: `https://random-name.serveo.net`

**Use this URL for your WhatsApp webhook!**

> **Note**: The `start.sh` script automatically tries multiple tunnel options:
> 1. **serveo.net** (first attempt)
> 2. **localtunnel** (`lt`) - if serveo fails
> 3. **ngrok** - if localtunnel fails or isn't installed

## API Documentation

Once running, visit:
- **Interactive docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc
- **Health check**: http://localhost:8000/health

## WhatsApp Webhook Setup

1. After running the app, expose it with serveo.net:
```bash
ssh -R 80:localhost:8000 serveo.net
```

2. Copy the public URL (e.g., `https://your-url.serveo.net`)

3. Configure webhook in your WhatsApp Business API dashboard:
   - **Callback URL**: `https://your-url.serveo.net/webhook`
   - **Verify Token**: Same as `WHATSAPP_VERIFY_TOKEN` from your `.env` file
   - **Webhook fields**: Select `messages`

4. Test by sending a WhatsApp message to your bot!

## Admin Panel

Open `admin/index.html` in your browser to access the admin panel.

**Configuration:**
- **API Base URL**: `http://localhost:8000` (or your public serveo.net URL)
- **Admin API Key**: Same as `ADMIN_API_KEY` from your `.env` file

**Admin Panel Features:**
- 📊 Dashboard with statistics
- 👥 User management (view, activate/deactivate, change subscription)
- 🛠️ Tool configuration (enable/disable, set minimum tier)
- ⚙️ API configuration

## Admin API Endpoints

All admin endpoints require the `X-Admin-Key` header with your `ADMIN_API_KEY`.

### Users
- `GET /admin/users` - List all users
- `GET /admin/users/{user_id}` - Get user details
- `PATCH /admin/users/{user_id}/subscription` - Update subscription tier
- `PATCH /admin/users/{user_id}/status` - Activate/deactivate user
- `GET /admin/users/{user_id}/conversations` - Get user conversations
- `GET /admin/users/{user_id}/messages` - Get user messages

### Tools
- `GET /admin/tools` - List all tools
- `GET /admin/tools/{name}` - Get tool configuration
- `PATCH /admin/tools/{name}` - Update tool settings

### Stats
- `GET /admin/stats` - Get system statistics

### Example Admin API Call
```bash
curl -X GET "http://localhost:8000/admin/users" \
  -H "X-Admin-Key: your_admin_api_key"
```

## Adding a New Tool

1. **Create a new tool file** in `app/tools/builtin/`:

```python
# app/tools/builtin/my_new_tool.py
from typing import Optional, Any
from app.tools.base import BaseTool

class MyNewTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="my_new_tool",
            description="Description of what the tool does",
            capabilities="Detailed capabilities",
            enabled=enabled,
            min_tier="free",  # or "plus", "pro"
        )
    
    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        # Your tool logic here
        return f"Result: {text}"
```

2. **Register the tool** in `app/tools/registry.py`:

```python
from app.tools.builtin.my_new_tool import MyNewTool

def init_tools():
    for tool in [
        MyTool(),
        CalculatorTool(),
        MyNewTool(),  # Add your new tool
    ]:
        _TOOL_INSTANCES[tool.name] = tool
```

3. **Restart the application** - The tool is now available!

## Subscription Tiers

- **Free**: Basic access to free-tier tools
- **Plus**: Access to plus-tier and below tools
- **Pro**: Access to all tools

Tools are automatically filtered based on user subscription tier.

## Database

The application uses SQLite by default. To use PostgreSQL:

1. Update `DATABASE_URL` in `.env`:
```
DATABASE_URL=postgresql://user:password@localhost/dbname
```

2. Install PostgreSQL driver:
```bash
uv add psycopg2-binary
```

## Development

**Run with auto-reload**:
```bash
uv run uvicorn app.main:app --reload
```

**Add new packages**:
```bash
uv add package-name
```

## Architecture Highlights

### Tool System
- **BaseTool**: Abstract base class for all tools
- **is_valid_for_user()**: Automatic subscription validation
- **Registry**: Central tool management and user-based filtering

### AI Agent
- Built with PydanticAI
- Dynamic tool assignment based on user tier
- Conversation history management

### Services Layer
- **whatsapp_service**: Webhook processing
- **conversation_service**: Conversation management
- **subscription_service**: Usage tracking (mock implementation)
- **ai_router**: AI response generation

## Scalability

This architecture is designed for scale:
- **Stateless**: FastAPI app can run multiple instances
- **Database-backed**: All state in PostgreSQL/SQLite
- **Modular tools**: Easy to split into microservices
- **Subscription-aware**: Built-in tier management

## Future Enhancements

- [ ] Real payment integration (Stripe, PayPal)
- [ ] Usage tracking and quotas
- [ ] Image/document/audio message support
- [ ] Redis for rate limiting and caching
- [ ] Tool usage analytics
- [ ] WebSocket support for real-time updates
- [ ] Admin web panel (HTML/CSS/JS)

## License

MIT

## Support

For issues and questions, please open an issue on GitHub.
