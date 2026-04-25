from fastapi import APIRouter, Depends
from pydantic import BaseModel

from reporting.authnz import CurrentUser, sync_user_profile
from reporting.schema.report_config import User

router = APIRouter()


class MeResponse(BaseModel):
    """Current user profile with resolved permissions."""

    user: User
    permissions: list[str]


@router.get("/api/v1/me", response_model=MeResponse)
async def get_me(current: CurrentUser = Depends(sync_user_profile)) -> MeResponse:
    """Return the current authenticated user's profile and resolved permissions."""
    return MeResponse(
        user=current.user,
        permissions=sorted(current.permissions),
    )
