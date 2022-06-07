import logging

from flask import blueprints
from flask import jsonify
from flask import Response

from reporting import authnz
from reporting import settings
from reporting.exceptions import UserCreationError
from reporting.services import reporting_neo4j

logger = logging.getLogger(__name__)
blueprint = blueprints.Blueprint("auth", __name__)


@blueprint.route("/api/v1/login", methods=["POST"])
def login() -> Response:
    """
    Validate OAuth headers, and set a cookie with the neo4j username and password.
    Calls to this function will invalidate older credentials.

    .. :quickref: login; set a cookie with neo4j username and password.

    **Example request**:

    .. sourcecode:: http

       POST /api/v1/login

    **Example response**:

    .. sourcecode:: http

    HTTP/1.1 200 OK
    Content-Type: application/json

    {
      "username": "...",
      "password": "..."
    }

    :resheader Content-Type: application/json
    :statuscode 200: success
    :statuscode 403: could not validate OAuth headers
    """
    resp_data = {
        "protocol": settings.NEO4J_USER_PROTOCOL,
        "port": settings.NEO4J_USER_PORT,
        "hostname": settings.NEO4J_USER_HOSTNAME,
        "auth_mode": settings.AUTH_MODE,
    }
    if settings.AUTH_MODE == "auto":
        email = authnz.get_email()
        try:
            password = reporting_neo4j.renew_user(email)
            resp_data["username"] = email
            resp_data["password"] = password
        except UserCreationError:
            resp = jsonify(error="Failed to login.")
            resp.status = 403
            return resp
    resp = jsonify(resp_data)
    return resp
