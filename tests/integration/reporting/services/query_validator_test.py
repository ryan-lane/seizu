"""Live Neo4j regression tests for query validation.

These tests intentionally do not mock the Neo4j driver. Dangerous queries are
validated through EXPLAIN by validate_query(), so write/schema cases should be
planned but not executed.
"""

from collections.abc import Iterable
from typing import Any

import pytest

from reporting.services import reporting_neo4j
from reporting.services.query_validator import validate_query
from reporting.services.reporting_neo4j import _get_async_neo4j_client
from tests.query_validator_cases import (
    ADMIN_COMMAND_FUZZ_CASES,
    ALLOWED_PROCEDURE_CASES,
    CYPHER_25_BLOCKED_EXTRA_QUERIES,
    DANGEROUS_READ_PATH_FUZZ_CASES,
    DISALLOWED_PROCEDURE_CASES,
    LIVE_READ_ONLY_QUERIES,
    NEO4JECTION_BLOCKED_QUERIES,
    READ_ONLY_CALL_SUBQUERY_CASES,
    USE_CLAUSE_FALSE_POSITIVE_CASES,
    USE_CLAUSE_FUZZ_CASES,
    WRITE_QUERY_TYPE_FUZZ_CASES,
)


@pytest.fixture(autouse=True)
async def reset_neo4j_driver_caches() -> None:
    if reporting_neo4j._ASYNC_CLIENT_CACHE is not None:
        await reporting_neo4j._ASYNC_CLIENT_CACHE.close()
    if reporting_neo4j._SYNC_CLIENT_CACHE is not None:
        reporting_neo4j._SYNC_CLIENT_CACHE.close()
    reporting_neo4j._ASYNC_CLIENT_CACHE = None
    reporting_neo4j._SYNC_CLIENT_CACHE = None
    yield
    if reporting_neo4j._ASYNC_CLIENT_CACHE is not None:
        await reporting_neo4j._ASYNC_CLIENT_CACHE.close()
    if reporting_neo4j._SYNC_CLIENT_CACHE is not None:
        reporting_neo4j._SYNC_CLIENT_CACHE.close()
    reporting_neo4j._ASYNC_CLIENT_CACHE = None
    reporting_neo4j._SYNC_CLIENT_CACHE = None


async def _neo4j_versions() -> tuple[set[str], set[str]]:
    driver = _get_async_neo4j_client()
    records, _, _ = await driver.execute_query("CALL dbms.components() YIELD name, versions RETURN name, versions")
    components: dict[str, set[str]] = {record["name"]: set(record["versions"]) for record in records}
    return components.get("Neo4j Kernel", set()), components.get("Cypher", set())


@pytest.fixture
async def cypher_versions() -> set[str]:
    _, versions = await _neo4j_versions()
    return versions


async def _assert_allowed(query: str, params: dict[str, object] | None = None) -> None:
    result = await validate_query(query, params=params)
    assert not result.has_errors, (
        f"Expected query to be allowed but it was blocked.\n"
        f"query: {query!r}\n"
        f"errors: {result.errors}\n"
        f"warnings: {result.warnings}"
    )


async def _assert_blocked(query: str, params: dict[str, object] | None = None) -> None:
    result = await validate_query(query, params=params)
    assert result.has_errors, (
        f"Expected query to be blocked but it was allowed.\nquery: {query!r}\nwarnings: {result.warnings}"
    )


def _query_param(param: Any, index: int = 0) -> object:
    return param.values[index]


def _case_id(param: Any) -> str | None:
    return param.id


def _as_query_params(cases: Iterable[Any], value_index: int = 0) -> list[Any]:
    return [pytest.param(_query_param(case, value_index), id=_case_id(case)) for case in cases]


