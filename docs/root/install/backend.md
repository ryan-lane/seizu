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

* ``SECRET_KEY``: Flask session secret key for sessions and CSRF. Set to some long, random string; default: ``None``

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
* ``OIDC_AUTHORITY``: OIDC provider base URL; passed to the frontend via ``GET /api/v1/config``; default: ``""``
* ``OIDC_CLIENT_ID``: OIDC client ID; passed to the frontend; default: ``""``
* ``OIDC_REDIRECT_URI``: OIDC callback URL (browser-reachable); passed to the frontend; default: ``""``
* ``OIDC_SCOPE``: OIDC scope; default: ``openid email``
* ``DEVELOPMENT_ONLY_REQUIRE_AUTH``: whether or not to require authentication. This option should only be changed in development; default: ``True``
* ``DEVELOPMENT_ONLY_AUTH_USER_EMAIL``: the email address of the fake user when authentication is disabled. This option should only be changed in development; default: ``testuser``

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
