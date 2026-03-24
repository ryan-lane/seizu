# Agent Guidelines

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Seizu?

Seizu (星図) is a configuration-driven reporting platform for Neo4j graph data. It has three main runtimes:

- **Flask web app** (`reporting/`) — serves the React frontend and a REST API
- **Scheduled query worker** (`reporting/scheduled_queries.py`) — runs Cypher queries on a schedule with pluggable action plugins (SQS, Slack, log); reads scheduled queries from the database (not the YAML config file)
- **Dashboard stats worker** (`reporting/dashboard_stats.py`) — pushes panel metrics into StatsD/Telegraf

## Running Commands with Docker

This project uses Docker Compose for managing development services. When running commands that require specific runtimes (bun, pipenv, Python, etc.), always use the appropriate Docker Compose service rather than attempting to run them directly on the host.

### Frontend (bun)

Use the `seizu-node` service from `docker-compose.yml` for all bun/node-related commands:

```bash
# Install packages
docker compose run --rm seizu-node bun add <package>
docker compose run --rm seizu-node bun add --dev <package>

# Run scripts
docker compose run --rm seizu-node bun run build
docker compose run --rm seizu-node bun run start
docker compose run --rm seizu-node bun run type-check

# Run tests (all)
docker compose run --rm seizu-node bun test --watchAll=false

# Run a single test file
docker compose run --rm seizu-node bun test src/components/__tests__/DashboardNavbar.test.tsx --watchAll=false
```

### Backend (Python/pipenv)

Use the `seizu` service for Python-related commands:

```bash
# Run all Python unit tests
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit"

# Run a single test file or test
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit/reporting/routes/query_test.py"
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit/reporting/routes/query_test.py::test_query_success"

# Install Python packages
docker compose run --rm seizu pipenv install <package>
```

> **Why `pipenv sync --dev` before pytest?** The Docker image's system Python has packages baked in at image-build time. When new packages are added, the `.venv` (stored in the project directory and therefore persisted on the host) must be synced from `Pipfile.lock` before running tests. `pipenv sync --dev` does this and ensures `pipenv run pytest` uses the virtualenv's pytest (with all current dependencies) rather than the system-level one.

### Makefile shortcuts

```bash
make test           # run all tests
make test_unit      # backend unit tests only
make test_frontend  # frontend type-check only
make lint           # pre-commit on all files
make schema             # regenerate schema/reporting-schema.json and schema/openapi.json
make generate_openapi   # export OpenAPI spec to schema/openapi.json (no running server needed)
make generate_client LANG=go  # generate a client library from schema/openapi.json
make seed_dashboard     # seed reports + scheduled queries via the API (requires `make up` first)
make auth_enable        # start Authentik, enable auth, restart services
make auth_disable       # disable auth, restart services, stop Authentik
make sqlmodel_enable    # switch to SQLModel/PostgreSQL backend, restart with postgres container
make sqlmodel_disable   # switch back to DynamoDB backend
```

### Linting (pre-commit)

Run pre-commit directly on the host machine (not via Docker):

```bash
pre-commit run --all-files        # run all hooks on all files
pre-commit run black --all-files  # run only black
pre-commit run flake8 --all-files # run only flake8
```

`make lint` also runs pre-commit on all files.

### General Rules

- Never install bun, node, pipenv, or Python packages directly on the host machine.
- Always use `docker compose run --rm <service>` for one-off commands.
- Use `docker compose up <service>` for long-running services.
- The `--rm` flag ensures temporary containers are cleaned up after the command completes.
- Run `pre-commit` directly on the host (not via Docker) — the `seizu` container lacks git, which pre-commit requires.

## Adjacent Services Configuration

Setup and configuration for adjacent development services (e.g., Neo4j, Redis, or any other services used alongside the main application) lives in the `.config/` folder. When configuring existing adjacent services or adding new ones for development, always place their configuration files in `.config/` and reference that location in `docker-compose.yml` and related tooling.

`.config/setup.sh` (called by `make up`) copies files from `.config/dev/` into `.compose/` (the runtime directory), and also bootstraps `.env` from `.env.example` on first run. Copies are **one-way and only happen if the destination does not exist**. If you change a source file under `.config/dev/`, manually copy it to `.compose/` for the change to take effect in running containers — or delete the destination file and re-run `make up`. Similarly, if you add a new env var, add it to `.env.example` — developers will need to manually add it to their own `.env`.

**Gunicorn:** The control socket, PID file, and working directory are set to `/run/seizu` (an ephemeral tmpfs-backed path inside the container) to avoid `EINVAL` errors that occur when Unix domain sockets are created on macOS Docker bind-mounted volumes.

## Architecture

### Frontend (`src/`)

