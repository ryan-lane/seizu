from cypher_guard import CypherParsingError
from cypher_guard import is_read
from CyVer import PropertiesValidator
from CyVer import SchemaValidator
from CyVer import SyntaxValidator

from reporting.services.reporting_neo4j import _get_neo4j_client


class QueryValidationError(Exception):
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__(str(errors))


def _check_read_only(query: str) -> None:
    """Verify the query is read-only using cypher-guard's AST parser."""
    try:
        if not is_read(query):
            raise QueryValidationError(
                ["Write queries are not allowed"]
            )
    except CypherParsingError as e:
        raise QueryValidationError(
            [f"Failed to parse query for read-only check: {e}"]
        )


def validate_query(query: str) -> None:
    errors = []
    driver = _get_neo4j_client()

    syntax_validator = SyntaxValidator(driver)
    is_valid, metadata = syntax_validator.validate(query)
    if not is_valid:
        errors.extend(metadata)
        raise QueryValidationError(errors)

    _check_read_only(query)

    schema_validator = SchemaValidator(driver)
    schema_is_valid, schema_metadata = schema_validator.validate(query)
    if not schema_is_valid:
        errors.extend(schema_metadata)

    properties_validator = PropertiesValidator(driver)
    properties_is_valid, properties_metadata = properties_validator.validate(query)
    if not properties_is_valid:
        errors.extend(properties_metadata)

    if errors:
        raise QueryValidationError(errors)
