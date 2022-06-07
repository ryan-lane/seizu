from flask import blueprints
from flask import jsonify
from flask import Response

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

    {
      "console_url": "..."
    }

    :resheader Content-Type: application/json
    :statuscode 200: success
    """
    config = reporting_config.ReportingConfig.Schema().dump(
        reporting_config.load_file(settings.REPORTING_CONFIG_FILE)
    )
    schema = reporting_config.output_json_schema()
    pagerduty_enabled = False
    if settings.PAGERDUTY_API_KEY:
        pagerduty_enabled = True
    resp = jsonify(
        {
            "console_url": settings.NEO4J_CONSOLE_URL,
            "pagerduty_enabled": pagerduty_enabled,
            "stats": {
                "external_provider": settings.STATSD_EXTERNAL_PROVIDER,
                "external_prefix": settings.STATSD_EXTERNAL_PREFIX,
            },
            "config": config,
            "schema": schema,
        },
    )
    return resp
