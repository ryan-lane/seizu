# Agent Guidelines

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Seizu?

Seizu (星図) is a configuration-driven reporting platform for Neo4j graph data. It has three main runtimes:

- **Flask web app** (`reporting/`) — serves the React frontend and a REST API
- **Scheduled query worker** (`reporting/scheduled_queries.py`) — runs Cypher queries on a schedule with pluggable action plugins (SQS, Slack, log)
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
make schema           # regenerate schema/reporting-schema.json from Pydantic models
make seed_reports     # seed report store from .config/dev/seizu/reporting-dashboard.yaml
make auth_enable      # start Authentik, enable auth, restart services
make auth_disable     # disable auth, restart services, stop Authentik
make sqlmodel_enable  # switch to SQLModel/PostgreSQL backend, restart with postgres container
make sqlmodel_disable # switch back to DynamoDB backend
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

React 19 + TypeScript, built with Bun, using Material-UI for components and Nivo for charts.

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
- All POST requests must include the `X-CSRFToken` header

### Backend (`reporting/`)

Flask 2 app, Python 3.12, using Gunicorn+Gevent in production.

**Key files and patterns:**
- `reporting/app.py` — Flask app factory (`create_app`)
- `reporting/settings.py` — all configuration via env vars (Pydantic validators)
- `reporting/routes/` — Flask blueprints: `config.py`, `query.py`, `reports.py`, `static.py`
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
| GET | `/healthcheck` | Healthcheck |

### Configuration System

Dashboard and report configurations are stored in DynamoDB. The YAML config file (mounted as `/reporting-dashboard.yaml` in the container; example at `.config/dev/seizu/reporting-dashboard.yaml`) is used for `queries` and `scheduled_queries`, and as a seed source for populating DynamoDB.

**YAML top-level sections:**
- `queries` — named Cypher query strings used only by `scheduled_queries` cypher references; not served to the frontend
- `dashboard` — a string key pointing to the report in `reports` that should be used as the default dashboard (e.g. `dashboard: dashboard`)
- `reports` — report definitions used to seed DynamoDB via `make seed_reports`; each report has its own `queries` dict for named Cypher strings used by its panels; not served directly to the frontend
- `scheduled_queries` — recurring query definitions with action plugins (SQS, Slack, log)

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

**DynamoDB storage** (`reporting/services/report_store/dynamodb.py`): reports and their version history are stored in a single DynamoDB table using a composite key design:
- Each report has a `#METADATA` item, a `#LATEST` pointer, and `VERSION#<n>` items
- A `#DASHBOARD/#POINTER` item records which report is the default dashboard
- Machine IDs for the Snowflake ID generator are set via `SNOWFLAKE_MACHINE_ID`

**SQLModel storage** (`reporting/services/report_store/sql.py`): three tables — `reports`, `report_versions`, `dashboard_pointer`. Uses SQLAlchemy JSON column for config storage; `initialize()` runs `SQLModel.metadata.create_all()`. Configured via `SQL_DATABASE_URL`.

**Seeding reports** from the YAML config:
```bash
make seed_reports                    # seed from .config/dev/seizu/reporting-dashboard.yaml
make seed_reports ARGS="--force"     # re-seed, overwriting existing reports by name
make seed_reports ARGS="--dry-run"   # preview without writing
```
The seed script also sets the dashboard pointer if `dashboard:` is configured in the YAML.

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

Located in `reporting/scheduled_query_modules/`. Each module implements a standard interface. When adding a new action type, add a new module here and register it in the scheduler.

### Docker Services

| Service | Role |
|---------|------|
| `seizu` | Flask backend + static frontend |
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
After resetting DynamoDB, re-seed reports with `make seed_reports`.

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

**How the auth flow works:**
- The frontend performs an OIDC Authorization Code + PKCE flow against `http://localhost:9000/application/o/seizu`
- The access token is sent as `Authorization: Bearer <token>` on every API request
- The backend validates the JWT against the JWKS endpoint at `http://authentik-server:9000/application/o/seizu/jwks/` (internal Docker hostname)
- The user's email is read from the `email` JWT claim

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
