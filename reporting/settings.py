from reporting.utils.settings import bool_env
from reporting.utils.settings import int_env
from reporting.utils.settings import list_env
from reporting.utils.settings import str_env

# Whether or not reporting is run in debug mode. Never run reporting in debug
# mode outside of development!
DEBUG = bool_env("DEBUG", False)
# The host the WSGI app should use.
HOST = str_env("HOST", "0.0.0.0")
# The port the WSGI app should use.
PORT = int_env("PORT", 8080)
# The location of the react app build directory
STATIC_FOLDER = str_env("STATIC_FOLDER", "/build")

# The hostname of the statsd server
STATSD_HOST = str_env("STATSD_HOST")
# The port of the statsd server
STATSD_PORT = int_env("STATSD_PORT", 8125)
# A comma separated list of tag_name:tag_value tags to apply to every stat
STATSD_CONSTANT_TAGS = list_env("STATSD_CONSTANT_TAGS")
# A prefix set by an external aggregator, like telegraf. This can be used
# by the dashboard in the documentation and details views, when showing
# metric names.
STATSD_EXTERNAL_PREFIX = str_env("STATSD_EXTERNAL_PREFIX")
# The external provider being used for metrics. This can be used by the
# dashboard to show example metrics queries in the details view.
# Currently supported values: newrelic
STATSD_EXTERNAL_PROVIDER = str_env("STATSD_EXTERNAL_PROVIDER")

# The location of the logging configuration file
LOG_CONFIG_FILE = str_env(
    "LOG_CONFIG_FILE",
    "/home/seizu/seizu/logging.conf",
)

# Must be set to the region the server is running.
AWS_DEFAULT_REGION = str_env("AWS_DEFAULT_REGION", "ap-northeast-1")

# Auth mode
AUTH_MODE = str_env("AUTH_MODE", "auto")

# JWKS location to use to validate JWT
JWKS_URL = str_env(
    "JWKS_URL",
    "https://public-keys.auth.elb.{AWS_DEFAULT_REGION}.amazonaws.com/{kid}",
)
# AWS ALBs use a URL that fetches a KID directly, while other providers use a URL that has a JSON file with a list
# of keys. Default for this is to be setup behind an ALB, so to use a kid based url.
JWKS_URL_FOR_ALB = bool_env("JWKS_URL_FOR_ALB", True)
# Algorithms we allow for JWT signing
ALLOWED_JWT_ALGORITHMS = list_env("ALLOWED_JWT_ALGORITHMS", ["ES256", "ES512"])
# Whether or not to require authentication.
# This option should only be changed in development.
DEVELOPMENT_ONLY_REQUIRE_AUTH = bool_env("DEVELOPMENT_ONLY_REQUIRE_AUTH", True)
# The email address of the fake user when authentication is disabled.
# This option should only be changed in development.
DEVELOPMENT_ONLY_AUTH_USER_EMAIL = str_env(
    "DEVELOPMENT_ONLY_AUTH_USER_EMAIL",
    "testuser",
)

# URI to connect to neo4j
NEO4J_URI = str_env("NEO4J_URI", "bolt://localhost:7687")

# Username to connect to neo4j
NEO4J_USER = str_env("NEO4J_USER")

# Password to use for neo4j connection
NEO4J_PASSWORD = str_env("NEO4J_PASSWORD")

# Protocol, port, and hostname from the client (javascript) side
NEO4J_USER_PROTOCOL = str_env("NEO4J_USER_PROTOCOL", "bolt+s")
NEO4J_USER_PORT = int_env("NEO4J_USER_PORT", 7687)
NEO4J_USER_HOSTNAME = str_env("NEO4J_USER_HOSTNAME", "localhost")

# URL of the neo4j browser console
NEO4J_CONSOLE_URL = str_env("NEO4J_CONSOLE_URL", "https://localhost:7473")

# Maximum duration in seconds a driver will keep a connection before being
# removed from its connection pool.
NEO4J_MAX_CONNECTION_LIFETIME = int_env("NEO4J_MAX_CONNECTION_LIFETIME", 3600)

