# AGENTS.md

This file is the entry point for AI coding agents working on this repo.

The full guide lives in **[CLAUDE.md](./CLAUDE.md)** — read it first.
End-user setup instructions are in **[README.md](./README.md)**.

## TL;DR for an agent landing here cold

1. **Run the tests** before you change anything: `uv run pytest -q`
   (should pass ~80 tests).
2. **Inbound message pipeline** lives in
   `app/services/whatsapp/orchestrator.py`. Start there for any
   "the bot did/didn't reply" bug.
3. **Plans drive everything** (model, tools, modalities, quotas):
   `app/core/plans.py`. Don't bake plan logic anywhere else.
4. **New tool** = drop a file in `app/tools/builtin/` (Python) or
   `app/tools/manifests/` (JSON) — the registry auto-discovers.
   Whitelist the tool name in `app/core/plans.py`.
5. **No comments** unless the *why* is non-obvious. Match the existing
   style.

For everything else (file map, conventions, sharp edges, recipes,
debugging hints), read **CLAUDE.md**.
