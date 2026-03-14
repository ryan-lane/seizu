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
docker compose run --rm seizu pipenv run pytest tests/unit

# Run a single test file or test
docker compose run --rm seizu pipenv run pytest tests/unit/reporting/routes/query_test.py
docker compose run --rm seizu pipenv run pytest tests/unit/reporting/routes/query_test.py::test_query_success

# Install Python packages
docker compose run --rm seizu pipenv install <package>
```

### Makefile shortcuts

```bash
make test           # run all tests
make test_unit      # backend unit tests only
make test_frontend  # frontend type-check only
make lint           # pre-commit on all files
```

### General Rules

- Never install bun, node, pipenv, or Python packages directly on the host machine.
- Always use `docker compose run --rm <service>` for one-off commands.
- Use `docker compose up <service>` for long-running services.
- The `--rm` flag ensures temporary containers are cleaned up after the command completes.

## Adjacent Services Configuration

Setup and configuration for adjacent development services (e.g., Neo4j, Redis, or any other services used alongside the main application) lives in the `.config/` folder. When configuring existing adjacent services or adding new ones for development, always place their configuration files in `.config/` and reference that location in `docker-compose.yml` and related tooling.

## Architecture

### Frontend (`src/`)

React 19 + TypeScript, built with Bun, using Material-UI for components and Nivo for charts.

**Key files and patterns:**
- `src/config.context.ts` — central ConfigContext loaded from `GET /api/v1/config`; holds all dashboard/report config and is the single source of truth for app state
- `src/hooks/useCypherQuery.ts` — wraps `POST /api/v1/query` for all data fetching
- `src/components/reports/` — panel components (`CypherCount`, `CypherTable`, `CypherBar`, etc.) are rendered dynamically based on the config panel type
- All POST requests must include the `X-CSRFToken` header

### Backend (`reporting/`)

Flask 2 app, Python 3.12, using Gunicorn+Gevent in production.

**Key files and patterns:**
- `reporting/app.py` — Flask app factory (`create_app`)
- `reporting/settings.py` — all configuration via env vars (Pydantic validators)
- `reporting/routes/` — Flask blueprints: `config.py`, `query.py`, `pagerduty.py`, `static.py`
- `reporting/services/` — business logic: `reporting_neo4j.py` (Neo4j driver + distributed locking), `query_validator.py` (multi-stage Cypher validation), `reporting_statsd.py`
- `reporting/schema/reporting_config.py` — Pydantic models that validate the YAML dashboard config
- `reporting/authnz/` — generic JWT validation using `PyJWKClient`; works with any standard OIDC provider

**Query validation pipeline** (`reporting/services/query_validator.py`):
1. Syntax validation (CyVer)
2. Read-only enforcement (cypher-guard)
3. Schema validation (CyVer)
4. Property validation (CyVer)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config` | Returns full dashboard/report config |
| POST | `/api/v1/query` | Executes a validated read-only Cypher query |
| GET | `/api/v1/pagerduty/*` | PagerDuty proxy endpoints |
| GET | `/health` | Healthcheck |

### Configuration System

The entire dashboard is configuration-driven via a YAML file (mounted as `/reporting-dashboard.yaml` in the container; example at `.config/dev/seizu/reporting-dashboard.yaml`).

**YAML top-level sections:**
- `queries` — named Cypher query strings
- `dashboard` — rows/panels layout (panel types: `count`, `progress`, `pie`, `bar`, `table`, `vertical_table`, `markdown`, `oncall`)
- `reports` — report pages with typed inputs (`autocomplete`, `text`) and rows/panels
- `scheduled_queries` — recurring query definitions with action plugins (SQS, Slack, log)

The TypeScript interfaces in `src/config.context.ts` mirror the Pydantic models in `reporting/schema/reporting_config.py` — keep them in sync when changing the config schema.

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
| `telegraf` | Metrics aggregation |
| `sqs` | ElasticMQ (local SQS emulation) |
| `authentik-server` | Authentik OIDC provider (profile: `auth`) |
| `authentik-worker` | Authentik background worker (profile: `auth`) |
| `authentik-postgresql` | Authentik database (profile: `auth`) |
| `authentik-redis` | Authentik cache (profile: `auth`) |

Networks are segmented: `proxy`, `database`, `stats`, `auth`, `credentials`.

### Authentication

The backend uses `PyJWKClient` (PyJWT) to validate JWTs against any standard OIDC JWKS endpoint. Key settings:

| Setting | Env var | Default | Description |
|---------|---------|---------|-------------|
| `JWKS_URL` | `JWKS_URL` | `""` | Standard JWKS JSON endpoint |
| `JWT_HEADER_NAME` | `JWT_HEADER_NAME` | `Authorization` | Request header carrying the token |
| `JWT_EMAIL_CLAIM` | `JWT_EMAIL_CLAIM` | `email` | JWT claim for the user's email |
| `JWT_ISSUER` | `JWT_ISSUER` | `""` | Optional issuer to validate |
| `JWT_AUDIENCE` | `JWT_AUDIENCE` | `""` | Optional audience to validate |
| `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `true` | Set `false` in dev to bypass auth |

The frontend performs an OIDC PKCE flow when `REACT_APP_OIDC_ENABLED=true`. Required frontend env vars: `REACT_APP_OIDC_AUTHORITY`, `REACT_APP_OIDC_CLIENT_ID`, `REACT_APP_OIDC_REDIRECT_URI`. Auth state lives in `src/auth.context.ts`; the `UserManager` singleton is in `src/userManager.ts`.

**Enabling Authentik in development:**

```bash
# Start Authentik alongside other services — setup is fully automated
docker compose --profile auth up

# Flip the two flags in docker-compose.yml (or via shell env):
#   seizu:      DEVELOPMENT_ONLY_REQUIRE_AUTH=true
#   seizu-node: REACT_APP_OIDC_ENABLED=true
```

No browser wizard is needed. On startup:
1. `AUTHENTIK_BOOTSTRAP_PASSWORD` creates the `akadmin` admin account and skips the setup flow
2. The built-in system blueprints (inside the image) run first and create default flows
3. The custom blueprint at `.config/dev/authentik/blueprints/seizu.yaml` (mounted at `/blueprints/custom`) creates the seizu OIDC provider and application
4. `authentik-init` (a one-shot service) creates a `developer` user via `ak shell`

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
- **`docs/`** — update documentation if behavior, configuration, or interfaces change
- **`AGENTS.MD`** — update these guidelines if new conventions or tooling patterns are introduced (loaded via `.claude/CLAUDE.md`)
