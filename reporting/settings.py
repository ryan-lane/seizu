from reporting.utils.settings import bool_env, int_env, list_env, str_env

# Whether or not reporting is run in debug mode. Never run reporting in debug
# mode outside of development!
DEBUG = bool_env("DEBUG", False)
# The host the ASGI app should use.
HOST = str_env("HOST", "0.0.0.0")
# The port the ASGI app should use.
PORT = int_env("PORT", 8080)
# The location of the react app build directory
STATIC_FOLDER = str_env("STATIC_FOLDER", "/build")

# The hostname of the statsd server (used by the statsd scheduled query action module)
STATSD_HOST = str_env("STATSD_HOST")
# The port of the statsd server
STATSD_PORT = int_env("STATSD_PORT", 8125)
# A comma separated list of tag_name:tag_value tags to apply to every stat
STATSD_CONSTANT_TAGS = list_env("STATSD_CONSTANT_TAGS")

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
# Internal authority URL used by the server to fetch OIDC discovery documents.
# In most deployments this equals OIDC_AUTHORITY. Set this when the server
# cannot reach the public OIDC_AUTHORITY hostname (e.g. docker dev environments
# with split internal/external hostnames). Defaults to OIDC_AUTHORITY when unset.
OIDC_INTERNAL_AUTHORITY = str_env("OIDC_INTERNAL_AUTHORITY", "")
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
NEO4J_NOTIFICATIONS_MIN_SEVERITY = str_env("NEO4J_NOTIFICATIONS_MIN_SEVERITY", "WARNING")

# Username to connect to neo4j
NEO4J_USER = str_env("NEO4J_USER")

# Password to use for neo4j connection
NEO4J_PASSWORD = str_env("NEO4J_PASSWORD")

# Maximum duration in seconds a driver will keep a connection before being
# removed from its connection pool.
NEO4J_MAX_CONNECTION_LIFETIME = int_env("NEO4J_MAX_CONNECTION_LIFETIME", 3600)

# Timeout in seconds for establishing a Neo4j TCP connection.
NEO4J_CONNECTION_TIMEOUT = int_env("NEO4J_CONNECTION_TIMEOUT", 10)

# Timeout in seconds for Neo4j query execution (server-side transaction timeout).
NEO4J_QUERY_TIMEOUT = int_env("NEO4J_QUERY_TIMEOUT", 30)

# Shared secret used to sign report-query capability tokens.
# Required in normal authenticated deployments. Use a cryptographically random
# value with at least 32 bytes of entropy; 64 bytes is preferred. Encode as hex
# or base64, store it in a secret manager or env var, and keep it stable across
# restarts so report tokens remain valid until they expire. If you use hex,
# 32 bytes = 64 characters and 64 bytes = 128 characters. If you use base64,
# 32 bytes is typically 44 characters with padding. Rotate if exposed.
# In development auth-disabled mode, Seizu can fall back to an in-process
# default so local work still runs.
REPORT_QUERY_SIGNING_SECRET = str_env("REPORT_QUERY_SIGNING_SECRET", "")

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
        "reporting.scheduled_query_modules.statsd",
    ],
)
# NOTE: scheduled query module settings are defined within the modules themselves

# Timeout in seconds for the overall FastAPI request handling. Requests that
# exceed this limit receive a 504 response.
API_REQUEST_TIMEOUT = int_env("API_REQUEST_TIMEOUT", 60)

# Timeout in seconds for JWKS endpoint HTTP requests used to fetch signing keys.
JWKS_FETCH_TIMEOUT = int_env("JWKS_FETCH_TIMEOUT", 10)

# Connection and read timeouts (in seconds) for AWS boto3 clients (DynamoDB, SQS).
AWS_CONNECT_TIMEOUT = int_env("AWS_CONNECT_TIMEOUT", 5)
AWS_READ_TIMEOUT = int_env("AWS_READ_TIMEOUT", 30)

# Timeout in seconds for SQL statement execution (asyncpg/PostgreSQL only).
SQL_STATEMENT_TIMEOUT = int_env("SQL_STATEMENT_TIMEOUT", 30)

# Timeout in seconds for Slack API calls.
SLACK_TIMEOUT = int_env("SLACK_TIMEOUT", 30)

# Whether to enable HSTS (HTTP Strict Transport Security) headers.
# Set to True in production to enforce HTTPS. Disable in development or when
# running behind an SSL-terminating load balancer.
TALISMAN_FORCE_HTTPS = bool_env("TALISMAN_FORCE_HTTPS", True)

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

# Which built-in MCP tool groups are exposed.
# Unset or empty → all groups enabled (default).
# "none"         → all built-in groups disabled (user-defined toolsets unaffected).
# Comma-separated list (e.g. "graph,reports") → only those groups.
# Known groups: graph, reports, roles, scheduled_queries, skillsets, toolsets.
MCP_ENABLED_BUILTINS = list_env("MCP_ENABLED_BUILTINS", [])

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
# Public base URL of the MCP endpoint (e.g. https://seizu.example.com/api/v1/mcp).
# Required for OAuth discovery: used in the WWW-Authenticate resource_metadata
# header and the RFC 9728 protected resource metadata document.
# Leave empty to disable protected-resource metadata.
MCP_RESOURCE_URL = str_env("MCP_RESOURCE_URL", "")
# Override the RFC 7591 dynamic client registration endpoint advertised in the
# OAuth metadata. When unset and both MCP_RESOURCE_URL and OIDC_CLIENT_ID are
# configured, Seizu serves its own lightweight DCR endpoint that returns the
# pre-configured OIDC_CLIENT_ID so MCP clients don't need a DCR-capable IdP.
MCP_OAUTH_REGISTRATION_ENDPOINT = str_env("MCP_OAUTH_REGISTRATION_ENDPOINT", "")
