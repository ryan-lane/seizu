from typing import Dict
from typing import Optional

from flask import Flask
from flask_seasurf import SeaSurf
from flask_talisman import Talisman

from reporting import settings
from reporting.routes import config
from reporting.routes import me
from reporting.routes import query
from reporting.routes import reports
from reporting.routes import scheduled_queries
from reporting.routes import static
from reporting.routes import users
from reporting.routes import validate
from reporting.services import report_store


CSP_POLICY = {
    "default-src": ["'self'"],
    "connect-src": ["'self'"],
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
        force_https=settings.TALISMAN_FORCE_HTTPS,
        content_security_policy=CSP_POLICY,
        # Add a nonce to inline scripts in the react app. When we can remove unsafe-inline from style-src,
        # we should inject the nonce here.
        content_security_policy_nonce_in=["script-src"],
    )

    csrf = SeaSurf(app)

    app.register_blueprint(config.blueprint)
    app.register_blueprint(me.blueprint)
    app.register_blueprint(query.blueprint)
    app.register_blueprint(reports.blueprint)
    app.register_blueprint(scheduled_queries.blueprint)
    app.register_blueprint(users.blueprint)
    app.register_blueprint(validate.blueprint)
    app.register_blueprint(static.blueprint)

    should_init = settings.DYNAMODB_CREATE_TABLE or (
        settings.REPORT_STORE_BACKEND == "sqlmodel"
    )
    if should_init:
        with app.app_context():
            report_store.initialize()

    # No CSRF cookie on healthcheck
    csrf.exempt_urls("/healthcheck")

    # Disable STS on healthcheck
    with app.app_context():
        healthcheck = app.view_functions["static_files.healthcheck"]
        setattr(healthcheck, "talisman_view_options", {"force_https": False})

    return app