React 19 + TypeScript, built with Bun, using Material-UI for components, MUI X Charts for bar/pie charts, and `@xyflow/react` for interactive graph (node-link) visualization.

**Key files and patterns:**
- `src/config.context.ts` — central ConfigContext loaded from `GET /api/v1/config`; holds OIDC and stats config; Cypher query resolution is now per-report (see `Report.queries`)
- `src/authConfig.context.ts` — `AuthConfigContext`; holds `auth_required` fetched from `GET /api/v1/config` in `App.tsx` at startup; consumed by `useCypherQuery` to gate API calls until a token is present
- `src/auth.context.ts` — `AuthContext`; holds the OIDC `user` and `accessToken` managed by `AuthProvider`
- `src/userManager.ts` — creates the `oidc-client-ts` `UserManager` singleton; returns `null` when auth is not required
- `src/components/AuthProvider.tsx` — manages the OIDC flow: registers `userLoaded`/`userUnloaded` event listeners (always, including on the callback path), calls `getUser()` on normal routes, and triggers `signinRedirect()` when unauthenticated
- `src/components/OidcCallback.tsx` — rendered at `/auth/callback`; calls `signinRedirectCallback()` to complete the PKCE exchange then navigates to `/`
- `src/hooks/useCypherQuery.ts` — wraps `POST /api/v1/query` for all data fetching; skips the request when `auth_required` is true and no `accessToken` is available yet
- `src/hooks/useReportsApi.ts` — hooks for fetching reports from DynamoDB: `useReportsList()`, `useReport(id)`, `useDashboardReport()`, `useDashboardReportId()`, `useAllReports()`, `useReportVersionsList(id)`, `useReportVersion(id, version)`; `useReportsMutations()` returns async functions for create/save-version/set-dashboard/delete operations
- `src/components/ReportView.tsx` — shared report rendering component used by both `Dashboard` and `Reports` pages; accepts a `Report` object; resolves panel `cypher` fields against `report.queries` with fallback to literal Cypher string
- `src/components/reports/` — panel components (`CypherCount`, `CypherTable`, `CypherBar`, etc.) are rendered dynamically based on the config panel type
- `src/components/reports/CypherGraph.tsx` — graph visualization panel using `@xyflow/react`; supports Graph/Table/Raw tabs; accepts explicit map format (`RETURN {nodes, links}`), Neo4j path format (`RETURN path`), or any query format (Table/Raw tabs always available); collapsible detail panel shows selected node/relationship properties or a graph summary
- `src/components/reports/GraphDetailPanel.tsx` — detail and summary panels rendered inside `CypherGraph`; `GraphDetailPanel` shows properties of a selected node or relationship; `GraphSummaryPanel` shows node counts by group and relationship counts by type
- `src/pages/QueryConsole.tsx` — ad-hoc query console at `/app/query-console`; query editor with Ctrl+Enter shortcut, graph visualization of results, Graph/Table/Raw tabs
- `src/components/QueryConsoleSchemaPanel.tsx` — collapsible database browser sidebar for the query console; queries `CALL db.labels()`, `CALL db.relationshipTypes()`, and `CALL db.propertyKeys()` to show available schema; clicking an item inserts and runs a discovery query
- All POST requests must include the `X-CSRFToken` header

**User identity display conventions:**
- `src/hooks/useCurrentUser.ts` — `useCurrentUser()` fetches `GET /api/v1/me` and returns the logged-in user; works in both auth-enabled and auth-disabled modes
- `src/hooks/useUser.ts` — `useUser(userId)` fetches `GET /api/v1/users/<userId>` to resolve an arbitrary user_id to a profile
- `src/components/UserAvatar.tsx` — renders a `boring-avatars` pixel SVG avatar seeded by name/email; use `<UserAvatar name={...} />` wherever an avatar is needed
- `src/components/UserDisplay.tsx` — resolves a stored `created_by` user_id (or legacy email string) to `display_name ?? email`; use `<UserDisplay userId={...} />` wherever a user name needs to be rendered from a stored ID
- **Convention:** always show `display_name` when available, falling back to `email`. Never display raw user_ids or `sub` values in the UI.

### Backend (`reporting/`)

APIFlask app (built on Flask 2), Python 3.12, using Gunicorn+Gevent in production.

