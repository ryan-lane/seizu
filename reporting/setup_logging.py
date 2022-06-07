import logging.config
import os.path

import yaml

from reporting import settings


try:
    with open(settings.LOG_CONFIG_FILE, "r") as fd:
        logconfig = yaml.safe_load(os.path.expandvars(fd.read()))
        logging.config.dictConfig(logconfig)
        logger = logging.getLogger(__name__)
except FileNotFoundError:
    logger = logging.getLogger(__name__)
    logger.warning(
        f"{settings.LOG_CONFIG_FILE} not found; skipping logging configuration",
    )
except Exception:
    logger = logging.getLogger(__name__)
    logger.exception(
        f"Failed to load {settings.LOG_CONFIG_FILE}; skipping logging configuration",
    )
