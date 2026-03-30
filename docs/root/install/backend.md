# Backend Installation & Configuration

## Demo/Quickstart/Development

If you're just wanting to quickly evaluate or demo Seizu, please see the [quickstart documentation](../dev/docker-compose.html#Quickstart).

## Installation using docker image

```bash
# first setup your environment in an env file, according to the configuration instructions
docker pull ghcr.io/paypay/seizu:latest
docker run --env-file <your-env-file> ghcr.io/paypay/seizu:latest
```

## Backend configuration

### Basic configuration

When using the docker image, the defaults should be sufficient for basic configuration.

* ``DEBUG``: Whether or not seizu is run in debug mode. This should never be set outside of development; default: ``False``
* ``HOST``: IP address to listen on; default: ``0.0.0.0``
* ``PORT``: Port to listen on; default: ``8080``
* ``STATIC_FOLDER``: location of the react app build directory; default: ``/build``

### Frontend configuration

seizu passes configuration to the frontend via a configuration endpoint.
Report and dashboard configurations are stored in DynamoDB; use ``seizu seed`` to populate them from a YAML file.

* ``SECRET_KEY``: Secret key used for CSRF token signing. Set to some long, random string; default: ``None``

### Neo4j configuration

* ``NEO4J_URI``: the URL to connect to neo4j; default: ``bolt://localhost:7687``
* ``NEO4J_USER``: the username to use to connect; default: ``None``
* ``NEO4J_PASSWORD``: the password to use to connect; default: ``None``
* ``NEO4J_MAX_CONNECTION_LIFETIME``: maximum duration in seconds a driver will keep a connection before removing it from its pool; default: ``3600``
* ``NEO4J_NOTIFICATIONS_MIN_SEVERITY``: minimum severity for Neo4j query notifications logged by the driver (``WARNING``, ``INFORMATION``, ``OFF``). Set to ``OFF`` to suppress schema warnings when the database is not fully populated; default: ``WARNING``

### Report storage configuration

* ``REPORT_STORE_BACKEND``: storage backend to use for report configurations. Supported values: ``dynamodb`` (default), ``sqlmodel``

### DynamoDB configuration

seizu stores report and dashboard configurations in DynamoDB. In production, standard AWS credential resolution applies (instance profile, environment variables, etc.).

