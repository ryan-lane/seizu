from typing import Any

from fastapi import APIRouter, Depends, Query

from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import QueryHistoryListResponse
from reporting.services import report_store

router = APIRouter()


@router.get("/api/v1/query-history", response_model=QueryHistoryListResponse)
async def list_query_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current: CurrentUser = Depends(require_permission(Permission.QUERY_HISTORY_READ)),
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