**Key files and patterns:**
- `reporting/app.py` — APIFlask app factory (`create_app`); serves OpenAPI spec at `/api/openapi.json` and Swagger UI at `/api/docs`
- `reporting/settings.py` — all configuration via env vars (Pydantic validators)
- `reporting/routes/` — APIFlask blueprints (`APIBlueprint`): `config.py`, `me.py`, `query.py`, `reports.py`, `users.py`, `validate.py`, `scheduled_queries.py`; `static.py` remains a regular Flask blueprint (excluded from OpenAPI spec)
- `reporting/authnz/__init__.py` — `bearer_auth = HTTPTokenAuth(scheme="Bearer")` is the auth object used by `@blueprint.auth_required(bearer_auth)` on all protected routes; `_verify_bearer` calls `get_user()` which handles both JWT validation (prod) and dev-mode bypass; routes keep `from reporting import authnz  # noqa: F401` so tests can mock `authnz.get_user` via the route module path
- `reporting/services/` — business logic: `reporting_neo4j.py` (Neo4j driver + distributed locking), `report_store/` (pluggable report storage; see below), `query_validator.py` (multi-stage Cypher validation), `reporting_statsd.py`
- `reporting/schema/reporting_config.py` — Pydantic models that validate the YAML config (`queries`, `dashboard`, `reports`, `scheduled_queries`)
- `reporting/schema/report_config.py` — Pydantic models for DynamoDB report items and API request/response schemas
- `reporting/authnz/` — generic JWT validation using `PyJWKClient`; works with any standard OIDC provider

**Query validation pipeline** (`reporting/services/query_validator.py`):

`validate_query()` returns a `ValidationResult(errors, warnings)` instead of raising. Errors block query execution; warnings are included in the response but the query still runs.

Errors (blocking):
1. Syntax validation (CyVer `SyntaxValidator`)
2. Read-only enforcement (cypher-guard `is_read`) — also catches unsupported/unsafe clauses

Warnings (non-blocking):
3. Schema validation (CyVer `SchemaValidator`) — unknown labels, relationships, paths
4. Property validation (CyVer `PropertiesValidator`) — unknown properties

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config` | Returns OIDC config, stats config, and JSON schema |
| POST | `/api/v1/query` | Executes a validated read-only Cypher query; returns `{results, errors, warnings}` |
| POST | `/api/v1/validate` | Validates a Cypher query without executing it; returns `{errors, warnings}` (always 200 if request is valid) |
| GET | `/api/v1/reports` | Lists all reports (metadata only) |
| POST | `/api/v1/reports` | Creates a new report; returns 201 |
| GET | `/api/v1/reports/dashboard` | Returns the latest version of the dashboard report; 404 if none configured |
| PUT | `/api/v1/reports/<id>/dashboard` | Sets a report as the default dashboard |
| GET | `/api/v1/reports/<id>` | Returns the latest version of a report |
| GET | `/api/v1/reports/<id>/versions` | Lists all versions of a report |
| GET | `/api/v1/reports/<id>/versions/<n>` | Returns a specific version of a report |
| POST | `/api/v1/reports/<id>/versions` | Saves a new version of a report; returns 201 |
| DELETE | `/api/v1/reports/<id>` | Deletes a report and all its versions; clears dashboard pointer if needed |
| GET | `/api/v1/me` | Returns the current authenticated user's profile (`user_id`, `sub`, `iss`, `email`, `display_name`, `created_at`, `last_seen_at`, `archived_at`) |
| GET | `/api/v1/users/<user_id>` | Returns a user profile by internal `user_id`; 404 if not found |
| GET | `/api/v1/scheduled-queries` | Lists all scheduled queries |
| POST | `/api/v1/scheduled-queries` | Creates a new scheduled query; returns 201 |
| GET | `/api/v1/scheduled-queries/<id>` | Returns a scheduled query by ID |
| PUT | `/api/v1/scheduled-queries/<id>` | Updates a scheduled query |
| DELETE | `/api/v1/scheduled-queries/<id>` | Deletes a scheduled query |
| GET | `/api/v1/scheduled-queries/<id>/versions` | Lists all versions of a scheduled query |
| GET | `/api/v1/scheduled-queries/<id>/versions/<n>` | Returns a specific version of a scheduled query |
| GET | `/healthcheck` | Healthcheck |
| GET | `/api/openapi.json` | OpenAPI 3.x specification (machine-readable, use with openapi-generator for CLI/client generation) |
| GET | `/api/docs` | Swagger UI (bearer token auth required for protected routes; CSP may restrict in browser) |

### CLI (`seizu_cli/`)

The Seizu CLI is a Typer application that calls the REST API over HTTP. It lives in `seizu_cli/` and is invoked via `python -m seizu_cli` (or via the Makefile targets).

**Key files:**
- `seizu_cli/main.py` — Typer app entry point; defines global options (`--api-url`, `--token`, `--credentials-file`, `--config-file`) and registers sub-apps and top-level commands; loads `seizu.conf` via `cli_config.load_config()`
- `seizu_cli/config.py` — `SeizuConfig` Pydantic model + `load_config()` that reads `~/.config/seizu/seizu.conf`; `default_seed_file()` returns `~/.config/seizu/reporting-dashboard.yaml`
- `seizu_cli/client.py` — `SeizuClient` wrapper around `requests`; handles Bearer token auth and CSRF token bootstrapping
- `seizu_cli/state.py` — module-level state shared between the callback and commands; `get_client()` creates the client lazily
- `seizu_cli/commands/reports.py` — `reports list/get/create/delete/set-dashboard/versions/version-get`
- `seizu_cli/commands/scheduled_queries.py` — `scheduled-queries list/get/delete/versions/version-get`
- `seizu_cli/commands/seed.py` — `seed` / `export` implementation
- `seizu_cli/auth.py` — token storage (OS-native keyring or `--credentials-file` fallback) and Device Authorization Grant flow
- `seizu_cli/commands/auth.py` — `auth login/logout/whoami` (also exposed as top-level `login/logout/whoami`)

**CLI config file (`~/.config/seizu/seizu.conf`):**

A YAML file that sets persistent defaults for the CLI. All values can be overridden by CLI flags or environment variables.

```yaml
api_url: https://seizu.example.com   # default --api-url
seed_file: ~/dashboards/reporting.yaml  # default seed/export config path
```

Resolution order for each setting: `CLI flag` → `env var` → `seizu.conf` → built-in default.

Use `--config-file PATH` (or `SEIZU_CONFIG_FILE`) to point at a non-default config file.

**Authentication (Device Authorization Grant, RFC 8628):**

The CLI uses the Device Authorization Grant so users don't need to copy/paste tokens manually. The flow:
1. `seizu login` fetches the OIDC discovery doc via `GET /api/v1/config` + `/.well-known/openid-configuration`
2. Posts to the device authorization endpoint; displays a short URL + code to the user
3. User opens the URL in a browser, logs in via Authentik, approves the request
4. CLI polls the token endpoint until it receives an access token
5. Token is saved to the OS-native keyring (or to a JSON file when `--credentials-file` is used), keyed by API URL
6. All subsequent commands auto-load the stored token — no `--token` flag needed

```bash
seizu login                          # authenticate (Device Authorization Grant)
seizu whoami                         # verify who you are
seizu logout                         # clear stored credentials
seizu --api-url https://... login    # authenticate against a different deployment
```

**Usage (inside the seizu container):**
```bash
# Show help
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --help

