"""Process-local counter for chat capability (skill/tool) cache invalidation.

The chat agent caches the per-user filtered listings returned by
``mcp_runtime.list_tools_for_user`` / ``list_prompts_for_user`` so a chat turn
does not repeat two report-store round-trips. A naive TTL cache can serve
stale capabilities for the full TTL after an admin creates, updates, or
deletes a tool/skill; this module provides a monotonic revision counter that
mutating code bumps, letting the cache invalidate immediately within the
process that performed the write.

Multi-worker note: each gunicorn worker has its own counter, so a write in
worker A is not seen by worker B until B's TTL safety net expires. That trade
is acceptable for an in-memory cache — keep the TTL short (tens of seconds)
to bound cross-worker staleness.

Living in its own module avoids a circular import: ``report_store`` (which
calls ``bump_revision`` after mutations) and ``chat_graph`` (which reads the
revision in its cache check) both depend on this module, not on each other.
"""

_revision = 0


def get_revision() -> int:
    return _revision


def bump_revision() -> None:
    global _revision
    _revision += 1
