import logging
from typing import Any
from typing import Dict
from typing import List

from flask import blueprints
from flask import jsonify
from flask import request
from flask import Response

from reporting.services.reporting_pagerduty import get_session

logger = logging.getLogger(__name__)
blueprint = blueprints.Blueprint("pagerduty", __name__)


@blueprint.route("/api/v1/pagerduty/oncalls", methods=["GET"])
def get_oncalls() -> Response:
    """
    Get current on-calls

    .. :quickref: pagerduty/oncalls; get current on-calls

    **Example request**:

    .. sourcecode:: http

       GET /api/v1/pagerduty/oncalls

    **Example response**:

    .. sourcecode:: http

    HTTP/1.1 200 OK
    Content-Type: application/json

    {
      "user": {},
      "schedule": {},
      "escalation_policy": {},
      ...
    }

    :resheader Content-Type: application/json
    :statuscode 200: success
    """
    params = {}
    user_ids = request.args.get("user_ids")
    if user_ids:
        params["user_ids[]"] = user_ids.split(",")
    escalation_policy_ids = request.args.get("escalation_policy_ids")
    if escalation_policy_ids:
        params["escalation_policy_ids[]"] = escalation_policy_ids.split(",")
    schedule_ids = request.args.get("schedule_ids")
    if schedule_ids:
        params["schedule_ids[]"] = schedule_ids.split(",")
    oncalls: List[Dict[str, Any]] = []
    pd_session = get_session()
    for oncall in pd_session.iter_all("oncalls", params=params):
        oncalls.append(oncall)
    resp = jsonify(
        {
            "oncalls": oncalls,
        },
    )
    return resp