* ``DYNAMODB_TABLE_NAME``: name of the DynamoDB table; default: ``seizu-reports``
* ``DYNAMODB_REGION``: AWS region for DynamoDB; default: ``us-east-1``
* ``DYNAMODB_ENDPOINT_URL``: override the DynamoDB endpoint URL (e.g. ``http://dynamodb:8000`` for local DynamoDB); default: ``""`` (uses AWS endpoint)
* ``DYNAMODB_CREATE_TABLE``: when ``true``, creates the table automatically on startup if it does not exist. Enable in local development; default: ``false``
* ``SNOWFLAKE_MACHINE_ID``: Snowflake ID generator machine ID (0–1023). Set a unique value per instance when running multiple replicas to avoid ID collisions; default: ``1``

### SQL configuration

Used when ``REPORT_STORE_BACKEND=sqlmodel``.

* ``SQL_DATABASE_URL``: SQLAlchemy database URL. Any SQLAlchemy-compatible database is supported. Examples:

  * ``postgresql://user:pass@host:5432/seizu``
  * ``sqlite:///./seizu.db``

  default: ``""``

### Auth configuration

#### OIDC / JWT configuration

seizu validates JWTs using `PyJWKClient` against any standard OIDC JWKS endpoint. Set ``JWKS_URL`` to your provider's JWKS JSON endpoint and configure the frontend OIDC settings so the browser can complete the PKCE flow.

* ``JWKS_URL``: JWKS JSON endpoint used to validate JWTs (e.g. ``https://idp.example.com/application/o/seizu/jwks/``); default: ``""``
* ``JWT_HEADER_NAME``: request header carrying the token; default: ``Authorization``
* ``JWT_EMAIL_CLAIM``: JWT claim for the user's email address; default: ``email``
* ``JWT_ISSUER``: optional issuer to validate in the JWT; default: ``""`` (skips issuer validation)
* ``JWT_AUDIENCE``: optional audience to validate; must match the OIDC client ID when using providers (like Authentik) that always set ``aud``; default: ``""``
* ``ALLOWED_JWT_ALGORITHMS``: comma-separated list of allowed JWT signing algorithms; default: ``RS256,ES256,ES512``
* ``OIDC_AUTHORITY``: OIDC provider base URL; passed to the frontend via ``GET /api/v1/config`` and also added to the ``connect-src`` Content-Security-Policy directive so the browser can reach the discovery document and token endpoint; default: ``""``
* ``OIDC_CLIENT_ID``: OIDC client ID; passed to the frontend; default: ``""``
* ``OIDC_REDIRECT_URI``: OIDC callback URL; passed to the frontend via ``GET /api/v1/config`` but **not used by the frontend** — the browser derives the redirect URI from ``window.location.origin`` so the PKCE callback always returns to the same origin that initiated the flow; default: ``""``
* ``OIDC_SCOPE``: OIDC scope; default: ``openid email``
* ``DEVELOPMENT_ONLY_REQUIRE_AUTH``: whether or not to require authentication. This option should only be changed in development; default: ``True``
* ``DEVELOPMENT_ONLY_AUTH_USER_EMAIL``: the email address of the fake user when authentication is disabled. This option should only be changed in development; default: ``testuser``

#### Security / cookie settings

* ``TALISMAN_FORCE_HTTPS``: redirect HTTP requests to HTTPS and enable HSTS. Set to ``False`` when running behind an SSL-terminating load balancer or in local development; default: ``True``
* ``CSRF_COOKIE_SECURE``: mark the CSRF cookie as ``Secure`` (HTTPS-only). Set to ``False`` when serving over plain HTTP (e.g. local development or behind an SSL-terminating proxy); default: ``True``

### RBAC configuration

Seizu uses Role-Based Access Control (RBAC) to restrict API and MCP access. Every authenticated request has a role resolved from the JWT, which maps to a set of granular permissions.

#### Built-in roles

| Role | Capabilities |
|------|-------------|
| **seizu-viewer** | Read reports and dashboard, run ad-hoc queries, view query history, call tools via API and MCP, read toolsets/scheduled queries/roles |
| **seizu-editor** | All Viewer capabilities + create/edit/delete reports, set default dashboard |
| **seizu-admin** | All Editor capabilities + manage toolsets, tools, scheduled queries, and user-defined roles |

#### Role claim

Seizu reads the user's role from a single JWT claim set by the OIDC provider. Configure your provider to embed the role name (e.g. ``"seizu-admin"``) as a claim in every issued token. Most providers support this via property mappings or claim enrichment rules on group membership.

* ``RBAC_ROLE_CLAIM``: JWT claim name that holds the user's Seizu role; default: ``seizu_role``
* ``RBAC_DEFAULT_ROLE``: Role assigned when the JWT has no ``RBAC_ROLE_CLAIM``. Set to ``""`` to deny access to users without an explicit role claim. Valid values: ``"seizu-viewer"``, ``"seizu-editor"``, ``"seizu-admin"``, or any user-defined role name; default: ``"seizu-viewer"``

**Authentik example** — create a Property Mapping with expression:

```python
seizu_group_role_map = {
    "seizu-admins": "seizu-admin",
    "seizu-editors": "seizu-editor",
}
for group in request.user.ak_groups.all():
    if group.name in seizu_group_role_map:
        return seizu_group_role_map[group.name]
return "seizu-viewer"
```

Bind the mapping to the Seizu OAuth2 provider as a custom token property mapping with scope ``openid``.

#### User-defined roles

Admins can create custom roles with arbitrary permission subsets via the API (``POST /api/v1/roles``). When a JWT contains a user-defined role name in ``RBAC_ROLE_CLAIM``, Seizu does a single database lookup to resolve its permissions. Built-in role resolution requires no database I/O.

### MCP server

Seizu exposes a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server at ``/api/v1/mcp``, allowing LLM agents such as Claude to query the Neo4j graph database using user-defined tools.

* ``MCP_ENABLED``: Enable or disable the MCP server endpoint. Set to ``False`` to turn off the endpoint entirely; default: ``True``

#### MCP OAuth metadata (optional)

When ``MCP_OAUTH_AUTHORIZATION_ENDPOINT`` and ``MCP_OAUTH_TOKEN_ENDPOINT`` are set, Seizu publishes an [RFC 8414](https://datatracker.ietf.org/doc/html/rfc8414) OAuth 2.0 Authorization Server Metadata document at ``/api/v1/mcp/.well-known/oauth-authorization-server``. MCP clients that support in-client authentication (e.g. Claude Desktop) can use this endpoint to discover the OIDC provider and authenticate users without a pre-issued token.

* ``MCP_OAUTH_AUTHORIZATION_ENDPOINT``: OIDC authorization endpoint URL; default: ``""`` (metadata endpoint disabled)
* ``MCP_OAUTH_TOKEN_ENDPOINT``: OIDC token endpoint URL; default: ``""`` (metadata endpoint disabled)
* ``MCP_OAUTH_ISSUER``: Issuer value for the metadata document. Defaults to ``JWT_ISSUER`` if unset; default: ``""``

### Scheduled queries

* ``ENABLE_SCHEDULED_QUERIES``: Whether or not scheduled queries should be enabled. Note that if the worker is not running, scheduled queries will not run, even if this is set to true; default: ``True``
* ``SCHEDULED_QUERY_FREQUENCY``: The frequency in seconds for how often we'll attempt to run scheduled queries; default: ``20``
* ``SCHEDULED_QUERY_MODULES``: A comma separated list of python import locations for available scheduled query modules; default: ``reporting.scheduled_query_modules.sqs,reporting.scheduled_query_modules.slack``

### Statsd configuration

Through the stats worker, seizu can send the results of queries configured in the dashboard configuration to your time series service, via statsd.
Note that the statsd support uses tags, so your time series database must also support tagging (like datadog, new relic, etc), and the statsd server your sending to must also support tags (like telegraf, with datadog extensions enabled).

* ``STATSD_HOST``: The hostname of the statsd server; default: ``None``
* ``STATSD_PORT``: The port of the statsd server; default: ``8125``
* ``STATSD_CONSTANT_TAGS``: A comma separated list of ``tag_name:tag_value`` tags to apply to every stat; default: ``None``
* ``DASHBOARD_STATS_MAX_INPUT_RESULTS``: When sending stats for panels that have an input, only send stats if the number of values in the input is less than this number; default: ``100``;

### Logging configuration

seizu ships with a sane json structured logging configuration, and good defaults, but you can override them via a config file.
Note that this setting is for the workers.
You'll also need to change gunicorn's logging configuration file setting to change the web process.

* ``LOG_CONFIG_FILE``: Location of the logging configuration file; default: ``/home/seizu/seizu/logging.conf``
