from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from reporting.authnz import CurrentUser
from reporting.authnz import require_permission
from reporting.authnz.permissions import Permission
from reporting.schema.report_config import User
from reporting.services import report_store

router = APIRouter()


@router.get("/api/v1/users/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    current: CurrentUser = Depends(require_permission(Permission.USERS_READ)),
) -> User:
    """Return a user profile by internal user_id."""
    user = await report_store.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
