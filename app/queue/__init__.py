"""Background task queue (ARQ + Redis).

Avoid eager re-exports here so we don't pull `tasks` (which imports the
WhatsApp orchestrator) before the package finishes initializing — that path
creates a circular import via ``user_queue_manager``.
"""
