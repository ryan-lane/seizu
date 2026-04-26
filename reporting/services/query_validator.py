import asyncio
import re
from dataclasses import dataclass, field
from typing import Any

from CyVer import PropertiesValidator, SchemaValidator

from reporting.services.reporting_neo4j import _get_async_neo4j_client, _get_sync_neo4j_client

_UNICODE_ESCAPE_RE = re.compile(r"\\u([0-9a-fA-F]{4})")

# Keyword scan for dangerous read-path operations that Neo4j classifies as
# query_type='r' but can be used for SSRF or data exfiltration.
#
# \bCALL\s+apoc\.     — APOC procedure calls (e.g. CALL apoc.load.json)
# \bapoc\.cypher\.    — APOC Cypher-execution functions used without CALL
#                       (apoc.cypher.runFirstColumnSingle/Many execute
#                       arbitrary inner Cypher, bypassing this validator)
# \bLOAD\s+CSV\b      — built-in LOAD CSV (also covers SSRF to file://)
_DANGEROUS_RE = re.compile(
    r"\bLOAD\s+CSV\b|\bCALL\s+apoc\.|\bapoc\.cypher\.",
    re.IGNORECASE,
)

# Neo4j administration/catalog commands can be classified as read-only by
# EXPLAIN while still exposing operational metadata or causing side effects
# such as terminating transactions.
_ADMIN_COMMAND_RE = re.compile(
    r"\bSHOW\s+("
    r"ALIASES?|"
    r"CURRENT\s+USER|"
    r"DATABASES?|"
    r"FUNCTIONS?|"
    r"INDEX(?:ES)?|"
    r"PRIVILEGES?|"
    r"PROCEDURES?|"
    r"ROLES?|"
    r"SERVERS?|"
    r"SETTINGS?|"
    r"SUPPORTED\s+PRIVILEGES|"
    r"TRANSACTIONS?|"
    r"USERS?"
    r")\b|"
    r"\bTERMINATE\s+TRANSACTIONS?\b|"
    r"\b(?:START|STOP)\s+DATABASE\b",
    re.IGNORECASE,
)


def _decode_cypher_unicode_escapes(query: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 16))

    return _UNICODE_ESCAPE_RE.sub(replace, query)


def _strip_cypher_comments(query: str) -> str:
    """Replace Cypher comments with spaces using a linear scan.

    This deliberately mirrors the previous conservative behavior: `//` inside a
    string literal is still treated as a comment in the stripped form. The
    validator also scans the original query, so URLs in strings cannot hide
    dangerous tokens that appear later in the raw text.
    """

    stripped: list[str] = []
    index = 0
    query_len = len(query)
    while index < query_len:
        current = query[index]
        next_char = query[index + 1] if index + 1 < query_len else ""

        if current == "/" and next_char == "*":
            stripped.append(" ")
            index += 2
            while index + 1 < query_len and not (query[index] == "*" and query[index + 1] == "/"):
                index += 1
            index = min(index + 2, query_len)
            continue

        if current == "/" and next_char == "/":
            stripped.append(" ")
            index += 2
            while index < query_len and query[index] != "\n":
                index += 1
            continue

        stripped.append(current)
        index += 1

    return "".join(stripped)


def _keyword_scan_targets(query: str) -> tuple[str, ...]:
    decoded = _decode_cypher_unicode_escapes(query)
    stripped = _strip_cypher_comments(query)
    stripped_decoded = _strip_cypher_comments(decoded)
    decoded_stripped = _decode_cypher_unicode_escapes(stripped)
    return query, stripped, decoded, stripped_decoded, decoded_stripped


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
    #
    # We check original, comment-stripped, and unicode-decoded forms:
    # - Stripped catches comment injection (CALL /* x */ apoc., LOAD /* x */ CSV)
    # - Original catches patterns that appear after a '//' inside a string
    #   literal (e.g. a URL like http://...) that the comment stripper would
    #   incorrectly consume, hiding a dangerous token that follows it.
    # - Unicode-decoded catches Cypher escapes in keywords and procedure names
    #   (e.g. SH\u004fW, C\u0041LL apoc., apoc.cyph\u0065r.).
    if any(_DANGEROUS_RE.search(target) or _ADMIN_COMMAND_RE.search(target) for target in _keyword_scan_targets(query)):
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
