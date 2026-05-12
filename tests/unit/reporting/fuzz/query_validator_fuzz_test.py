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
