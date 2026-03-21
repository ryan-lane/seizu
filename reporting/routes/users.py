from flask import blueprints
from flask import jsonify
from flask import Response

from reporting import authnz
from reporting.services import report_store

blueprint = blueprints.Blueprint("users", __name__)


@blueprint.route("/api/v1/users/<user_id>", methods=["GET"])
@authnz.require_auth
def get_user(user_id: str) -> Response:
    user = report_store.get_user(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.model_dump())
