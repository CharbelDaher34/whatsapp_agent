# WhatsApp Bot Backend

A production-leaning WhatsApp assistant built on FastAPI, SQLModel,
PydanticAI, and ARQ. Plan-based (Free / Pro / Max), multi-modal, with
per-user memory, OAuth integrations (Gmail), an admin panel, and a public
web app for sign-up / billing.

> If you're an AI agent, see **[CLAUDE.md](./CLAUDE.md)** for codebase
> navigation, conventions, and common-task recipes.

---

## Table of contents
1. [What you get](#what-you-get)
2. [Architecture at a glance](#architecture-at-a-glance)
3. [Prerequisites](#prerequisites)
4. [Quick start (local, 5 minutes)](#quick-start-local-5-minutes)
5. [Production setup](#production-setup)
6. [Configuring WhatsApp Cloud API](#configuring-whatsapp-cloud-api)
7. [Configuring Stripe (optional)](#configuring-stripe-optional)
8. [Configuring Google OAuth (Gmail)](#configuring-google-oauth-gmail)
9. [Plan tier matrix](#plan-tier-matrix)
10. [WhatsApp slash commands](#whatsapp-slash-commands)
11. [Adding new features](#adding-new-features)
    - [Add a new tool (Python)](#add-a-new-tool-python)
    - [Add a new plugin (JSON manifest)](#add-a-new-plugin-json-manifest)
    - [Add a new integration (OAuth)](#add-a-new-integration-oauth)
    - [Add a new WhatsApp input type](#add-a-new-whatsapp-input-type)
12. [Running tests](#running-tests)
13. [Troubleshooting](#troubleshooting)
14. [Project layout](#project-layout)

---

## What you get

- **AI-Powered chat**: Plan-aware PydanticAI agent (model, tools and
  history depth all scale with the user's tier).
- **Full WhatsApp coverage**: text, image, video, audio, voice notes,
  document, sticker, location, contacts, interactive (button / list),
  template buttons, reactions.
- **Memory**: facts, preferences, and lazy summaries persisted per user;
  the agent pre-loads the most relevant memories every turn.
- **Integrations**: per-user OAuth records (Gmail today; the model is a
  drop-in template for more providers).
- **Tools / plugins**:
  - Drop a Python file in `app/tools/builtin/` or
    `app/tools/integrations/` → tool auto-registered.
  - Drop a JSON file in `app/tools/manifests/` → external HTTP tool
    auto-registered.
- **Plans**: Free / Pro / Max with daily and monthly message quotas,
  enforced before any AI tokens are spent.
- **Web app**: landing, pricing, phone+OTP login, dashboard with usage,
  Stripe checkout (with a mock fallback for dev).
- **Admin**: REST endpoints under `/admin/*` and an HTML panel at
  `/admin-ui`.
- **Operationally sound**: ARQ Redis worker for webhook processing,
  per-user message coalescing, rate limit middleware, async SQLModel.

---

## Architecture at a glance

```
       ┌──────────────────┐
       │ WhatsApp Cloud   │
       │      API         │
       └────────┬─────────┘
                │ webhook
                ▼
   ┌──────────────────────┐    ┌──────────────────┐
   │  /webhook (FastAPI)  │───▶│  ARQ worker      │
   │  validates + enqueue │    │  process_webhook │
   └──────────────────────┘    └────────┬─────────┘
                                        │
                                        ▼
                               ┌────────────────────┐
                               │ orchestrator.py    │
                               │  parse → quota →   │
                               │  command? → handle │
                               │  → agent_runner    │
                               │  → send reply      │
                               └────────┬───────────┘
                                        │
                ┌───────────────────────┼─────────────────────────┐
                ▼                       ▼                         ▼
        ┌────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
        │ Memory service │   │ Subscription / quota│   │ Tool registry    │
        │ (DB)           │   │ (UsageRecord, DB)   │   │ (auto-discovery) │
        └────────────────┘   └─────────────────────┘   └──────────────────┘

  Web app (FastAPI, Jinja templates):
    /            landing
    /pricing     plans
    /login       phone+OTP via WhatsApp → JWT cookie
    /dashboard   usage, integrations, memory
    /admin-ui    admin panel (X-Admin-Key)
    /checkout/*  Stripe (or mock) checkout
    /integrations/google/* OAuth flow
    /stripe/webhook         applies plan changes
```

Storage:
- **Postgres / SQLite** — users, conversations, messages, memory,
  integrations, usage records, tool configs.
- **Redis** — message queue (ARQ), per-user request lock, OTP codes,
  per-user current image path.

---

## Prerequisites

| What | Version | Notes |
|---|---|---|
| Python | 3.13+ | `uv` will install it for you |
| [uv](https://github.com/astral-sh/uv) | latest | dependency + venv manager |
| Redis | 6+ | required (queue, OTP, image cache) |
| Postgres | 14+ | optional in dev (SQLite default) |
| WhatsApp Business Account | — | Cloud API access; see below |
| OpenAI API key | — | required for the AI agent |
| Public HTTPS URL | — | required for WhatsApp webhook (use ngrok in dev) |

Optional:
- Stripe account (real billing — without it, the app uses a mock checkout).
- Google Cloud OAuth client (for Gmail integration).
- Google Gemini API key (for image generation/editing).

---

## Quick start (local, 5 minutes)

> This walks you through the simplest possible local setup: SQLite, Redis,
> and ngrok for the WhatsApp webhook. No Stripe, no Gmail.

### 1. Clone and install

```bash
git clone <your-fork>.git
cd whatsapp_agent
uv sync
```

### 2. Start Redis

```bash
# macOS
brew services start redis
# Linux
sudo systemctl start redis
# Or via Docker
docker run -d --name redis -p 6379:6379 redis:7
```

### 3. Configure your `.env`

```bash
cp env.example .env
$EDITOR .env
```

At minimum, set:
- `WHATSAPP_VERIFY_TOKEN` — any random string you'll paste into the Meta
  dashboard later.
- `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID` — from Meta dashboard
  (see [Configuring WhatsApp Cloud API](#configuring-whatsapp-cloud-api)).
- `OPENAI_API_KEY` — from <https://platform.openai.com/api-keys>.
- `ADMIN_API_KEY` — any strong random string for `/admin/*`.
- `JWT_SECRET` — any long random string for the web auth cookie.
- (Optional) `WHATSAPP_APP_SECRET` for production-grade signature
  verification.
- (Optional) `GOOGLE_CLOUD_API_KEY` to enable image generation tools.

### 4. Initialize the database

The app auto-creates tables on first start, so for SQLite you don't need to
do anything. To verify:

```bash
uv run python -c "from app.db.init_db import init_db; init_db()"
```

### 5. Start the API and worker (two terminals)

```bash
# Terminal A — API
uv run uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal B — ARQ worker (processes webhook messages)
uv run python -m app.queue.worker
```

You should see:
- `🔧 Tool registry: 11 tools — [...]`
- `Application startup complete.`

### 6. Expose your local server with ngrok

```bash
ngrok http 8000
```

Copy the `https://...ngrok-free.app` URL. You'll paste it into the Meta
dashboard.

### 7. Configure the WhatsApp webhook

In Meta Developer Console → your WhatsApp app → Webhooks:
- **Callback URL**: `<ngrok-url>/webhook`
- **Verify token**: must equal your `WHATSAPP_VERIFY_TOKEN`.
- Subscribe the field: **messages**.

Then, on the WhatsApp Business Platform tab, send yourself a test message
or message your test phone number — the bot should respond.

### 8. Try the slash commands

In WhatsApp, send to the bot:
- `/help` — list commands
- `/plan` — your current plan
- `/usage` — today + month-to-date usage
- `/upgrade` — get an upgrade list

### 9. Open the web app

Visit <http://localhost:8000>:
- `/pricing` — plans
- `/login` — phone+OTP via WhatsApp
- `/dashboard` — usage, integrations, memory
- `/admin-ui` — admin panel (paste your `ADMIN_API_KEY`)
- `/docs` — OpenAPI / Swagger

---

## Production setup

### Database

Switch to Postgres:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/whatsapp_bot
```

We use Alembic for migrations:

```bash
uv run alembic upgrade head
```

(For a fresh DB, the app will also create tables on first start — but
prefer migrations in production.)

### Required configuration changes

| Setting | Why |
|---|---|
| `DEBUG=False` | turns off the OTP code echo in the login flash |
| `WHATSAPP_APP_SECRET=…` | enables HMAC signature verification on webhooks |
| `JWT_SECRET=<long random>` | signs session cookies AND obfuscates stored OAuth tokens |
| `ADMIN_API_KEY=<long random>` | guards `/admin/*` and `/admin-ui` |
| `WEB_BASE_URL=https://your.domain` | drives OAuth redirects, checkout success URLs, etc. |

### Process model

Run two processes (e.g. via systemd, Docker Compose, Fly machines, etc.):

```bash
# API
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Worker
uv run python -m app.queue.worker
```

The webhook endpoint enqueues into Redis; the worker processes off the
queue. If Redis is unreachable the API falls back to processing inline so
you don't drop messages.

### Reverse proxy

Front the API with HTTPS (Caddy / nginx / Cloudflare). WhatsApp will only
hit an HTTPS endpoint.

### Docker (optional)

```bash
cp env.docker.example .env
docker compose up -d
```

This brings up Postgres, Redis, the API, and the worker.

---

## Configuring WhatsApp Cloud API

1. Go to <https://developers.facebook.com/apps/> → create a Business app.
2. Add the **WhatsApp** product. You'll get a sandbox phone number for free.
3. From the WhatsApp → Getting Started page:
   - Copy the **temporary access token** → paste as `WHATSAPP_TOKEN`.
     (For prod, generate a permanent token via System Users.)
   - Copy the **Phone number ID** → paste as `WHATSAPP_PHONE_ID`.
4. App settings → Basic → reveal **App secret** → paste as
   `WHATSAPP_APP_SECRET`.
5. WhatsApp → Configuration → Webhooks:
   - Callback URL: `https://your-domain/webhook` (or ngrok URL in dev).
   - Verify token: same string as `WHATSAPP_VERIFY_TOKEN`.
   - Subscribe to the `messages` field.
6. Add your phone number to the test list (sandbox apps only).

---

## Configuring Stripe (optional)

Without Stripe, the app runs in **mock billing mode**: clicking "Upgrade"
calls `/checkout/mock-success`, which upgrades the user instantly without
charging. This is fine for dev and screencasts, NOT for production.

For real billing:

1. Stripe Dashboard → API keys → copy the **secret key** to
   `STRIPE_SECRET_KEY`.
2. Create two recurring **Prices** (one for Pro, one for Max). Copy their
   IDs (`price_…`) into `STRIPE_PRICE_PRO` and `STRIPE_PRICE_MAX`.
3. Add a webhook endpoint pointing at
   `https://your-domain/stripe/webhook` and listening for at least:
   - `checkout.session.completed`
   - `customer.subscription.deleted`
   Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.

The app verifies the Stripe signature on every webhook and applies plan
changes via `app/web/stripe_webhook.py`.

---

## Configuring Google OAuth (Gmail)

1. Google Cloud Console → APIs & Services → Credentials → **Create
   credentials → OAuth client ID** (Web application).
2. Add an authorized redirect URI:
   `https://your-domain/integrations/google/callback`
3. Enable the **Gmail API** for your project.
4. Paste the client id/secret into `GOOGLE_OAUTH_CLIENT_ID` /
   `GOOGLE_OAUTH_CLIENT_SECRET`.
5. (Optional) Override the redirect URI explicitly with
   `GOOGLE_OAUTH_REDIRECT_URI`.

Users connect Gmail from `/dashboard` (Pro/Max only). The
`gmail_search` tool then becomes usable from chat — the agent will say
"Gmail isn't connected" if the user hasn't done step (3) yet.

---

## Plan tier matrix

| Capability | Free | Pro | Max |
|---|---|---|---|
| Messages / day | 30 | 500 | unlimited |
| Messages / month | 300 | 10 000 | unlimited |
| Model | gpt-4o-mini | gpt-4o | gpt-4o |
| Conversation history | last 10 | last 30 | last 80 |
| Image generation (`text_to_image`) | ❌ | ✅ | ✅ |
| Image editing (`image_to_image`) | ❌ | ✅ | ✅ |
| Voice transcription (Whisper) | ❌ | ✅ | ✅ |
| Document analysis (PDF/text) | ❌ | ✅ | ✅ |
| Memory (`remember` / `recall` / `forget`) | ✅ | ✅ | ✅ |
| Lazy summarization | ❌ | ✅ | ✅ |
| Gmail search | ❌ | ✅ | ✅ |
| Weather plugin | ✅ | ✅ | ✅ |
| `ask_buttons` / `ask_list` (interactive Q→A) | ✅ | ✅ | ✅ |

The full source of truth is `app/core/plans.py`. Edit it to tweak tiers.

---

## WhatsApp slash commands

Type any of these directly in WhatsApp:

| Command | Aliases | What it does |
|---|---|---|
| `/help` | `menu`, `commands` | List every shortcut |
| `/plan` | `myplan`, `status` | Show current plan + capabilities |
| `/usage` | `quota` | Today + month-to-date usage |
| `/upgrade` | `buy`, `subscribe` | Send an upgrade list with checkout links |
| `/pro` | — | Direct link to Pro checkout |
| `/max` | — | Direct link to Max checkout |
| `/memory` | `memories` | List what the bot remembers about you |
| `/forget <topic>` | — | Forget memories matching `<topic>` |
| `/forgetall` | — | Wipe all memory |
| `/integrations` | `connect` | Link to dashboard to connect Gmail etc. |

Source: `app/services/whatsapp/commands.py`.

---

## Adding new features

### Add a new tool (Python)

Drop a file in `app/tools/builtin/` whose top-level class extends
`BaseTool`. The registry auto-discovers it on the next startup.

```python
# app/tools/builtin/coin_flip.py
from typing import Any, Optional
import secrets
from app.tools.base import BaseTool


class CoinFlipTool(BaseTool):
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="coin_flip",
            description="Flip a coin.",
            capabilities="No input needed. Returns 'heads' or 'tails'.",
            enabled=enabled,
            min_tier="free",
        )

    async def process(self, text: str, **kwargs: Any) -> Optional[str]:
        return secrets.choice(["heads", "tails"])
```

Then add `"coin_flip"` to the `tools={…}` set in any plan you want
exposed in `app/core/plans.py`. Restart — done.

### Add a new plugin (JSON manifest)

For external HTTP-only tools, no Python required. Drop a manifest in
`app/tools/manifests/`:

```json
// app/tools/manifests/cat_facts.json
{
  "name": "cat_facts",
  "description": "Random cat fact.",
  "capabilities": "No input. Returns one fact.",
  "min_tier": "free",
  "method": "GET",
  "url": "https://catfact.ninja/fact",
  "extract": "fact"
}
```

Whitelist the name in `app/core/plans.py` and restart. The full manifest
schema is documented in `app/tools/plugin.py`.

### Add a new integration (OAuth)

Three files:

1. **OAuth helper** in `app/services/integration_service.py`
   (extend `upsert_<provider>` and a `get_fresh_<provider>_access_token`).
2. **OAuth web routes** in `app/web/integrations.py`
   (`/integrations/<provider>/connect` + `…/callback`).
3. **A tool** under `app/tools/integrations/<provider>.py` that uses
   `get_active(session, user_id, "<provider>")` and the fresh access
   token.

The `Integration` SQLModel already supports any provider name. The Gmail
integration (`app/tools/integrations/gmail.py`,
`app/web/integrations.py`) is the canonical reference.

Add `"<your_tool>"` to the `tools={…}` set of the plans that should
expose it.

### Add a new WhatsApp input type

Already-supported types: text, image, video, audio, voice, document,
sticker, location, contacts, interactive (button/list reply), template
button, reaction. To add a new one:

1. Extend the `MessageType` enum in `app/services/whatsapp/parser.py`.
2. Extend `extract_message_content` to populate `MessageContent`.
3. Add a handler under `app/services/whatsapp/handlers/`
   (subclass `BaseMessageHandler`).
4. Register it in `app/services/whatsapp/handlers/registry.py`.

---

## Running tests

```bash
uv run pytest -q
```

Should print `80 passed`. Test layout:
- `tests/test_models.py` — model basics + tier validation
- `tests/test_plans.py` — plan/quota/tool-gating
- `tests/test_parser.py` — every WhatsApp inbound type
- `tests/test_tools.py` — tool unit tests + tier-filtering
- `tests/test_commands.py` — slash command parsing
- `tests/test_memory.py` — memory CRUD + tools
- `tests/test_integrations.py` — Integration model + token round-trip
- `tests/test_registry_discovery.py` — tool/plugin auto-discovery
- `tests/test_api.py` — public HTTP routes
- `tests/test_security.py` — webhook signature verification

---

## Troubleshooting

**The bot is silent.**
- Check the worker is running (`uv run python -m app.queue.worker`).
- `tail` the API logs — incoming webhooks log `📱 Received webhook
  payload`.
- In Meta dashboard → WhatsApp → Configuration, hit **Send test event** —
  you should see a 200 OK in the log.
- Make sure your phone is in the test recipient list (sandbox apps).

**`401 Unauthorized` on `/admin/*`.**
- Set `X-Admin-Key: <your ADMIN_API_KEY>` on every request.
- Don't forget to restart after changing `.env`.

**`uv sync` says Python 3.13 is required.**
- `uv` will auto-download a managed 3.13 — just run `uv sync` again.

**WhatsApp signature verification fails.**
- Double-check `WHATSAPP_APP_SECRET` is the *App Secret* (not the access
  token) from Meta App Settings → Basic.
- Or unset it temporarily for local debugging.

**Stripe webhook returns 400.**
- Confirm `STRIPE_WEBHOOK_SECRET` matches the secret shown for **this
  exact endpoint** in the Stripe dashboard. Each endpoint gets its own
  signing secret.

**Plan upgrade didn't apply after Stripe checkout.**
- Verify the webhook is reachable — `stripe trigger
  checkout.session.completed` from the Stripe CLI is the fastest test.
- Check the worker / API logs for `Stripe event:` messages.

**Login OTP never arrives.**
- The OTP is sent over WhatsApp from your business number to whoever's
  trying to log in. They have to be a phone you can message (e.g. on the
  test recipient list in sandbox mode).
- In `DEBUG=True` mode the code is also shown on the post-submit screen.

---

## Project layout

```
whatsapp_agent/
├── app/
│   ├── main.py                       # FastAPI app + lifespan + router mount
│   ├── core/
│   │   ├── config.py                 # Settings (Pydantic settings, .env)
│   │   ├── plans.py                  # Plan tiers (Free/Pro/Max) — source of truth
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/
│   │   ├── session.py                # Async + sync SQLAlchemy engines
│   │   └── init_db.py
│   ├── models/                       # SQLModel tables
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── usage.py                  # daily/monthly counter
│   │   ├── memory.py                 # facts / preferences / summaries
│   │   ├── integration.py            # per-user OAuth records
│   │   ├── tool.py
│   │   ├── interaction.py
│   │   ├── webhook_log.py
│   │   └── broadcast.py
│   ├── schemas/                      # Pydantic request/response schemas
│   ├── api/routes/                   # JSON HTTP routes
│   │   ├── whatsapp.py               # /webhook (Meta)
│   │   ├── admin.py                  # /admin/* (X-Admin-Key)
│   │   ├── broadcast.py
│   │   ├── webhooks_admin.py
│   │   └── health.py
│   ├── middleware/
│   │   ├── rate_limit.py
│   │   └── message_queue.py          # per-user request lock
│   ├── queue/
│   │   ├── connection.py             # ARQ + Redis pool
│   │   ├── tasks.py                  # process_webhook_message
│   │   ├── worker.py                 # `python -m app.queue.worker`
│   │   └── user_queue_manager.py     # per-user message coalescing
│   ├── services/
│   │   ├── conversation_service.py   # get_or_create user/conv, save messages
│   │   ├── subscription_service.py   # quota check + register
│   │   ├── memory_service.py         # memory CRUD + lazy summarization
│   │   ├── integration_service.py    # OAuth token storage + refresh
│   │   ├── ai/
│   │   │   ├── agent_runner.py       # builds + runs the PydanticAI agent
│   │   │   └── reply_service.py      # post-processes tool outputs
│   │   └── whatsapp/
│   │       ├── client.py             # send text / image / location
│   │       ├── interactive.py        # send buttons / list / reactions / read
│   │       ├── parser.py             # webhook → ParsedMessage
│   │       ├── media_handler.py      # download / upload media; URL extract
│   │       ├── response_builder.py
│   │       ├── orchestrator.py       # the main inbound message pipeline
│   │       ├── commands.py           # /plan /usage /upgrade /memory ...
│   │       └── handlers/             # one per MessageType
│   ├── agents/
│   │   └── whatsapp_agent.py         # builds the per-user PydanticAI agent
│   ├── tools/
│   │   ├── base.py                   # BaseTool + plan gating
│   │   ├── context.py                # phone / user_id contextvars for tools
│   │   ├── registry.py               # auto-discovery
│   │   ├── plugin.py                 # JSON-manifest HTTP plugin
│   │   ├── builtin/                  # auto-discovered Python tools
│   │   ├── integrations/             # auto-discovered Python tools (OAuth)
│   │   └── manifests/                # auto-loaded JSON plugins
│   ├── web/
│   │   ├── routes.py                 # /, /pricing, /login, /dashboard, /checkout
│   │   ├── auth.py                   # phone+OTP + JWT cookie
│   │   ├── billing.py                # Stripe (with mock fallback)
│   │   ├── stripe_webhook.py         # /stripe/webhook
│   │   ├── integrations.py           # /integrations/google/{connect,callback}
│   │   ├── admin_ui.py               # /admin-ui
│   │   ├── crypto.py                 # at-rest token obfuscation
│   │   ├── templates/                # Jinja2
│   │   └── static/                   # CSS
│   └── utils/
│       ├── auth.py                   # admin_auth dependency
│       ├── whatsapp_security.py      # HMAC signature verification
│       └── monitoring.py
├── tests/                            # pytest, asyncio_mode = auto
├── admin/                            # legacy folder (unused; kept for reference)
├── alembic/                          # migration scripts
├── alembic.ini
├── pyproject.toml
├── env.example                       # copy to .env
├── docker-compose.yml
├── Dockerfile
├── start.sh
└── README.md (this file)
```

---

## License

Proprietary — see your fork.
