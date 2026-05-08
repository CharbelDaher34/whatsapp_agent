# CLAUDE.md — agent navigation for this repo

> This document is for AI coding agents (Claude Code, Cursor, OpenAI agents,
> etc.) opening this repo cold. It explains where things live, how the
> request pipeline works, and the conventions the existing code already
> follows. Read this **before** you grep around — it'll save you a lot of
> time. End-user setup instructions live in **README.md**.

---

## 1. What this repo is

A WhatsApp assistant. Inbound webhooks → ARQ queue → per-user pipeline that
parses, type-dispatches, runs a plan-aware PydanticAI agent, and replies.
Plus a small public web app (signup, pricing, dashboard, Stripe checkout)
and an admin panel.

Stack: **FastAPI + SQLModel (async) + PydanticAI + ARQ + Redis + Jinja2 +
optional Postgres / Stripe / Google OAuth**.

---

## 2. Mental model — one request, end to end

Inbound:

1. `POST /webhook` (`app/api/routes/whatsapp.py`) — verifies the Meta HMAC
   signature, validates the payload shape, **enqueues** into ARQ
   (Redis-backed) and returns 200 OK immediately.
2. The ARQ worker runs `process_webhook_message` (`app/queue/tasks.py`),
   which calls `handle_incoming_webhook` in
   `app/services/whatsapp/orchestrator.py`. **This is the central
   orchestrator — start reading here for any inbound bug.**
3. The orchestrator:
   1. Parses (`whatsapp/parser.py`) → `ParsedMessage`.
   2. Marks the message read (`whatsapp/interactive.py`).
   3. Resolves user + conversation (`services/conversation_service.py`).
   4. **Quota check** (`services/subscription_service.check_quota`) BEFORE
      we burn AI tokens. On rejection, sends an upgrade prompt and stops.
   5. **Slash command intercept** (`whatsapp/commands.maybe_handle_command`).
      `/plan`, `/usage`, `/upgrade`, `/memory`, `/forget`, `/integrations`,
      `/help` etc. bypass the AI entirely.
   6. Routes the message to a type-specific handler
      (`whatsapp/handlers/*` via `handlers/registry.py`). Image handler
      downloads + caches the image path in Redis; document handler does
      best-effort PDF/text extraction; audio handler runs Whisper for
      Pro/Max.
   7. Saves the inbound message.
   8. Calls `services/ai/agent_runner.generate_reply` which:
      - Builds a per-user `Agent` via `agents/whatsapp_agent.py`
        (model + tools + system prompt all scale with the plan).
      - Pre-loads top-relevant **memories** from `services/memory_service.py`
        into the prompt block.
      - Sets `current_phone` and `current_user_id` contextvars
        (`tools/context.py`) so tools can find the user without explicit
        threading.
   9. Post-processes the model output (`services/ai/reply_service`):
      - `IMAGE_URL:<path>` → upload + send image.
      - `[NO_TEXT_REPLY]` → the agent already pushed an interactive
        message, so don't double-message.
      - Otherwise: plain text.
  10. Saves bot reply, registers usage, lazily summarizes if history
      exceeded threshold.
  11. Drains queued-while-processing messages for that user
      (`queue/user_queue_manager.py`).

Outbound (web):
- Templated Jinja pages: `app/web/templates/`. Auth = phone+OTP via
  WhatsApp → JWT cookie (`app/web/auth.py`).
- Stripe via `app/web/billing.py` (mock fallback when keys are absent).
- Google OAuth via `app/web/integrations.py`.
- Admin panel HTML at `/admin-ui` (`app/web/admin_ui.py`) — calls the
  existing `/admin/*` JSON endpoints with the operator's
  `X-Admin-Key`.

---

## 3. Quick file map

| If you need to… | Look here |
|---|---|
| Change a plan's quota / model / tool whitelist | `app/core/plans.py` |
| Add a new env var | `app/core/config.py`, then `env.example` |
| Add a new WhatsApp inbound type | `app/services/whatsapp/parser.py` + new handler under `app/services/whatsapp/handlers/` + register in `handlers/registry.py` |
| Add a new tool (Python) | drop a file in `app/tools/builtin/` (or `app/tools/integrations/`) — auto-registered by `app/tools/registry.py`. Whitelist in `plans.py` |
| Add an external HTTP-only tool | drop a JSON manifest in `app/tools/manifests/` (schema: `app/tools/plugin.py`) |
| Add a slash command | `app/services/whatsapp/commands.py` (extend `_COMMAND_ALIASES` + add a handler) |
| Tweak the system prompt | `app/agents/whatsapp_agent.py::_build_system_prompt` |
| Change the inbound pipeline | `app/services/whatsapp/orchestrator.py` |
| Change the agent run loop | `app/services/ai/agent_runner.py` |
| Change post-processing of model output | `app/services/ai/reply_service.py` |
| Touch memory behaviour | `app/services/memory_service.py` |
| Add a new integration (OAuth) | (1) provider OAuth in `app/services/integration_service.py`, (2) routes in `app/web/integrations.py`, (3) tool in `app/tools/integrations/<provider>.py` |
| Modify the admin JSON API | `app/api/routes/admin.py` |
| Modify the admin HTML panel | `app/web/templates/admin.html` (vanilla JS hits `/admin/*`) |
| Modify the public web app | `app/web/routes.py` + `app/web/templates/` |
| Modify Stripe behaviour | `app/web/billing.py` (start) + `app/web/stripe_webhook.py` (apply changes) |
| Touch the queue / worker | `app/queue/` (do **not** import `tasks` from `app/queue/__init__.py` — it would re-introduce a circular import that we already fixed) |

