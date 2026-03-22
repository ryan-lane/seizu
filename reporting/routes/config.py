from flask import blueprints
from flask import jsonify
from flask import Response

from reporting import scheduled_query_modules
from reporting import settings
from reporting.schema import reporting_config

blueprint = blueprints.Blueprint("config", __name__)


@blueprint.route("/api/v1/config", methods=["GET"])
def get_config() -> Response:
    """
    Get frontend configuration.

    .. :quickref: config; get frontend configuration data

    **Example request**:

    .. sourcecode:: http

       GET /api/v1/config

    **Example response**:

    .. sourcecode:: http

    HTTP/1.1 200 OK
    Content-Type: application/json

    {}

    :resheader Content-Type: application/json
    :statuscode 200: success
    """
    schema = reporting_config.output_json_schema()
    oidc_config = None
    if settings.OIDC_AUTHORITY:
        oidc_config = {
            "authority": settings.OIDC_AUTHORITY,
            "client_id": settings.OIDC_CLIENT_ID,
            "redirect_uri": settings.OIDC_REDIRECT_URI,
            "scope": settings.OIDC_SCOPE,
        }
    action_schemas = {
        name: [f.model_dump() for f in fields]
        for name, fields in scheduled_query_modules.get_action_schemas().items()
    }
    resp = jsonify(
        {
            "auth_required": settings.DEVELOPMENT_ONLY_REQUIRE_AUTH,
            "oidc": oidc_config,
            "stats": {
                "external_provider": settings.STATSD_EXTERNAL_PROVIDER,
                "external_prefix": settings.STATSD_EXTERNAL_PREFIX,
            },
            "scheduled_query_action_types": scheduled_query_modules.get_configured_action_names(),
            "scheduled_query_action_schemas": action_schemas,
            "config": {},
            "schema": schema,
        },
    )
    return resp
