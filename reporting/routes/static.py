import os
from typing import Union

from flask import blueprints
from flask import current_app
from flask import jsonify
from flask import render_template
from flask import Response
from flask import send_from_directory

from reporting import settings

blueprint = blueprints.Blueprint("static_files", __name__)


@blueprint.route("/healthcheck")
def healthcheck() -> Response:
    resp = jsonify(success=True)
    resp.status_code = 200
    return resp


@blueprint.route("/", defaults={"path": ""})
@blueprint.route("/<path:path>")
def index(path: str) -> Union[Response, str]:
    # Deliver non-template files that are directly in the root of the static folder, but
    # not in the "static directory" configured for the app
    if path in ["manifest.json", "asset-manifest.json", "favicon.png", "favicon.svg"]:
        return send_from_directory(
            os.path.join(current_app.root_path, settings.STATIC_FOLDER),
            path,
        )
    return render_template("index.html")