# Authenticate (runs Device Authorization Grant)
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 login

# List reports (auto-loads stored token)
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 reports list

# Seed from YAML
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed --force
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed --dry-run

# Export to YAML
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 export
```

Or via the Makefile (preferred):
```bash
make seed_dashboard
make seed_dashboard ARGS="--force"
make seed_dashboard ARGS="export"
```

**CSRF handling:** The client calls `GET /api/v1/config` first to bootstrap the CSRF token cookie, then includes `X-CSRFToken` in all mutating requests. No backend changes are needed.

**Generating clients in other languages:** The OpenAPI spec is the canonical interface definition. Generate clients with:
```bash
make generate_openapi                    # exports schema/openapi.json
make generate_client LANG=go             # generates a Go client in generated/go-client/
make generate_client LANG=typescript-fetch  # TypeScript
make generate_client LANG=java           # Java
```
Uses `openapitools/openapi-generator-cli` via Docker. See https://openapi-generator.tech/docs/generators for all supported languages.

### Configuration System

Dashboard and report configurations are stored in DynamoDB. The YAML config file (mounted as `/reporting-dashboard.yaml` in the container; example at `.config/dev/seizu/reporting-dashboard.yaml`) is used for `queries` and `scheduled_queries`, and as a seed source for populating DynamoDB.

**YAML top-level sections:**
- `queries` — named Cypher query strings used only by `scheduled_queries` cypher references; not served to the frontend
- `dashboard` — a string key pointing to the report in `reports` that should be used as the default dashboard (e.g. `dashboard: dashboard`)
- `reports` — report definitions used to seed DynamoDB via `make seed_dashboard`; each report has its own `queries` dict for named Cypher strings used by its panels; not served directly to the frontend
- `scheduled_queries` — recurring query definitions with action plugins (SQS, Slack, log); **list** format (not a dict); used only to seed scheduled queries into the database via `make seed_dashboard`

**Report storage abstraction** (`reporting/services/report_store/`): a pluggable storage layer for report configurations.
- `base.py` — `ReportStore` ABC defining the full public interface (`list_reports`, `get_report_latest`, `create_report`, `set_dashboard_report`, `initialize`, etc.)
- `dynamodb.py` — `DynamoDBReportStore(ReportStore)` — DynamoDB single-table design with composite PK/SK; Snowflake IDs
- `sql.py` — `SQLModelReportStore(ReportStore)` — SQLModel/SQLAlchemy implementation; works with any DB supported by SQLAlchemy (PostgreSQL, SQLite, etc.); configured via `SQL_DATABASE_URL`
- `__init__.py` — `get_store()` factory (reads `REPORT_STORE_BACKEND` setting; default: `dynamodb`) and module-level convenience delegators

Use `from reporting.services import report_store` and call e.g. `report_store.list_reports()` — the configured backend is selected transparently.

**Switching backends in development:**
```bash
make sqlmodel_enable   # sets REPORT_STORE_BACKEND=sqlmodel; restarts with postgres container
make sqlmodel_disable  # reverts to REPORT_STORE_BACKEND=dynamodb
make dynamodb_enable   # alias: sqlmodel_disable (dynamodb is the default)
make down && make up   # apply after changing backends
```
`make up` automatically includes `--profile sqlmodel` when `REPORT_STORE_BACKEND=sqlmodel` is set in `.env` (same pattern as `--profile auth`).

**DynamoDB storage** (`reporting/services/report_store/dynamodb.py`): reports, scheduled queries, and their version histories are stored in a single DynamoDB table using a composite key design:
- Each report has a `#METADATA` item, a `#LATEST` pointer, and `VERSION#<n>` items
- Each scheduled query has a `#METADATA` item under `SQ#<id>`, a list index item under `SCHEDULED_QUERY_LIST`, and `VERSION#<n>` items
- A `#DASHBOARD/#POINTER` item records which report is the default dashboard
- Machine IDs for the Snowflake ID generator are set via `SNOWFLAKE_MACHINE_ID`

