from apiflask import APIBlueprint
from flask import g

from reporting import authnz  # noqa: F401
from reporting.authnz import bearer_auth
from reporting.schema.report_config import User

blueprint = APIBlueprint("me", __name__)


@blueprint.get("/api/v1/me")
@blueprint.auth_required(bearer_auth)
@blueprint.output(User)
def get_current_user() -> User:
    """Return the current authenticated user's profile."""
    return authnz.sync_user_profile(g.current_user)
