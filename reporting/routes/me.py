from fastapi import APIRouter
from fastapi import Depends

from reporting.authnz import CurrentUser
from reporting.authnz import sync_user_profile
from reporting.schema.report_config import User

router = APIRouter()


@router.get("/api/v1/me", response_model=User)
async def get_me(current: CurrentUser = Depends(sync_user_profile)) -> User:
    """Return the current authenticated user's profile."""
    return current.user