**SQLModel storage** (`reporting/services/report_store/sql.py`): five tables — `reports`, `report_versions`, `dashboard_pointer`, `scheduled_queries`, `scheduled_query_versions`. Uses SQLAlchemy JSON column for config storage; `initialize()` runs `SQLModel.metadata.create_all()`. Configured via `SQL_DATABASE_URL`.

**Seeding reports and scheduled queries** from the YAML config (requires the API to be running via `make up`):
```bash
make seed_dashboard                                  # seed reports + scheduled queries from .config/dev/seizu/reporting-dashboard.yaml
make seed_dashboard ARGS="--force"                   # save a new version even if config is unchanged
make seed_dashboard ARGS="--dry-run"                 # preview without writing
make up && make seed_dashboard                       # typical first-run workflow
```

**Exporting** reports from the store back into YAML:
```bash
make seed_dashboard ARGS="export"                    # export store reports back into the YAML file
make seed_dashboard ARGS="export --dry-run"          # preview the exported YAML without writing
```

`make seed_dashboard` calls the Typer CLI (`seizu_cli`) which talks to the running API at `http://seizu:8080`. The CLI seeds both reports and scheduled queries in a single run, and sets the dashboard pointer if `dashboard:` is configured in the YAML.

**Seeding scheduled queries:** Scheduled queries are stored in the database with Snowflake IDs and full version history. The `cypher` field in the YAML is resolved against the top-level `queries` dict (falling back to the literal string if no key matches). Matching is by name; existing queries are skipped unless their content has changed or `--force` is passed.

When seeding, existing reports whose latest stored version matches the YAML are skipped; if the config has changed, a new version is saved automatically.

When exporting, existing YAML keys are reused when the report name matches; otherwise a slug derived from the report name is used. The `queries` and `scheduled_queries` sections of the YAML are preserved unchanged.

Each `Report` in DynamoDB has a `queries` dict (named Cypher strings). Panel `cypher` fields are resolved against this dict at render time, falling back to the literal value as a direct Cypher string when no key matches. The `Report` TypeScript interface in `src/config.context.ts` must stay in sync with the Pydantic `Report` model in `reporting/schema/reporting_config.py`.

### Cartography Data Sync

Cartography runs via the `nostart` profile (not started on `docker compose up`). Each Makefile target uses `--selected-modules` to run only the relevant module:

```bash
make sync_cve         # CVE data only
make sync_aws         # AWS infrastructure
make sync_github      # GitHub
make sync_crowdstrike # CrowdStrike
make sync_k8s         # Kubernetes
```

The cartography image entrypoint is already `cartography` — do not prefix the command with `cartography` when calling `docker compose run`.

### Scheduled Query Action Plugins

Located in `reporting/scheduled_query_modules/`. Each module implements the `ModuleInterface` defined in `__init__.py`. When adding a new action type, add a new module here and add it to `_BUILTIN_MODULES` or configure it via `SCHEDULED_QUERY_MODULES`.

Key methods every module must implement:
- `action_name()` — the string used in `action_type` when configuring an action
- `setup()` — called once at worker startup for initialisation
- `handle_results(scheduled_query_id, action, results)` — processes query results
- `action_config_schema()` — returns `List[ActionConfigFieldDef]` describing the config fields; the frontend renders typed input forms from this schema instead of a raw JSON textarea. The `ActionConfigFieldDef` type is declared in `reporting/schema/report_config.py` and supports field types: `string`, `text`, `number`, `boolean`, `string_list`, `select`.

