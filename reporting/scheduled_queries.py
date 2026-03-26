import asyncio
import logging
import signal
from typing import Any
from typing import Dict
from typing import List

from reporting import scheduled_query_modules
from reporting import settings
from reporting import setup_logging  # noqa:F401
from reporting.schema.report_config import ScheduledQueryItem
from reporting.schema.reporting_config import ScheduledQuery
from reporting.schema.reporting_config import ScheduledQueryAction
from reporting.schema.reporting_config import ScheduledQueryParam
from reporting.schema.reporting_config import ScheduledQueryWatchScan
from reporting.services import report_store
from reporting.services.reporting_neo4j import incr_scheduled_query_fail_count
from reporting.services.reporting_neo4j import lock_scheduled_query
from reporting.services.reporting_neo4j import reset_scheduled_query_fail_count
from reporting.services.reporting_neo4j import run_query_with_retry

logger = logging.getLogger(__name__)

_shutdown_event: asyncio.Event = asyncio.Event()


def _bootstrap() -> None:
    def finalizer(sig: int, frame: Any) -> None:
        logger.info("SIGTERM caught, shutting down")
        _shutdown_event.set()

    signal.signal(signal.SIGTERM, finalizer)


def _item_to_scheduled_query(item: ScheduledQueryItem) -> ScheduledQuery:
    """Convert a DB ScheduledQueryItem into a ScheduledQuery model for the worker."""
    return ScheduledQuery(
        name=item.name,
        cypher=item.cypher,
        params=[ScheduledQueryParam(**p) for p in item.params],
        frequency=item.frequency,
        watch_scans=[ScheduledQueryWatchScan(**ws) for ws in item.watch_scans],
        enabled=item.enabled,
        actions=[ScheduledQueryAction(**a) for a in item.actions],
    )


async def schedule_query(
    scheduled_query_id: str,
    scheduled_query: ScheduledQuery,
) -> None:
    if not scheduled_query.enabled:
        logger.debug(
            "Skipping disabled query", extra={"scheduled_query_id": scheduled_query_id}
        )
        return
    logger.debug("Checking query", extra={"scheduled_query_id": scheduled_query_id})
    if await lock_scheduled_query(scheduled_query_id, scheduled_query):
        logger.debug(
            "Got lock for query", extra={"scheduled_query_id": scheduled_query_id}
        )
        try:
            query_str = scheduled_query.cypher
            params = {d.name: d.value for d in scheduled_query.params}
            results = await run_query_with_retry(query_str, params)
            for action in scheduled_query.actions:
                await _handle_results(scheduled_query_id, action, results)
            try:
                await reset_scheduled_query_fail_count(scheduled_query_id)
            except Exception:
                logger.exception(
                    "Failed to reset query count",
                    extra={"scheduled_query_id": scheduled_query_id},
                )
        except Exception:
            logger.exception(
                "Failed to run actions for query",
                extra={"scheduled_query_id": scheduled_query_id},
            )
            try:
                await incr_scheduled_query_fail_count(scheduled_query_id)
            except Exception:
                logger.exception(
                    "Failed to reset query count",
                    extra={"scheduled_query_id": scheduled_query_id},
                )


async def _handle_results(
    scheduled_query_id: str,
    action: ScheduledQueryAction,
    results: List[Dict[str, Any]],
) -> None:
    action_type = action.action_type
    if not action_type:
        logger.error(
            "Skipping misconfigured scheduled query",
            extra={
                "scheduled_query_id": scheduled_query_id,
                "misconfiguration": "missing action_type",
            },
        )
        return
    if action_type not in scheduled_query_modules.get_module_names():
        logger.error(
            "Skipping results for scheduled query that is using an action that is not"
            " configured in SCHEDULED_QUERY_MODULES",
            extra={
                "scheduled_query_id": scheduled_query_id,
                "action": action_type,
            },
        )
        return
    module = scheduled_query_modules.get_module(action_type)
    await asyncio.to_thread(module.handle_results, scheduled_query_id, action, results)


async def _schedule_queries() -> None:
    _bootstrap()
    should_init = settings.DYNAMODB_CREATE_TABLE or (
        settings.REPORT_STORE_BACKEND == "sqlmodel"
    )
    if should_init:
        await report_store.initialize()
    await scheduled_query_modules.load_modules()
    while not _shutdown_event.is_set():
        logger.debug("Checking queries to schedule...")
        sq_items = await report_store.list_scheduled_queries()
        for item in sq_items:
            sq = _item_to_scheduled_query(item)
            await schedule_query(item.scheduled_query_id, sq)
        if not _shutdown_event.is_set():
            await asyncio.sleep(settings.SCHEDULED_QUERY_FREQUENCY)


def main() -> None:
    if settings.ENABLE_SCHEDULED_QUERIES:
        asyncio.run(_schedule_queries())


if __name__ == "__main__":
    main()
