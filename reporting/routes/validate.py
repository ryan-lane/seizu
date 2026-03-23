from apiflask import APIBlueprint

from reporting import authnz  # noqa: F401
from reporting.authnz import bearer_auth
from reporting.schema.query import QueryRequest
from reporting.schema.query import ValidationResponse
from reporting.services.query_validator import validate_query

blueprint = APIBlueprint("validate", __name__)


@blueprint.post("/api/v1/validate")
@blueprint.auth_required(bearer_auth)
@blueprint.input(QueryRequest, arg_name="body")
@blueprint.output(ValidationResponse)
def validate_cypher(body: QueryRequest) -> ValidationResponse:
    """Validate a Cypher query without executing it."""
    result = validate_query(body.query, params=body.params)
    return ValidationResponse(
        errors=[str(e) for e in result.errors],
        warnings=[str(w) for w in result.warnings],
    )