Action schemas are served to the frontend via `GET /api/v1/config` as `scheduled_query_action_schemas`.

### Docker Services

| Service | Role |
|---------|------|
| `seizu` | APIFlask backend + static frontend |
| `seizu-node` | Bun dev server (frontend only) |
| `seizu-dashboard-stats` | Stats aggregation worker |
| `seizu-scheduled-queries` | Scheduled query worker |
| `neo4j` | Graph database |
| `dynamodb` | DynamoDB Local (report config storage, default backend) |
| `postgres` | PostgreSQL (report config storage, `sqlmodel` profile/backend) |
| `telegraf` | Metrics aggregation |
| `sqs` | ElasticMQ (local SQS emulation) |
| `authentik-server` | Authentik OIDC provider (profile: `auth`) |
| `authentik-worker` | Authentik background worker (profile: `auth`) |
| `authentik-postgresql` | Authentik database (profile: `auth`) |
| `authentik-redis` | Authentik cache (profile: `auth`) |
| `cartography` | Graph data sync tool (profile: `nostart`) |

Networks are segmented: `proxy`, `database`, `stats`, `auth`, `credentials`.

**Dev access URLs:**
- Frontend (Bun dev server): `http://localhost:3000`
- Backend (Flask/Gunicorn): `http://localhost:8080`

**Named volumes:** Data is stored in named Docker volumes rather than bind mounts. To reset:
```bash
docker compose down
docker volume rm seizu_neo4j_data     # reset Neo4j graph data
docker volume rm seizu_dynamodb_data  # reset DynamoDB report configs
docker compose up
```
After resetting DynamoDB, re-seed reports with `make seed_dashboard`.

### Authentication

The backend uses `PyJWKClient` (PyJWT) to validate JWTs against any standard OIDC JWKS endpoint. Key settings:

| Setting | Env var | Default | Description |
|---------|---------|---------|-------------|
| `JWKS_URL` | `JWKS_URL` | `""` | Standard JWKS JSON endpoint |
| `JWT_HEADER_NAME` | `JWT_HEADER_NAME` | `Authorization` | Request header carrying the token |
| `JWT_EMAIL_CLAIM` | `JWT_EMAIL_CLAIM` | `email` | JWT claim for the user's email |
| `JWT_ISSUER` | `JWT_ISSUER` | `""` | Optional issuer to validate |
| `JWT_AUDIENCE` | `JWT_AUDIENCE` | `""` | Audience to validate; must match the OIDC client ID (e.g. `seizu`) when using Authentik, because Authentik always sets `aud` in the access token |
| `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `true` | Set `false` in dev to bypass auth |
| `TALISMAN_FORCE_HTTPS` | `TALISMAN_FORCE_HTTPS` | `true` | Set `false` when not serving HTTPS (dev or behind SSL-terminating LB) |
| `OIDC_AUTHORITY` | `OIDC_AUTHORITY` | `""` | OIDC provider base URL; served to the frontend via `/api/v1/config` |
| `OIDC_CLIENT_ID` | `OIDC_CLIENT_ID` | `""` | OIDC client ID; served to the frontend via `/api/v1/config` |
| `OIDC_REDIRECT_URI` | `OIDC_REDIRECT_URI` | `""` | OIDC callback URL (browser-reachable); served to the frontend via `/api/v1/config` |
| `OIDC_SCOPE` | `OIDC_SCOPE` | `"openid email"` | OIDC scope; served to the frontend via `/api/v1/config` |

The frontend performs an OIDC PKCE flow when the backend returns `auth_required: true` and an `oidc` config object from `GET /api/v1/config`. The `UserManager` is created dynamically in `App.tsx` from the fetched config and shared via `AuthConfigContext` — there are no build-time `REACT_APP_OIDC_*` env vars. Auth state lives in `src/auth.context.ts`; the `UserManager` factory is in `src/userManager.ts`.

**Testing authentication locally with Authentik:**

`make auth_enable` and `make auth_disable` only update `.env`. `make up` and `make down` automatically include `--profile auth` when `DEVELOPMENT_ONLY_REQUIRE_AUTH=true` is set in `.env`, so Authentik services start and stop with the rest of the stack.

**Step 1 — Enable auth and restart:**
```bash
make auth_enable
make down && make up
```

`make auth_enable` sets `DEVELOPMENT_ONLY_REQUIRE_AUTH=true` in `.env`. `make up` then detects this and starts the full stack including the Authentik profile. On first run allow ~2 minutes for Authentik to become healthy; subsequent runs take ~30 seconds.

Setup is fully automated — no browser wizard needed. The following happen automatically:
1. `AUTHENTIK_BOOTSTRAP_PASSWORD` creates the `akadmin` admin account and skips the setup wizard
2. Built-in system blueprints run and create default flows
3. `.config/dev/authentik/blueprints/seizu.yaml` (mounted at `/blueprints/custom`) creates the seizu OIDC provider and application
4. The custom blueprint sets passwords for `akadmin` and `developer` and creates the `developer` user

**Step 2 — Log in:**

Visit `http://localhost:3000`. You will be redirected to Authentik at `http://localhost:9000`. Log in as `developer` / `devpassword`. Authentik redirects back to `http://localhost:3000/auth/callback`, completes the PKCE exchange, and the app loads with a valid session.

