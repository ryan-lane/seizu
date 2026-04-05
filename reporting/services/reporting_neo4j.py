import logging
from datetime import datetime
from typing import cast
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional

import neo4j.exceptions
from neo4j import AsyncGraphDatabase
from neo4j import AsyncTransaction
from neo4j import Driver
from neo4j import GraphDatabase
from neo4j import Record

from reporting import settings
from reporting.schema.reporting_config import ScheduledQueryWatchScan

logger = logging.getLogger(__name__)

_ASYNC_CLIENT_CACHE: Optional[neo4j.AsyncDriver] = None
_SYNC_CLIENT_CACHE: Optional[Driver] = None


def _get_async_neo4j_client() -> neo4j.AsyncDriver:
    global _ASYNC_CLIENT_CACHE
    if _ASYNC_CLIENT_CACHE is None:
        neo4j_auth = None
        if settings.NEO4J_USER or settings.NEO4J_PASSWORD:
            neo4j_auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        _ASYNC_CLIENT_CACHE = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=neo4j_auth,
            max_connection_lifetime=settings.NEO4J_MAX_CONNECTION_LIFETIME,
            notifications_min_severity=cast(
                Literal["OFF", "WARNING", "INFORMATION"],
                settings.NEO4J_NOTIFICATIONS_MIN_SEVERITY,
            ),
        )
    return _ASYNC_CLIENT_CACHE


def _get_sync_neo4j_client() -> Driver:
    """Return a synchronous Neo4j driver — used only by CyVer validators."""
    global _SYNC_CLIENT_CACHE
    if _SYNC_CLIENT_CACHE is None:
        neo4j_auth = None
        if settings.NEO4J_USER or settings.NEO4J_PASSWORD:
            neo4j_auth = (settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        _SYNC_CLIENT_CACHE = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=neo4j_auth,
            max_connection_lifetime=settings.NEO4J_MAX_CONNECTION_LIFETIME,
            notifications_min_severity=cast(
                Literal["OFF", "WARNING", "INFORMATION"],
                settings.NEO4J_NOTIFICATIONS_MIN_SEVERITY,
            ),
        )
    return _SYNC_CLIENT_CACHE


async def run_query(cypher: str, parameters: Dict = None) -> List[Record]:
    results = []
    driver = _get_async_neo4j_client()
    async with driver.session() as session:
        query_results = await session.run(cypher, parameters=parameters)
        async for result in query_results:
            results.append(result)
    return results


async def run_query_with_retry(cypher: str, parameters: Dict = None) -> List[Record]:
    attempt = 1
    while True:
        try:
            return await run_query(cypher, parameters=parameters)
        except neo4j.exceptions.ServiceUnavailable:
            logger.debug("Unable to connect to neo4j, retrying...")
            if attempt >= 5:
                raise
        attempt = attempt + 1


async def run_tx(
    tx: AsyncTransaction, cypher: str, parameters: Dict = None
) -> List[Record]:
    results = []
    query_results = await tx.run(cypher, parameters=parameters)
    async for result in query_results:
        results.append(result)
    return results


async def run_tx_with_retry(
    tx: AsyncTransaction, cypher: str, parameters: Dict = None
) -> List[Record]:
    attempt = 1
    while True:
        try:
            return await run_tx(tx, cypher, parameters=parameters)
        except neo4j.exceptions.ServiceUnavailable:
            logger.debug("Unable to connect to neo4j, retrying...")
            if attempt >= 5:
                raise
        attempt = attempt + 1


async def _scan_time(scan_type: ScheduledQueryWatchScan) -> int:
    query = """
    MATCH (s:SyncMetadata)
    WHERE s.grouptype =~ ($grouptype)
          AND s.syncedtype =~ ($syncedtype)
          AND toString(s.groupid) =~ ($groupid)
    RETURN max(s.lastupdated) AS maxlastupdated
    """
    results = await run_query_with_retry(
        query,
        {
            "grouptype": scan_type.grouptype,
            "syncedtype": scan_type.syncedtype,
            "groupid": scan_type.groupid,
        },
    )
    maxlastupdated = 0
    for result in results:
        if result["maxlastupdated"] is not None:
            maxlastupdated = result["maxlastupdated"]
    return maxlastupdated


async def check_watch_scan_triggered(
    last_scheduled_at: Optional[str],
    watch_scans: List[ScheduledQueryWatchScan],
) -> bool:
    """Return True if any watched SyncMetadata node was updated after last_scheduled_at.

    Converts *last_scheduled_at* (ISO string or None) to Unix seconds for
    comparison with Neo4j's ``lastupdated`` field, preserving the same unit
    semantics as the previous Neo4j-based locking implementation.
    """
    if last_scheduled_at is None:
        scheduled_unix = 0
    else:
        scheduled_unix = int(datetime.fromisoformat(last_scheduled_at).timestamp())

    for scan_type in watch_scans:
        scan_time = await _scan_time(scan_type)
        logger.debug(
            f"scan_type: {scan_type}, scan_time: {scan_time}, scheduled: {scheduled_unix}"
        )
        if scan_time > scheduled_unix:
            return True
    return False