UNIT_DANGEROUS_READ_PATH_QUERIES = _as_query_params(DANGEROUS_READ_PATH_FUZZ_CASES)
UNIT_WRITE_QUERIES = _as_query_params(WRITE_QUERY_TYPE_FUZZ_CASES, value_index=1)
UNIT_READ_ONLY_CALL_SUBQUERY_QUERIES = _as_query_params(READ_ONLY_CALL_SUBQUERY_CASES)
UNIT_ADMIN_COMMAND_QUERIES = _as_query_params(ADMIN_COMMAND_FUZZ_CASES)
UNIT_USE_CLAUSE_QUERIES = _as_query_params(USE_CLAUSE_FUZZ_CASES)
UNIT_USE_CLAUSE_FALSE_POSITIVE_QUERIES = _as_query_params(USE_CLAUSE_FALSE_POSITIVE_CASES)
UNIT_DISALLOWED_PROCEDURE_QUERIES = _as_query_params(DISALLOWED_PROCEDURE_CASES)
UNIT_ALLOWED_PROCEDURE_QUERIES = _as_query_params(ALLOWED_PROCEDURE_CASES)


@pytest.mark.parametrize("query", LIVE_READ_ONLY_QUERIES)
async def test_live_read_only_queries_are_allowed(query: str) -> None:
    params = {"name": "test"} if "$name" in query else None
    await _assert_allowed(query, params=params)


async def test_live_missing_parameter_is_not_blocking() -> None:
    result = await validate_query("MATCH (n) WHERE n.name = $name RETURN n LIMIT 1")
    assert not result.has_errors


@pytest.mark.parametrize("query", UNIT_WRITE_QUERIES)
async def test_live_unit_write_family_queries_are_blocked(query: str) -> None:
    await _assert_blocked(query)


@pytest.mark.parametrize("query", UNIT_DANGEROUS_READ_PATH_QUERIES)
async def test_live_unit_dangerous_read_path_family_queries_are_blocked(query: str) -> None:
    await _assert_blocked(query)


@pytest.mark.parametrize("query", UNIT_ADMIN_COMMAND_QUERIES)
async def test_live_unit_admin_command_family_queries_are_blocked(query: str) -> None:
    await _assert_blocked(query)


@pytest.mark.parametrize("query", NEO4JECTION_BLOCKED_QUERIES)
async def test_live_neo4jection_family_queries_are_blocked(query: str) -> None:
    await _assert_blocked(query)


@pytest.mark.parametrize("query", UNIT_USE_CLAUSE_QUERIES)
async def test_live_use_clause_family_queries_are_blocked(query: str) -> None:
    params = {"db": "neo4j", "id": "4:abc:0"} if "$" in query else None
    await _assert_blocked(query, params=params)


@pytest.mark.parametrize("query", UNIT_USE_CLAUSE_FALSE_POSITIVE_QUERIES)
async def test_live_use_clause_false_positive_queries_are_allowed(query: str) -> None:
    await _assert_allowed(query)


@pytest.mark.parametrize("query", UNIT_DISALLOWED_PROCEDURE_QUERIES)
async def test_live_disallowed_procedure_family_queries_are_blocked(query: str) -> None:
    await _assert_blocked(query)


@pytest.mark.parametrize("query", UNIT_ALLOWED_PROCEDURE_QUERIES)
async def test_live_allowed_procedure_family_queries_are_allowed(query: str) -> None:
    await _assert_allowed(query)


@pytest.mark.parametrize("query", UNIT_READ_ONLY_CALL_SUBQUERY_QUERIES)
async def test_live_unit_read_only_call_subquery_family_queries_are_allowed(
    cypher_versions: Iterable[str], query: str
) -> None:
    if query.startswith("CYPHER 25") and "25" not in cypher_versions:
        pytest.skip("active Neo4j does not advertise Cypher 25")
    await _assert_allowed(query)


@pytest.mark.parametrize("query", CYPHER_25_BLOCKED_EXTRA_QUERIES)
async def test_live_cypher25_extra_dangerous_queries_are_blocked(cypher_versions: Iterable[str], query: str) -> None:
    if "25" not in cypher_versions:
        pytest.skip("active Neo4j does not advertise Cypher 25")
    await _assert_blocked(query)
