import logging
import signal
import time
from typing import Any
from typing import Dict
from typing import List

from flask import Flask
from flask.cli import AppGroup

from reporting import scheduled_query_modules
from reporting import settings
from reporting import setup_logging  # noqa:F401
from reporting.schema import reporting_config
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

STATE = {
    "shutdown": False,
}

app = Flask(__name__)
user_cli = AppGroup("worker")
app.cli.add_command(user_cli)


def _is_shutdown() -> bool:
    global STATE
    return STATE["shutdown"]


def _bootstrap() -> None:
    global STATE

    def finalizer(signal, frame):  # type: ignore
        logger.info("SIGTERM caught, shutting down")
        STATE["shutdown"] = True

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


def schedule_query(
    scheduled_query_id: str,
    scheduled_query: ScheduledQuery,
) -> None:
    if not scheduled_query.enabled:
        logger.debug(
            "Skipping disabled query", extra={"scheduled_query_id": scheduled_query_id}
        )
        return
    logger.debug("Checking query", extra={"scheduled_query_id": scheduled_query_id})
    if lock_scheduled_query(scheduled_query_id, scheduled_query):
        logger.debug(
            "Got lock for query", extra={"scheduled_query_id": scheduled_query_id}
        )
        try:
            query_str = scheduled_query.cypher
            params = {d.name: d.value for d in scheduled_query.params}
            results = run_query_with_retry(query_str, params)
            for action in scheduled_query.actions:
                _handle_results(scheduled_query_id, action, results)
            try:
                reset_scheduled_query_fail_count(scheduled_query_id)
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
                incr_scheduled_query_fail_count(scheduled_query_id)
            except Exception:
                logger.exception(
                    "Failed to reset query count",
                    extra={"scheduled_query_id": scheduled_query_id},
                )


def _handle_results(
    scheduled_query_id: str, action: ScheduledQueryAction, results: List[Dict[str, Any]]
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
            " configued in SCHEDULED_QUERY_MODULES",
            extra={
                "scheduled_query_id": scheduled_query_id,
                "action": action_type,
            },
        )
        return
    module = scheduled_query_modules.get_module(action_type)
    module.handle_results(scheduled_query_id, action, results)


def _schedule_queries() -> None:
    _bootstrap()
    should_init = settings.DYNAMODB_CREATE_TABLE or (
        settings.REPORT_STORE_BACKEND == "sqlmodel"
    )
    if should_init:
        report_store.initialize()
    config = reporting_config.load_file(settings.REPORTING_CONFIG_FILE)
    scheduled_query_modules.load_modules(config)
    while not _is_shutdown():
        logger.debug("Checking queries to schedule...")
        sq_items = report_store.list_scheduled_queries()
        for item in sq_items:
            sq = _item_to_scheduled_query(item)
            schedule_query(item.scheduled_query_id, sq)
        if not _is_shutdown():
            time.sleep(settings.SCHEDULED_QUERY_FREQUENCY)


@user_cli.command("schedule-queries")
def schedule_queries() -> None:
    if settings.ENABLE_SCHEDULED_QUERIES:
        _schedule_queries()