# Length of password in bytes to auto-generate for users
GENERATED_PASSWORD_LENGTH = int_env("GENERATED_PASSWORD_LENGTH", 50)

# Time in seconds until generated passwords expire
PASSWORD_EXPIRATION_TIME = int_env("PASSWORD_EXPIRATION_TIME", 24 * 60 * 60)
# The frequency in seconds for how often we'll scan for expired users
USER_SCAN_FREQUENCY = int_env("USER_SCAN_FREQUENCY", 10)
# A comma separated list of users that shouldn't be tracked for expiration (permanent users)
USERS_EXCEMPT_FROM_EXPIRATION = list_env("USERS_EXCEMPT_FROM_EXPIRATION", ["neo4j"])

# Whether or not scheduled queries should be enabled.
ENABLE_SCHEDULED_QUERIES = bool_env("ENABLE_SCHEDULED_QUERIES", True)
# The frequency in seconds for how often we'll attempt to run scheduled queries
SCHEDULED_QUERY_FREQUENCY = int_env("SCHEDULED_QUERY_FREQUENCY", 20)
# Scheduled query modules
SCHEDULED_QUERY_MODULES = list_env(
    "SCHEDULED_QUERY_MODULES",
    [
        "reporting.scheduled_query_modules.sqs",
        "reporting.scheduled_query_modules.slack",
    ],
)
# NOTE: scheduled query module settings are defined within the modules themselves

# Name of the dynamodb table used to track user password time expirations
DYNAMODB_TABLE = str_env("DYNAMODB_TABLE", "seizu")
# Override for the default dynamodb (to use local dynamodb)
DYNAMODB_URL = str_env("DYNAMODB_URL")
# Whether or not to auto-create the dynamodb table
DYNAMODB_CREATE_TABLE = bool_env("DYNAMODB_CREATE_TABLE", False)

# CSRF settings

# Flask session secret key for sessions (needed for CSRF)
SECRET_KEY = str_env("SECRET_KEY")

# Cookie name
CSRF_COOKIE_NAME = str_env("CSRF_COOKIE_NAME", "_csrf_token")
# Header name
CSRF_HEADER_NAME = str_env("CSRF_HEADER_NAME", "X-CSRFToken")
# Use a secure cookie by default.
CSRF_COOKIE_SECURE = bool_env("CSRF_COOKIE_SECURE", True)
# Set the cookie to be usable by javascript by default, since that's our use-case.
CSRF_COOKIE_HTTPONLY = bool_env("CSRF_COOKIE_HTTPONLY", False)
# Set the samesite policy to strict by default, since the site is likely served on the same site.
CSRF_COOKIE_SAMESITE = str_env("CSRF_COOKIE_SAMESITE", "Strict")
# Cookie path
CSRF_COOKIE_PATH = str_env("CSRF_COOKIE_PATH", "/")
# Cookie domain
_CSRF_COOKIE_DOMAIN = str_env("CSRF_COOKIE_DOMAIN", "")
if _CSRF_COOKIE_DOMAIN == "":
    CSRF_COOKIE_DOMAIN = None
else:
    CSRF_COOKIE_DOMAIN = _CSRF_COOKIE_DOMAIN
# Whether or not to check the referrer
CSRF_CHECK_REFERER = bool_env("CSRF_CHECK_REFERER", True)
# Setting that can be used to disable CSRF protection
CSRF_DISABLE = bool_env("CSRF_DISABLE", False)

# YAML config used for dashboard generation and stat reporting
REPORTING_CONFIG_FILE = str_env("REPORTING_CONFIG_FILE", "/reporting-dashboard.conf")

# Maximum number of stats we will generate for panels with inputs
DASHBOARD_STATS_MAX_INPUT_RESULTS = int_env("DASHBOARD_STATS_MAX_INPUT_RESULTS", 100)

# API key for interacting with pagerduty API
PAGERDUTY_API_KEY = str_env("PAGERDUTY_API_KEY")
