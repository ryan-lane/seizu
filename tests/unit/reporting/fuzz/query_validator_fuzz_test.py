import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from reporting.services.query_validator import validate_query


def _mock_read_only_explain() -> MagicMock:
    mock_driver = MagicMock()
    mock_summary = MagicMock()
    mock_summary.notifications = []
    mock_summary.query_type = "r"
    mock_driver.execute_query = AsyncMock(return_value=([], mock_summary, []))
    return mock_driver


async def _validate_with_mocked_neo4j(query: str):
    with (
        patch("reporting.services.query_validator._get_async_neo4j_client", return_value=_mock_read_only_explain()),
        patch("reporting.services.query_validator.SchemaValidator") as schema_validator,
        patch("reporting.services.query_validator.PropertiesValidator") as properties_validator,
    ):
        schema_validator.return_value.validate.return_value = (True, [])
        properties_validator.return_value.validate.return_value = (True, [])
        return await validate_query(query)


separator = st.one_of(
    st.just(" "),
    st.just("\t"),
    st.just("\n"),
    st.just("/* hidden */"),
    st.just("/**/"),
    st.just(r"\u0020"),
)

plain_whitespace = st.sampled_from([" ", "\t", "\n"])

use_anchor = st.sampled_from(
    [
        ("", ""),
        ("CYPHER 25 ", ""),
        ("MATCH (n) RETURN count(n) AS c UNION ", ""),
        ("CYPHER 25 RETURN 1 AS x NEXT ", ""),
        ("CYPHER 25 WHEN true THEN ", ""),
        ("CYPHER 25 WHEN false THEN RETURN 0 AS n ELSE ", ""),
        ("CALL { ", " } RETURN n"),
    ]
)

use_graph_reference = st.sampled_from(
    [
        "otherdb",
        "myComposite.myConstituent",
        "`my-other-db`",
        "`my-composite`.`my-constituent`",
        "graph.byName('system')",
        "graph.byElementId($id)",
        "else",
        "end",
        "when",
        "then",
    ]
)

use_following_clause = st.sampled_from(
    [
        "MATCH (n) RETURN n",
        "RETURN 1 AS n",
        "WITH 1 AS n RETURN n",
        "UNWIND [1, 2] AS n RETURN n",
        "FOR x IN [1, 2] RETURN x",
        "LET x = 1 RETURN x",
        "OPTIONAL CALL { RETURN 1 AS n } RETURN n",
        "CALL { RETURN 1 AS n } RETURN n",
        "LOAD CSV FROM 'http://127.0.0.1:1/' AS row RETURN row",
        "SHOW SETTINGS YIELD name RETURN name",
    ]
)

case_operator = st.sampled_from(["", " + alt", " * 2"])


@settings(max_examples=75)
@given(separator=separator)
def test_dangerous_load_csv_variants_are_blocked(separator: str) -> None:
    query = f"LOAD{separator}CSV FROM 'http://169.254.169.254/latest/meta-data/' AS row RETURN row"

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert result.has_errors


@settings(max_examples=75)
@given(separator=separator)
def test_dangerous_call_apoc_variants_are_blocked(separator: str) -> None:
    query = f"CALL{separator}apoc.load.json('http://169.254.169.254/') YIELD value RETURN value"

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert result.has_errors


@settings(max_examples=75)
@given(
    prefix=st.text(max_size=20),
    suffix=st.text(max_size=20),
    show_keyword=st.sampled_from(["SHOW", r"SH\u004fW"]),
    separator=separator,
)
def test_admin_command_variants_are_blocked(
    prefix: str,
    suffix: str,
    show_keyword: str,
    separator: str,
) -> None:
    query = f"{prefix} {show_keyword}{separator}SETTINGS YIELD name RETURN name {suffix}"

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert result.has_errors


@settings(max_examples=200)
@given(
    anchor=use_anchor,
    use_keyword=st.sampled_from(["USE", "use", r"\u0055SE"]),
    first_separator=separator,
    graph_reference=use_graph_reference,
    second_separator=separator,
    following_clause=use_following_clause,
)
def test_use_clause_variants_are_blocked(
    anchor: tuple[str, str],
    use_keyword: str,
    first_separator: str,
    graph_reference: str,
    second_separator: str,
    following_clause: str,
) -> None:
    prefix, suffix = anchor
    query = f"{prefix}{use_keyword}{first_separator}{graph_reference}{second_separator}{following_clause}{suffix}"

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert result.has_errors


@settings(max_examples=100)
@given(
    before_use=st.integers(min_value=-5, max_value=5),
    alternate=st.integers(min_value=-5, max_value=5),
    then_separator=plain_whitespace,
    else_separator=plain_whitespace,
    operator=case_operator,
)
def test_case_expressions_with_use_variable_are_allowed(
    before_use: int,
    alternate: int,
    then_separator: str,
    else_separator: str,
    operator: str,
) -> None:
    query = (
        f"WITH {before_use} AS use, {alternate} AS alt "
        f"RETURN CASE WHEN use >= 0 THEN{then_separator}use{operator}"
        f"{else_separator}ELSE alt END AS value"
    )

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert not result.has_errors


@settings(max_examples=75)
@given(
    key_separator=plain_whitespace,
    value=st.integers(min_value=-100, max_value=100),
)
def test_map_keys_named_use_are_allowed(key_separator: str, value: int) -> None:
    query = f"RETURN {{use:{key_separator}{value}}} AS item"

    result = asyncio.run(_validate_with_mocked_neo4j(query))

    assert not result.has_errors
