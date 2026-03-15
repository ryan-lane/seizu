from dataclasses import dataclass
from dataclasses import field

from cypher_guard import CypherParsingError
from cypher_guard import is_read
from CyVer import PropertiesValidator
from CyVer import SchemaValidator
from CyVer import SyntaxValidator

from reporting.services.reporting_neo4j import _get_neo4j_client


@dataclass
class ValidationResult:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def validate_query(query: str) -> ValidationResult:
    result = ValidationResult()
    driver = _get_neo4j_client()

    # Syntax validation — error, cannot proceed without valid syntax
    syntax_validator = SyntaxValidator(driver)
    is_valid, metadata = syntax_validator.validate(query)
    if not is_valid:
        result.errors.extend(metadata)
        return result

    # Read-only enforcement via cypher-guard — error
    # Raises CypherParsingError on invalid or unsupported syntax, which is
    # treated as a security-safe rejection.
    try:
        if not is_read(query):
            result.errors.append("Write queries are not allowed")
            return result
    except CypherParsingError as e:
        result.errors.append(
            f"Query has invalid syntax or uses unsupported Cypher clauses: {e}"
        )
        return result

    # Schema validation — warning, query still executes
    schema_validator = SchemaValidator(driver)
    schema_is_valid, schema_metadata = schema_validator.validate(query)
    if not schema_is_valid:
        result.warnings.extend(schema_metadata)

    # Property validation — warning, query still executes
    properties_validator = PropertiesValidator(driver)
    properties_is_valid, properties_metadata = properties_validator.validate(query)
    if not properties_is_valid:
        result.warnings.extend(properties_metadata)

    return result
