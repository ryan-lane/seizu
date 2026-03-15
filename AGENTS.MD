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
make auth_enable    # start Authentik, enable auth, restart services
make auth_disable   # disable auth, restart services, stop Authentik
```

### General Rules

- Never install bun, node, pipenv, or Python packages directly on the host machine.
- Always use `docker compose run --rm <service>` for one-off commands.
- Use `docker compose up <service>` for long-running services.
- The `--rm` flag ensures temporary containers are cleaned up after the command completes.

## Adjacent Services Configuration

Setup and configuration for adjacent development services (e.g., Neo4j, Redis, or any other services used alongside the main application) lives in the `.config/` folder. When configuring existing adjacent services or adding new ones for development, always place their configuration files in `.config/` and reference that location in `docker-compose.yml` and related tooling.

`.config/setup.sh` (called by `make up`) copies files from `.config/dev/` into `.compose/` (the runtime directory), and also bootstraps `.env` from `.env.example` on first run. Copies are **one-way and only happen if the destination does not exist**. If you change a source file under `.config/dev/`, manually copy it to `.compose/` for the change to take effect in running containers — or delete the destination file and re-run `make up`. Similarly, if you add a new env var, add it to `.env.example` — developers will need to manually add it to their own `.env`.

**Gunicorn:** The control socket, PID file, and working directory are set to `/run/seizu` (an ephemeral tmpfs-backed path inside the container) to avoid `EINVAL` errors that occur when Unix domain sockets are created on macOS Docker bind-mounted volumes.

## Architecture

### Frontend (`src/`)

React 19 + TypeScript, built with Bun, using Material-UI for components and Nivo for charts.

**Key files and patterns:**
- `src/config.context.ts` — central ConfigContext loaded from `GET /api/v1/config`; holds all dashboard/report config and is the single source of truth for app state
- `src/authConfig.context.ts` — `AuthConfigContext`; holds `auth_required` fetched from `GET /api/v1/config` in `App.tsx` at startup; consumed by `useCypherQuery` to gate API calls until a token is present
- `src/auth.context.ts` — `AuthContext`; holds the OIDC `user` and `accessToken` managed by `AuthProvider`
- `src/userManager.ts` — creates the `oidc-client-ts` `UserManager` singleton; returns `null` when `REACT_APP_OIDC_ENABLED` is not `true`
- `src/components/AuthProvider.tsx` — manages the OIDC flow: registers `userLoaded`/`userUnloaded` event listeners (always, including on the callback path), calls `getUser()` on normal routes, and triggers `signinRedirect()` when unauthenticated
- `src/components/OidcCallback.tsx` — rendered at `/auth/callback`; calls `signinRedirectCallback()` to complete the PKCE exchange then navigates to `/`
- `src/hooks/useCypherQuery.ts` — wraps `POST /api/v1/query` for all data fetching; skips the request when `auth_required` is true and no `accessToken` is available yet
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
| GET | `/healthcheck` | Healthcheck |

### Configuration System

The entire dashboard is configuration-driven via a YAML file (mounted as `/reporting-dashboard.yaml` in the container; example at `.config/dev/seizu/reporting-dashboard.yaml`).

**YAML top-level sections:**
- `queries` — named Cypher query strings
- `dashboard` — rows/panels layout (panel types: `count`, `progress`, `pie`, `bar`, `table`, `vertical_table`, `markdown`, `oncall`)
- `reports` — report pages with typed inputs (`autocomplete`, `text`) and rows/panels
- `scheduled_queries` — recurring query definitions with action plugins (SQS, Slack, log)

The TypeScript interfaces in `src/config.context.ts` mirror the Pydantic models in `reporting/schema/reporting_config.py` — keep them in sync when changing the config schema.

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

**Neo4j data volume:** Neo4j data is stored in a named Docker volume (`neo4j_data`) rather than a bind mount. To reset the database for a fresh start:
```bash
docker compose down
docker volume rm seizu_neo4j_data
docker compose up
```

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

The frontend performs an OIDC PKCE flow when `REACT_APP_OIDC_ENABLED=true`. Required frontend env vars: `REACT_APP_OIDC_AUTHORITY`, `REACT_APP_OIDC_CLIENT_ID`, `REACT_APP_OIDC_REDIRECT_URI`. Auth state lives in `src/auth.context.ts`; the `UserManager` singleton is in `src/userManager.ts`.

**Testing authentication locally with Authentik:**

**Step 1 — Enable auth:**
```bash
make auth_enable
```

This starts the Authentik services (waiting for them to be healthy), flips `DEVELOPMENT_ONLY_REQUIRE_AUTH` and `REACT_APP_OIDC_ENABLED` in `.env`, and restarts `seizu` and `seizu-node`. On first run allow ~2 minutes for Authentik to become healthy; subsequent runs take ~30 seconds.

Setup is fully automated — no browser wizard needed. The following happen automatically:
1. `AUTHENTIK_BOOTSTRAP_PASSWORD` creates the `akadmin` admin account and skips the setup wizard
2. Built-in system blueprints run and create default flows
3. `.config/dev/authentik/blueprints/seizu.yaml` (mounted at `/blueprints/custom`) creates the seizu OIDC provider and application
4. The custom blueprint sets passwords for `akadmin` and `developer` and creates the `developer` user

Note: `REACT_APP_*` vars are injected into the React bundle at dev-server start time, so a container restart is required (not just a hot reload).

**Step 4 — Log in:**

Visit `http://localhost:3000`. You will be redirected to Authentik at `http://localhost:9000`. Log in as `developer` / `devpassword`. Authentik redirects back to `http://localhost:3000/auth/callback`, completes the PKCE exchange, and the app loads with a valid session.

**How the auth flow works:**
- The frontend performs an OIDC Authorization Code + PKCE flow against `http://localhost:9000/application/o/seizu`
- The access token is sent as `Authorization: Bearer <token>` on every API request
- The backend validates the JWT against the JWKS endpoint at `http://authentik-server:9000/application/o/seizu/jwks/` (internal Docker hostname)
- The user's email is read from the `email` JWT claim

**Reverting to no-auth dev mode:**
```bash
make auth_disable
```

This flips the flags back in `.env`, restarts `seizu` and `seizu-node`, and stops the Authentik services.

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
- **`docs/`** — update documentation if behavior, configuration, or interfaces change
- **`AGENTS.MD`** — update these guidelines if new conventions or tooling patterns are introduced (loaded via `.claude/CLAUDE.md`)
