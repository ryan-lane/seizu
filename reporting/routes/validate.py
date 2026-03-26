from fastapi import APIRouter
from fastapi import Depends

from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.schema.query import QueryRequest
from reporting.schema.query import ValidationResponse
from reporting.services.query_validator import validate_query

router = APIRouter()


@router.post("/api/v1/validate", response_model=ValidationResponse)
async def validate_cypher(
    body: QueryRequest,
    current: CurrentUser = Depends(get_current_user),
) -> ValidationResponse:
    """Validate a Cypher query without executing it."""
    result = await validate_query(body.query, params=body.params)
    return ValidationResponse(
        errors=[str(e) for e in result.errors],
        warnings=[str(w) for w in result.warnings],
    )