**How the auth flows work:**

*Browser (Authorization Code + PKCE):*
- The frontend performs an OIDC Authorization Code + PKCE flow against `http://localhost:9000/application/o/seizu`
- The access token is sent as `Authorization: Bearer <token>` on every API request
- The backend validates the JWT against the JWKS endpoint at `http://authentik-server:9000/application/o/seizu/jwks/` (internal Docker hostname)
- The user's email is read from the `email` JWT claim

*CLI (Device Authorization Grant, RFC 8628):*
- `seizu login` hits `POST http://localhost:9000/application/o/seizu/device/` to obtain a `device_code` and `user_code`
- The user visits the verification URL in a browser (pre-filled with the code) and logs in
- The CLI polls `POST http://localhost:9000/application/o/seizu/token/` until the user approves
- The access token is stored in `~/.config/seizu/credentials.json` and auto-loaded on subsequent commands
- The Authentik blueprint enables this via `device_code_flow: !Find [slug, default-provider-device-code]`

**Reverting to no-auth dev mode:**
```bash
make auth_disable
make down && make up
```

`make auth_disable` sets `DEVELOPMENT_ONLY_REQUIRE_AUTH=false` in `.env`. `make down && make up` then stops the full stack (including Authentik) and restarts without the auth profile.

**Authentik admin UI:** `http://localhost:9000` — log in as `akadmin` / `devpassword` to inspect the OIDC provider, application, and users.

The OIDC redirect URIs registered in the blueprint are `http://localhost:3000/auth/callback` (dev server) and `http://localhost:8080/auth/callback` (backend direct). If you change ports, update `.config/dev/authentik/blueprints/seizu.yaml` and the `REACT_APP_OIDC_REDIRECT_URI` env var in `docker-compose.yml`.

Default dev credentials:
- Admin UI (`http://localhost:9000`): `akadmin` / `devpassword`
- Login as developer: `developer` / `devpassword`

### Testing Patterns

**Backend:** pytest + pytest-mock. Tests live in `tests/unit/reporting/`, mirroring `reporting/` structure. Use the Flask `test_client()` pattern — see `tests/unit/reporting/routes/query_test.py` for a reference example.

**Frontend:** React Testing Library + Jest (via Bun). Test files are co-located in `__tests__/` subdirectories next to the components they test.

### Typing

Python code targets strict mypy with `check_untyped_defs = true` and `disallow_untyped_defs = true` (see `setup.cfg`). When writing or modifying Python code:

- All functions must have complete type annotations.
- Prefer fixing type errors over suppressing them. Do not add `# type: ignore` or `ignore_errors = true` without a genuine reason (e.g., broken third-party stubs with no alternative).
- When you encounter existing `# type: ignore` comments in code you are changing, fix the underlying type issue and remove the comment rather than propagating it.
- Use `typing.cast` only when the type system cannot express a known-safe invariant (e.g., casting a `str` to a `Literal` type constrained by settings validation).

## Frontend Style Guide

### List View Pattern

All list views (reports, scheduled queries, users, etc.) follow a consistent structure. When building a new list view or modifying an existing one, adhere to these conventions.

#### Layout

- Top bar: page title (`<Typography variant="h1">`) on the left, primary action button (`<Button variant="contained">`) on the right.
- Loading state: `<CircularProgress />` rendered inline (no full-page spinner).
- Error state: `<Error />` icon + `<Typography>` message side-by-side in a flex row.
- Table: `<TableContainer component={Paper} variant="outlined">` wrapping a `<Table>`.

#### Table structure

- Every list view uses a `<Table>` with explicit `<TableHead>` and `<TableBody>`.
- Empty state is a `<TableRow>` with a single `<TableCell colSpan={N}>` containing a muted `<Typography color="text.secondary">` message. Do not render a separate card or placeholder outside the table.
- Row hover: `<TableRow hover>` on every data row.
- Secondary/metadata columns use `sx={{ color: 'text.secondary' }}` on the `<TableCell>`.
- Dates are formatted with `new Date(value).toLocaleString()`.
- User references are rendered with `<UserDisplay userId={...} />` — never raw IDs or emails.

