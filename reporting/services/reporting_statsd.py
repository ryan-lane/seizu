from datadog import initialize

from reporting import settings

options = {
    "statsd_host": settings.STATSD_HOST,
    "statsd_port": settings.STATSD_PORT,
    "statsd_constant_tags": settings.STATSD_CONSTANT_TAGS,
}

initialize(**options)