---

## 4. Conventions the existing code already follows

These are not aspirational — the rest of the repo follows them, so please
match.

- **Plans drive everything.** Don't bake plan checks into individual
  features; declare them in `app/core/plans.py` and let the existing
  gating do the work. Examples: `tools` whitelist, `can_*` flags,
  `inbound_modalities`.
- **One source of truth.** The plan tier lives on `User.subscription_tier`;
  display labels live in `app/core/plans.py::PLANS[…].display_name`. Don't
  hard-code "Pro"/"Max" strings elsewhere.
- **Tools are stateless and async.** Subclass `BaseTool`, implement
  `async def process(self, text, **kwargs)`. Use the `phone` and
  `user_id` kwargs (forwarded by `BaseTool.to_pydanticai_tool`) to look
  up user-specific state — don't add new contextvars.
- **No new sync DB sessions.** Use `async with get_session() as session:`
  from `app.db.session`.
- **Use the existing logger.** `from app.core.logging import logger`. No
  prints, no other loggers.
- **No new feature flags.** If something's plan-gated, gate it via
  `app/core/plans.py`. If it's environment-config'd, add a setting in
  `app/core/config.py`.
- **Idempotent startup.** `init_db()` and `init_tools()` must remain
  idempotent — `init_tools()` clears the registry before re-populating.
- **No comments unless the WHY is non-obvious.** Most code in this repo
  has zero comments by design. Don't add a docstring/comment for what the
  code already says.
- **Async sessions, synchronous-ish admin sessions.** The webhook
  pipeline uses `AsyncSession`; the admin REST routes use the sync
  `Session` (FastAPI dependency style). Don't mix them in the same
  function.
- **Tests live in `tests/`** with `asyncio_mode = "auto"`. Write `async`
  tests directly without `@pytest.mark.asyncio`.

---

## 5. Sharp edges (read before editing)

- **`app/queue/__init__.py` is intentionally empty.** Earlier it eagerly
  imported `tasks`, which transitively imported the WhatsApp orchestrator
  and caused a circular import via `user_queue_manager`. Don't re-add
  imports there.
- **`extract_image_url_from_text`** parses both raw `IMAGE_URL:<path>` and
  markdown `![…](IMAGE_URL:…)`. Image-generation tools must return the
  raw form so the response builder can pick it up.
- **`[NO_TEXT_REPLY]` sentinel.** When the agent calls `ask_buttons` /
  `ask_list`, it should append `[NO_TEXT_REPLY]` so we don't send a
  duplicate text. The reply post-processor strips it.
- **Reactions don't trigger a reply.** `handlers/reaction_handler.py`
  returns `requires_ai=False`. Don't change this without a good reason —
  users sending 👍 don't expect a chat back.
- **Admin auth returns 401 for missing OR wrong key.** Don't change this
  to 403 / 422 — there's a test that asserts 401.
- **Stripe is optional.** When `STRIPE_SECRET_KEY` is empty, the app runs
  in "mock billing" mode. `settings.billing_mode` returns `"live"` or
  `"mock"`. Most billing-related code branches on that.
- **OAuth tokens are stored signed, not encrypted.** `app/web/crypto.py`
  uses `itsdangerous` — fine for dev, NOT KMS-grade. Don't claim
  otherwise in any user-facing copy.
- **WhatsApp message body cap is 4000 chars.** `send_whatsapp_text`
  truncates. If you need long output, send multiple messages.
- **Image generation tool output uses the prefix `IMAGE_URL:`** — keep
  this token, downstream code splits on it.

---

## 6. Common tasks (recipes)

### 6.1 Add a new built-in tool
1. New file in `app/tools/builtin/<name>.py` with a class extending
   `BaseTool`. Set `min_tier`.
2. Add the tool's `name` to the `tools={…}` set of every plan that
   should expose it in `app/core/plans.py`.
