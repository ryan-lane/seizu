from flask import blueprints
from flask import g
from flask import jsonify
from flask import Response

from reporting import authnz

blueprint = blueprints.Blueprint("me", __name__)


@blueprint.route("/api/v1/me", methods=["GET"])
@authnz.require_auth
def get_current_user() -> Response:
    user = authnz.sync_user_profile(g.current_user)
    return jsonify(user.model_dump())
