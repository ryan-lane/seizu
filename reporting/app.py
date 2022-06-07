from typing import Dict
from typing import Optional

from flask import Flask
from flask_seasurf import SeaSurf
from flask_talisman import Talisman

from reporting import settings
from reporting.routes import auth
from reporting.routes import config
from reporting.routes import pagerduty
from reporting.routes import static


if settings.NEO4J_USER_PROTOCOL == "bolt":
    _scheme = "ws"
elif settings.NEO4J_USER_PROTOCOL == "bolt+s":
    _scheme = "wss"
else:
    _scheme = settings.NEO4J_USER_PROTOCOL
_connect_src = f"{_scheme}://{settings.NEO4J_USER_HOSTNAME}:{settings.NEO4J_USER_PORT}"

CSP_POLICY = {
    "default-src": ["'self'"],
    "connect-src": ["'self'", _connect_src],
    # issues in material-ui
    "style-src": ["'self'", "'unsafe-inline'"],
    "script-src-elem": ["'self'"],
}


def create_app(override_settings: Optional[Dict] = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=settings.STATIC_FOLDER,
        static_folder=f"{settings.STATIC_FOLDER}/static",
    )
    app.config.from_object(settings)
    if override_settings:
        app.config.update(override_settings)

    csp = Talisman()
    csp.init_app(
        app,
        content_security_policy=CSP_POLICY,
        # Add a nonce to inline scripts in the react app. When we can remove unsafe-inline from style-src,
        # we should inject the nonce here.
        content_security_policy_nonce_in=["script-src"],
    )

    csrf = SeaSurf(app)

    app.register_blueprint(auth.blueprint)
    app.register_blueprint(config.blueprint)
    app.register_blueprint(pagerduty.blueprint)
    app.register_blueprint(static.blueprint)

    # No CSRF cookie on healthcheck
    csrf.exempt_urls("/healthcheck")

    # Disable STS on healthcheck
    with app.app_context():
        healthcheck = app.view_functions["static_files.healthcheck"]
        setattr(healthcheck, "talisman_view_options", {"force_https": False})

    return app