3. Restart. The registry auto-discovers it.
4. Add a unit test under `tests/test_tools.py` (or `test_<name>.py`).

### 6.2 Add a new slash command
1. Add the canonical name + aliases to `_COMMAND_ALIASES` in
   `app/services/whatsapp/commands.py`.
2. Add an `_handle_<name>(phone, user, session)` function.
3. Branch in `maybe_handle_command`.
4. Add a parametrize entry to `tests/test_commands.py`.

### 6.3 Add a new integration (provider)
1. Add provider-specific helpers in
   `app/services/integration_service.py` (mirror `upsert_google` /
   `get_fresh_google_access_token`).
2. Add OAuth `/integrations/<provider>/connect` and `…/callback` routes
   in `app/web/integrations.py`.
3. Add a tool under `app/tools/integrations/<provider>.py` that calls
   `get_active(session, user_id, "<provider>")` and the fresh access
   token. Set `min_tier="pro"`.
4. Whitelist the tool name in `app/core/plans.py` (Pro + Max).
5. Surface it on the dashboard
   (`app/web/templates/dashboard.html` integrations section + extra
   context in `app/web/routes.py::dashboard`).
6. Tests in `tests/test_integrations.py` for the model + service layer
   (don't try to live-test OAuth in unit tests — use the upsert/revoke
   API).

### 6.4 Add a new WhatsApp inbound type
1. Extend the `MessageType` enum in
   `app/services/whatsapp/parser.py`.
2. Extend `extract_message_content` to populate `MessageContent`
   (add new fields if needed).
3. Add a handler under `app/services/whatsapp/handlers/`. Subclass
   `BaseMessageHandler`. Decide whether `requires_ai=True/False`.
4. Register it in `app/services/whatsapp/handlers/registry.py`.
5. Add a parser test in `tests/test_parser.py`.

### 6.5 Run the dev stack locally
```bash
uv sync
cp env.example .env && $EDITOR .env       # fill required keys
docker run -d --name redis -p 6379:6379 redis:7
uv run uvicorn app.main:app --reload --port 8000   # terminal A
uv run python -m app.queue.worker                  # terminal B
```

For inbound WhatsApp webhooks: `ngrok http 8000`, paste the HTTPS URL
into Meta dashboard Webhook config (callback `<url>/webhook`, verify
token = `WHATSAPP_VERIFY_TOKEN`).

### 6.6 Run tests
```bash
uv run pytest -q
```
80+ tests should pass. Each new feature should ship with a focused test
file.

---

## 7. Things to avoid

- **Don't introduce sync HTTP clients** in any code that's reachable
  from a webhook or async route — we use `httpx.AsyncClient` exclusively.
- **Don't `eval` user input.** The calculator is AST-based for a reason.
- **Don't add new background scheduling.** Lazy summarization runs as
  part of the request lifecycle on purpose. If you need cron-like work,
  schedule via ARQ (already wired up).
- **Don't re-export from `app/queue/__init__.py`** (circular import).
- **Don't bypass `register_message`.** Skipping it desyncs daily quota.
- **Don't mock `send_whatsapp_text` in tests by patching httpx.** Use the
  existing `await send_whatsapp_text` path; all tests today work without
  a mock since the webhook tests don't trigger sends.
- **Don't store secrets in code.** Settings only.

---

## 8. Useful entry points for debugging

| Symptom | Where to look first |
|---|---|
| Wrong tool list for a tier | `app/core/plans.py::PLANS` |
| Quota always says "exceeded" | `app/services/subscription_service.py::check_quota`, then the `usage_record` table |
| Agent doesn't see a memory you stored | `app/services/ai/agent_runner.py::_build_memory_block` (recall query string) |
| Image not sent back | `app/services/ai/reply_service.py::process_tool_outputs`, then `app/services/whatsapp/media_handler.py::extract_image_url_from_text` |
| OAuth callback 500s | `app/web/integrations.py::google_callback` (check `state` TTL in Redis) |
| Webhook 401 | `WHATSAPP_APP_SECRET` mismatch — see `app/utils/whatsapp_security.py` |
| Dashboard shows wrong plan | `app/web/auth.py::issue_session_token` only encodes the tier at login time; user upgrades issue a redirect, but the cookie lags until next login. The dashboard always re-loads the DB row, so trust that. |

---

## 9. Out of scope (not yet implemented)

- Real OAuth provider beyond Google.
- Vector / embedding-based memory recall (current recall is substring +
  importance ranking).
- Per-tenant white-labelling.
- A11y / i18n on the public site.
- Sending cron-scheduled proactive WhatsApp messages.

If a user asks for one of these, surface that it's net-new work, then
follow the recipe in §6 if they want it built.
