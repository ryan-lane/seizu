import logging
import time
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
from neo4j.exceptions import TransactionError

from reporting import settings
from reporting.schema.reporting_config import ScheduledQuery
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


async def _lock(tx: AsyncTransaction, query_id: str) -> None:
    query = """
    MERGE (sq:ScheduledQuery{id: $query_id})
    ON CREATE SET sq.firstseen = timestamp(), sq.fail_count = 0
    SET sq.scheduled = $UPDATE_TAG
    """
    await run_tx_with_retry(
        tx, query, {"query_id": query_id, "UPDATE_TAG": int(time.time())}
    )


async def _scheduled_time(tx: AsyncTransaction, query_id: str) -> int:
    query = "MATCH (sq:ScheduledQuery{id: $query_id}) RETURN sq.scheduled"
    results = await run_tx_with_retry(tx, query, {"query_id": query_id})
    scheduled = 0
    for result in results:
        scheduled = result["sq.scheduled"]
    return scheduled


async def _scan_time(tx: AsyncTransaction, scan_type: ScheduledQueryWatchScan) -> int:
    query = """
    MATCH (s:SyncMetadata)
    WHERE s.grouptype =~ ($grouptype)
          AND s.syncedtype =~ ($syncedtype)
          AND toString(s.groupid) =~ ($groupid)
    RETURN max(s.lastupdated) AS maxlastupdated
    """
    results = await run_tx_with_retry(
        tx,
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


async def _watch_triggered(
    tx: AsyncTransaction,
    scheduled: int,
    watch_scans: List[ScheduledQueryWatchScan],
) -> bool:
    for scan_type in watch_scans:
        scan_time = await _scan_time(tx, scan_type)
        logger.debug(
            f"scan_type: {scan_type}, scan_time: {scan_time}, scheduled: {scheduled}"
        )
        if scan_time > scheduled:
            return True
    return False


def _frequency_triggered(scheduled: int, frequency: int) -> bool:
    next_run_time = scheduled + (frequency * 60)
    now = datetime.now().timestamp()
    logger.debug(f"now: {now}, scheduled: {scheduled}")
    return now > next_run_time


async def lock_scheduled_query(
    scheduled_query_id: str, scheduled_query: ScheduledQuery
) -> bool:
    frequency = scheduled_query.frequency
    watch_scans = scheduled_query.watch_scans
    driver = _get_async_neo4j_client()
    async with driver.session() as session:
        try:
            async with await session.begin_transaction() as tx:
                scheduled = await _scheduled_time(tx, scheduled_query_id)
                if frequency and _frequency_triggered(scheduled, frequency):
                    logger.debug(f"Triggering frequency lock for {scheduled_query_id}")
                    await _lock(tx, scheduled_query_id)
                elif watch_scans and await _watch_triggered(tx, scheduled, watch_scans):
                    logger.debug(f"Triggering watch_scan lock for {scheduled_query_id}")
                    await _lock(tx, scheduled_query_id)
                else:
                    logger.debug(
                        f"Neither frequency nor watch_scan lock for {scheduled_query_id}"
                    )
                    return False
        except TransactionError:
            logger.exception(f"Failed to get lock for {scheduled_query_id}")
            return False
        return True


async def incr_scheduled_query_fail_count(scheduled_query_id: str) -> None:
    query = """
    MERGE (sq:ScheduledQuery{id: $query_id})
    ON CREATE SET sq.firstseen = timestamp(), sq.fail_count = 0
    SET sq.fail_count = sq.fail_count + 1
    """
    await run_query_with_retry(query, {"query_id": scheduled_query_id})


async def reset_scheduled_query_fail_count(scheduled_query_id: str) -> None:
    query = """
    MERGE (sq:ScheduledQuery{id: $query_id})
    ON CREATE SET sq.firstseen = timestamp(), sq.fail_count = 0
    SET sq.fail_count = 0
    """
    await run_query_with_retry(query, {"query_id": scheduled_query_id})
