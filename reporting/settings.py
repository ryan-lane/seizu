from reporting.utils.settings import bool_env
from reporting.utils.settings import int_env
from reporting.utils.settings import list_env
from reporting.utils.settings import str_env

# Whether or not reporting is run in debug mode. Never run reporting in debug
# mode outside of development!
DEBUG = bool_env("DEBUG", False)
# The host the ASGI app should use.
HOST = str_env("HOST", "0.0.0.0")
# The port the ASGI app should use.
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

# Standard JWKS endpoint used to validate JWTs. Must be a JSON endpoint returning a
# {"keys": [...]} JWK Set. Works with any standard OIDC provider.
# Example: https://authentik.example.com/application/o/myapp/jwks/
# Example: https://cognito-idp.{region}.amazonaws.com/{userPoolId}/.well-known/jwks.json
JWKS_URL = str_env("JWKS_URL", "")
# Algorithms we allow for JWT signing
ALLOWED_JWT_ALGORITHMS = list_env("ALLOWED_JWT_ALGORITHMS", ["RS256", "ES256", "ES512"])
# The request header from which the JWT is read.
# Use "Authorization" (default) for standard Bearer token auth (e.g. OIDC PKCE).
# Use "x-amzn-oidc-data" for backwards compatibility with AWS ALB OIDC headers.
JWT_HEADER_NAME = str_env("JWT_HEADER_NAME", "Authorization")
# The JWT claim that contains the user's email address.
JWT_EMAIL_CLAIM = str_env("JWT_EMAIL_CLAIM", "email")
# The JWT claim that contains the user's subject identifier.
# The OIDC standard claim is "sub" and it should not be changed in most cases.
JWT_SUB_CLAIM = str_env("JWT_SUB_CLAIM", "sub")
# The JWT claim that contains the token issuer.
# The OIDC standard claim is "iss" and it should not be changed in most cases.
JWT_ISS_CLAIM = str_env("JWT_ISS_CLAIM", "iss")
# Optional issuer to validate in the JWT. Leave empty to skip issuer validation.
JWT_ISSUER = str_env("JWT_ISSUER", "")
# Optional audience to validate in the JWT. Leave empty to skip audience validation.
JWT_AUDIENCE = str_env("JWT_AUDIENCE", "")
# OIDC configuration surfaced to the frontend via GET /api/v1/config.
# When DEVELOPMENT_ONLY_REQUIRE_AUTH is True, these are included in the config
# response so the frontend can build its UserManager without build-time env vars.
OIDC_AUTHORITY = str_env("OIDC_AUTHORITY", "")
OIDC_CLIENT_ID = str_env("OIDC_CLIENT_ID", "")
OIDC_REDIRECT_URI = str_env("OIDC_REDIRECT_URI", "")
OIDC_SCOPE = str_env("OIDC_SCOPE", "openid email")

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

# Minimum severity level for Neo4j query notifications logged by the driver.
# Valid values: WARNING (default), INFORMATION, OFF.
# Set to OFF to suppress schema warnings about missing labels/properties when
# the database is not fully populated (e.g. in development).
NEO4J_NOTIFICATIONS_MIN_SEVERITY = str_env(
    "NEO4J_NOTIFICATIONS_MIN_SEVERITY", "WARNING"
)

# Username to connect to neo4j
NEO4J_USER = str_env("NEO4J_USER")

# Password to use for neo4j connection
NEO4J_PASSWORD = str_env("NEO4J_PASSWORD")

# Maximum duration in seconds a driver will keep a connection before being
# removed from its connection pool.
NEO4J_MAX_CONNECTION_LIFETIME = int_env("NEO4J_MAX_CONNECTION_LIFETIME", 3600)

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

# Whether to enable HSTS (HTTP Strict Transport Security) headers.
# Set to True in production to enforce HTTPS. Disable in development or when
# running behind an SSL-terminating load balancer.
TALISMAN_FORCE_HTTPS = bool_env("TALISMAN_FORCE_HTTPS", True)

# Maximum number of stats we will generate for panels with inputs
DASHBOARD_STATS_MAX_INPUT_RESULTS = int_env("DASHBOARD_STATS_MAX_INPUT_RESULTS", 100)

# DynamoDB settings for report config storage
# Name of the DynamoDB table used to store report configs and version history
DYNAMODB_TABLE_NAME = str_env("DYNAMODB_TABLE_NAME", "seizu-reports")
# AWS region for DynamoDB. Falls back to boto3 default chain if unset.
DYNAMODB_REGION = str_env("DYNAMODB_REGION", "us-east-1")
# Override the DynamoDB endpoint URL, e.g. http://dynamodb:8000 for local dev.
# Leave empty to use the default AWS endpoint.
DYNAMODB_ENDPOINT_URL = str_env("DYNAMODB_ENDPOINT_URL", "")
# When true, the table is created automatically on startup if it does not exist.
# Enable this in local development against DynamoDB Local.
DYNAMODB_CREATE_TABLE = bool_env("DYNAMODB_CREATE_TABLE", False)
# Snowflake ID generator machine ID (0–1023). Set a unique value per instance
# when running multiple replicas to avoid ID collisions.
SNOWFLAKE_MACHINE_ID = int_env("SNOWFLAKE_MACHINE_ID", 1)
# Report storage backend. Supported values: "dynamodb" (default), "sqlmodel".
REPORT_STORE_BACKEND = str_env("REPORT_STORE_BACKEND", "dynamodb")
# SQLAlchemy database URL used when REPORT_STORE_BACKEND=sqlmodel.
# Any SQLAlchemy-compatible URL works (PostgreSQL, SQLite, MySQL, etc.).
# Example: postgresql://seizu:seizu@postgres:5432/seizu
# Example: sqlite:///./seizu.db
SQL_DATABASE_URL = str_env("SQL_DATABASE_URL", "")

# The JWT claim that contains the user's Seizu role name.
# Configure your OIDC provider to embed the role (e.g. "seizu-admin") directly
# as a claim in the token. Common claim names: "seizu_role", "role".
RBAC_ROLE_CLAIM = str_env("RBAC_ROLE_CLAIM", "seizu_role")

# Default role assigned when a user's JWT has no RBAC_ROLE_CLAIM.
# Set to "" to deny access to users without an explicit role claim.
# Valid values: "seizu-viewer", "seizu-editor", "seizu-admin", or any user-defined role name.
RBAC_DEFAULT_ROLE = str_env("RBAC_DEFAULT_ROLE", "seizu-viewer")

# Whether to enable the MCP server at /api/v1/mcp.
MCP_ENABLED = bool_env("MCP_ENABLED", True)

# OAuth 2.0 Authorization Server Metadata (RFC 8414) for MCP clients.
# When set, Seizu exposes /.well-known/oauth-authorization-server so MCP clients
# (e.g. Claude Desktop) can discover the OAuth flow and authenticate users
# without requiring a pre-issued token.
# Set these to the authorization and token endpoints of your OIDC provider.
# Example (Authentik): https://authentik.example.com/application/o/seizu/authorize/
# Leave empty to disable the metadata endpoint.
MCP_OAUTH_ISSUER = str_env("MCP_OAUTH_ISSUER", "")
MCP_OAUTH_AUTHORIZATION_ENDPOINT = str_env("MCP_OAUTH_AUTHORIZATION_ENDPOINT", "")
MCP_OAUTH_TOKEN_ENDPOINT = str_env("MCP_OAUTH_TOKEN_ENDPOINT", "")
