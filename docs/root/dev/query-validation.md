# Query validation

Seizu validates Cypher before it is executed by the Query Console, report query execution, scheduled queries, MCP graph queries, and Cypher-backed MCP tools. The validator is implemented in `reporting/services/query_validator.py`.

The validator is a security guardrail for user-provided and configuration-provided Cypher. It is not a replacement for Neo4j authentication, network controls, RBAC, or careful permission assignment. Users who can run read queries can still read data available to the configured Neo4j user.

## Validation flow

Validation runs in layers:

1. Neo4j `EXPLAIN` checks syntax and query classification. Only read-classified queries are allowed; write, read-write, schema, and DBMS operations are blocked.
2. Seizu scans the original query, a comment-stripped query, and Cypher Unicode-decoded forms for dangerous constructs that can be read-classified by Neo4j.
3. Procedure calls are checked against a default allowlist of side-effect-free built-in schema procedures.
4. CyVer schema and property validators run after blocking checks. These produce warnings only; warnings do not prevent execution.

The regex guard currently blocks:

- `LOAD CSV`, including comment and Unicode obfuscation variants.
- Neo4j administration and catalog commands such as `SHOW`, database management, privilege management, and server management.
- `USE` clauses that route a query to another graph or database.
- Procedure calls outside the allowlist, including plugin and custom procedures.
- Dangerous function namespaces that can execute dynamic Cypher, create graph-catalog state, or send data to external model providers, such as `apoc.cypher.*`, `gds.*`, `ai.*`, and `genai.*`.

## Procedure allowlist

The default procedure allowlist is intentionally small. It permits read-only schema introspection procedures such as `db.labels`, `db.relationshipTypes`, `db.propertyKeys`, and `db.schema.*`.

Operators can allow extra procedures with `QUERY_VALIDATOR_ALLOWED_PROCEDURES`. The setting is a comma-separated list:

```bash
QUERY_VALIDATOR_ALLOWED_PROCEDURES=apoc.meta.stats,custom.readOnlyProcedure,gds.
```

Each entry is either an exact procedure name or a namespace prefix ending in a dot. Prefixes allow matching `CALL` procedure invocations only. They do not permit dangerous function namespaces in the same namespace; for example, `apoc.` does not permit `apoc.cypher.*`, and `gds.` does not permit `gds.*` functions.

Use exact procedure names when possible. Namespace prefixes are broader and should only be used when every procedure in that namespace is acceptable for the Seizu deployment.

## Changing validation behavior

When changing validation, update the centralized case lists in `tests/query_validator_cases.py` first. The unit and live integration suites both import those cases, which keeps mocked and Neo4j-backed regression coverage aligned.

For each new risky Cypher feature or bypass attempt:

1. Add the query to the appropriate case family in `tests/query_validator_cases.py`.
2. Add or update targeted unit tests in `tests/unit/reporting/services/query_validator_test.py` when the behavior depends on settings or validator internals.
3. Append a row to `tests/data/query-fuzzing.csv` with the technique, query, observed result, blocking layer, and notes.
4. Update `reporting/services/query_validator.py`.
5. If you add or change a setting, update `.env.example` and the backend configuration docs.

Prefer tests that show both sides of a rule: the dangerous form is blocked, and a nearby legitimate read-only form remains allowed. This is especially important for clause-start regexes and procedure-call parsing.

## Validator test workflow

Run the unit regression suite after any validator change:

```bash
docker compose run --rm seizu uv run --frozen --no-sync pytest tests/unit/reporting/services/query_validator_test.py -v
```

Run the live Neo4j-backed suite when the change depends on real Cypher parsing, query classification, Neo4j version behavior, or plugin behavior:

```bash
make test_query_validator_live
```

To compare the configured development Neo4j version with the latest supported Neo4j image, switch versions and rerun the live suite:

```bash
make neo4j_current
make down && make up
make test_query_validator_live

make neo4j_latest
make down && make up
make test_query_validator_live
```

The latest-version target uses a separate Neo4j data volume so the normal development database is not upgraded in place.

Before opening a pull request, run the normal project checks:

```bash
pre-commit run --all-files
make docs
```
