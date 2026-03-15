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

seizu will pass configuration to the backend via a configuration endpoint.
It uses this configuration to build the dashboard and reports.
When using the docker image, the defaults for the reporting configuration file and schema file should be sufficient, but you will want to bind mount in the configuration file to the location defined in ``REPORTING_CONFIG_FILE``.

* ``REPORTING_CONFIG_FILE``: location to the dashboard configuration; default: ``/reporting-dashboard.conf``
* ``REPORTING_CONFIG_SCHEMA_FILE``: location to the dashboard configuration jsonschema; default: ``/reporting-dashboard.schema.json``
* ``SECRET_KEY``: Flask session secret key for for sessions and CSRF. Set to some long, random string; default: ``None``

### Neo4j configuration

If you wish you use any of the workers, or SSO, it's necessary to configure access from the backend to Neo4j.

* ``NEO4J_URI``: the URL to connect to neo4j; default: ``bolt://localhost:7687``
* ``NEO4J_USER``: the username to use to connect; default: ``None``
* ``NEO4J_PASSWORD``: the password to use to connect; default: ``None``

### Auth configuration

#### SSO configuration

seizu, when placed behind a load balancer or API gateway that handles OAuth2 and provides a JWT, can validate the JWT and pass the user identity to the backend.

* ``JWKS_URL``: JWKS location to use to validate JWT. ``{AWS_DEFAULT_REGION}`` and ``{kid}`` can be used as template variables; default: ``https://public-keys.auth.elb.{AWS_DEFAULT_REGION}.amazonaws.com/{kid}``
* ``JWKS_URL_FOR_ALB``: AWS ALBs use a URL that fetches a KID directly, while other providers use a URL that has a JSON file with a list of keys. If using an ALB, this should be false, if using a standard JSON file with a list of keys, this should be true; default: ``True``
* ``ALLOWED_JWT_ALGORITHMS``: A comma separated list of algorithms we allow for JWT signing; default: ``ES256,ES512``
* ``DEVELOPMENT_ONLY_REQUIRE_AUTH``: Whether or not to require authentication. This option should only be changed in development; default: ``True``
* ``DEVELOPMENT_ONLY_AUTH_USER_EMAIL``: The email address of the fake user when authentication is disabled. This option should only be changed in development; default: ``testuser``

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
