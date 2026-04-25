import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from CyVer import PropertiesValidator, SchemaValidator

from reporting.services.reporting_neo4j import _get_async_neo4j_client, _get_sync_neo4j_client

# Keyword scan for dangerous read-path operations that Neo4j classifies as
# query_type='r' but can be used for SSRF or data exfiltration.
_DANGEROUS_RE = re.compile(
    r"\bLOAD\s+CSV\b|\bCALL\s+apoc\.",
    re.IGNORECASE,
)


@dataclass
class ValidationResult:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


async def validate_query(query: str, params: dict[str, Any] | None = None) -> ValidationResult:
    result = ValidationResult()
    driver = _get_async_neo4j_client()

    # Syntax validation and write detection via EXPLAIN.
    # EXPLAIN never executes the query (no side effects).  The returned summary
    # includes query_type: 'r' (read), 'w' (write), 'rw' (read-write), or 's'
    # (schema).  We only permit 'r'.  Params are forwarded so Neo4j can plan
    # parameterized queries correctly, avoiding false ParameterNotProvided errors.
    try:
        _, summary, _ = await driver.execute_query(
            f"EXPLAIN {query}",
            parameters_=params or {},
        )
        if summary.query_type != "r":
            result.errors.append("Write queries are not allowed")
            return result
        if summary.notifications:
            for notification in summary.notifications:
                code = notification.get("code", "")
                description = notification.get("description", str(notification))
                if code == "Neo.ClientNotification.Statement.ParameterNotProvided":
                    # When params are omitted (e.g. /api/v1/validate called
                    # without params), surface as a warning rather than
                    # blocking the caller.
                    result.warnings.append(description)
                elif code in (
                    "Neo.DatabaseError.Statement.ExecutionFailed",
                    "Neo.ClientError.Statement.SyntaxError",
                    "Neo.ClientNotification.Statement.UnsatisfiableRelationshipTypeExpression",
                ):
                    result.errors.append(description)
    except Exception as e:
        error_msg = getattr(e, "message", str(e))
        if "EXPLAIN" in error_msg:
            error_msg = error_msg.split("EXPLAIN")[0].strip('"')
        result.errors.append(error_msg)
        return result

    if result.has_errors:
        return result

    # SSRF / exfiltration guard — Neo4j classifies LOAD CSV and APOC HTTP
    # procedures as query_type='r', so they pass the check above.
    # Reject them explicitly before allowing the query to execute.
    if _DANGEROUS_RE.search(query):
        result.errors.append("Write queries are not allowed")
        return result

    # Schema validation — warning, query still executes
    # CyVer validators are synchronous; run them in a thread pool.
    sync_driver = _get_sync_neo4j_client()
    schema_validator = SchemaValidator(sync_driver)
    schema_is_valid, schema_metadata = await asyncio.to_thread(schema_validator.validate, query)
    if not schema_is_valid:
        result.warnings.extend(schema_metadata)

    # Property validation — warning, query still executes
    properties_validator = PropertiesValidator(sync_driver)
    properties_is_valid, properties_metadata = await asyncio.to_thread(properties_validator.validate, query)
    if not properties_is_valid:
        result.warnings.extend(properties_metadata)

    return result
