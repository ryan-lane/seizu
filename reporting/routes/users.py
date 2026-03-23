from apiflask import abort
from apiflask import APIBlueprint

from reporting import authnz  # noqa: F401
from reporting.authnz import bearer_auth
from reporting.schema.report_config import User
from reporting.services import report_store

blueprint = APIBlueprint("users", __name__)


@blueprint.get("/api/v1/users/<user_id>")
@blueprint.auth_required(bearer_auth)
@blueprint.output(User)
def get_user(user_id: str) -> User:
    """Return a user profile by internal user_id."""
    user = report_store.get_user(user_id)
    if user is None:
        abort(404, message="User not found")
    return user