#### Column naming conventions

| Content | Header label |
|---------|-------------|
| Timestamp of last write | **Latest Update** |
| User who last wrote | **Updated By** |
| User who created a record | **Created By** |
| Version number | **Version** |
| Enabled/disabled state | **Status** |

#### Per-row actions

Use a `RowMenu` component (three-dot overflow menu) rather than inline icon buttons:

- Trigger: `<IconButton size="small"><MoreVertIcon /></IconButton>` wrapped in a `<Tooltip title="More actions">`.
- Menu anchor: `anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}`, `transformOrigin={{ vertical: 'top', horizontal: 'right' }}`.
- `slotProps={{ paper: { sx: { minWidth: 180 } } }}`.
- Destructive actions (Delete) go at the bottom, separated by a `<Divider />`, and use `sx={{ color: 'error.main' }}` with a `<DeleteIcon color="error" />`.
- Disabled items (e.g. "already current version") should be wrapped in a `<Tooltip>` explaining why, with a `<span>` wrapper around the `<MenuItem>` so the tooltip renders correctly when the item is disabled.

#### Clickable names

- Make the primary identifier (name, version number, etc.) clickable to show details.
- For list rows: use `sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}` on a `<Typography>`, not a `<Link>`, when the click opens a dialog rather than navigating.
- For history rows where a version can be viewed: same pattern — click opens a read-only detail dialog.

#### Detail dialogs (read-only view)

- Use a shared dialog component (e.g. `ScheduledQueryDetailDialog`) exported from `src/components/`.
- Title bar: name + optional secondary label (e.g. version), close `<IconButton>` on the right.
- A `<Divider />` separates the title from the content.
- Sections use a consistent `Section` sub-component: subtitle label in `color="text.secondary"`, content below.
- Code/Cypher blocks use `<Box component="pre">` with `bgcolor: 'action.hover'`, `fontFamily: 'monospace'`, `whiteSpace: 'pre-wrap'`, `wordBreak: 'break-word'`.

#### Dialogs (create / delete)

- Create dialogs: `maxWidth="sm" fullWidth`.
- Delete confirmation dialogs: `maxWidth="xs" fullWidth`; use `<DialogContentText>` with the record name in `<strong>`.
- Always show a `<CircularProgress size={20} />` inside the submit button while the async operation is in flight; keep the button disabled.
- Error messages go in an `<Alert severity="error">` at the top of `<DialogContent>`, not in a separate snackbar.

#### Version history pages

- Route pattern: `<entity>/:id/history` (e.g. `reports/:id/history`, `scheduled-queries/:id/history`).
- Back button at top using `<Button startIcon={<ArrowBackIcon />}>` navigating to the parent list.
- Page title: `<HistoryIcon color="action" />` + `<Typography variant="h1">Version history – {name}</Typography>`.
- Table columns: **Version**, **Saved**, **Created By**, **Comment**, actions menu.
- Current version row: version label in bold with a `"current"` caption in `color="primary"`.
- Restore action: disabled on the current version with a tooltip explaining why; restoring calls the update API with `comment: \`Restored from version ${version}\``.
- Helmet title: `History – {name} | Seizu`.

## Keeping Supporting Files Up to Date

When making changes to the codebase, always review and update the following files as needed to reflect those changes:

- **`Makefile`** — add or update targets for any new build, test, or tooling steps
- **`.github/workflows/`** — update CI jobs to include new test, lint, or type-check steps
- **`Dockerfile` and `docker-compose.yml`** — update if new files, build steps, services, or environment variables are introduced
- **`.pre-commit-config.yaml`** — update hooks or dependencies if linting/formatting tooling changes
- **`.eslintrc`** (or other lint/format configs) — update if new file types, parsers, or plugins are needed
- **`Pipfile`** — add or remove Python dependencies when adding or removing backend features; run `docker compose run --rm seizu pipenv install <pkg>` to add, edit `Pipfile` directly then run `docker compose run --rm seizu pipenv lock` to update `Pipfile.lock`, then run `make lock` to regenerate `requirements.txt`
- **`docs/`** — update documentation when adding, changing, or removing features, panel types, API endpoints, configuration options, or any user-facing behavior. Always grep docs/ for references to anything you are removing to ensure nothing is left stale.
- **`schema/reporting-schema.json`** — regenerate via `make schema` (or manually update) when the Pydantic config schema changes
- **`.env.example`** — add new env vars; remove or relocate vars when features are removed
- **`AGENTS.MD`** — update these guidelines if new conventions or tooling patterns are introduced (loaded via `.claude/CLAUDE.md`)
