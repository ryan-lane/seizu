from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from reporting.authnz import CurrentUser, require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import QueryHistoryItem, QueryHistoryListResponse
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


@router.get("/api/v1/query-history/{history_id}", response_model=QueryHistoryItem)
async def get_query_history_item(
    history_id: str,
    current: CurrentUser = Depends(require_permission(Permission.QUERY_HISTORY_READ)),
) -> Any:
    """Return a single query history item by ID, scoped to the current user."""
    item = await report_store.get_query_history_item(
        user_id=current.user.user_id,
        history_id=history_id,
    )
    if item is None:
        return JSONResponse(content={"error": "Not found"}, status_code=404)
    return item
