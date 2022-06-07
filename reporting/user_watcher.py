import logging
import signal
import time

import neo4j.exceptions
from flask import Flask
from flask.cli import AppGroup

from reporting import settings
from reporting import setup_logging  # noqa:F401
from reporting.services import reporting_neo4j

logger = logging.getLogger(__name__)

STATE = {
    "shutdown": False,
}

app = Flask(__name__)
user_cli = AppGroup("worker")
app.cli.add_command(user_cli)


def _is_shutdown() -> bool:
    global STATE

    return STATE["shutdown"]


def _bootstrap() -> None:
    global STATE

    # To exit cleanly, let's catch a SIGTERM signal and set the state to shutdown.
    # This will cause the infinite loop to exit on next run

    # not going to lie, I'm too lazy to find the typing here and it's a
    # known documented pattern
    def finalizer(signal, frame):  # type: ignore
        logger.info("SIGTERM caught, shutting down")
        STATE["shutdown"] = True

    signal.signal(signal.SIGTERM, finalizer)


@user_cli.command("watch-users")
def watch_users() -> None:
    _bootstrap()
    while not _is_shutdown():
        logger.info("Scanning for expired users...")
        try:
            reporting_neo4j.delete_expired_users()
        except neo4j.exceptions.ServiceUnavailable:
            logger.warning("Unable to connect to neo4j, retrying...")
        # check again that we're not shutdown, so we don't wait around for a minute for no reason.
        if not _is_shutdown():
            time.sleep(settings.USER_SCAN_FREQUENCY)
