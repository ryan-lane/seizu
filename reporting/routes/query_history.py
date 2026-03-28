from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query

from reporting.authnz import CurrentUser
from reporting.authnz import get_current_user
from reporting.schema.report_config import QueryHistoryListResponse
from reporting.services import report_store

router = APIRouter()


@router.get("/api/v1/query-history", response_model=QueryHistoryListResponse)
async def list_query_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
) -> Any:
    """Return the authenticated user's query history, paginated newest-first.

    History is strictly scoped to the calling user — other users' history is
    never returned.
    """
    items, total = await report_store.list_query_history(
        user_id=current.user.user_id,
        page=page,
        per_page=per_page,
    )
    return QueryHistoryListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )
