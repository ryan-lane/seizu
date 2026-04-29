# Agent Guidelines

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Seizu?

Seizu (星図) is a configuration-driven reporting platform for Neo4j graph data. Two runtimes:
- **FastAPI web app** (`reporting/`) — serves the React frontend and REST API (ASGI, Gunicorn + UvicornWorker)
- **Scheduled query worker** (`reporting/scheduled_queries.py`) — runs Cypher queries on a schedule with pluggable action plugins (SQS, Slack, log); reads from the database, not the YAML config

## Running Commands with Docker

Never install bun, node, pipenv, or Python directly on the host. Always use `docker compose run --rm <service>`.

### Frontend (`seizu-node`)

```bash
docker compose run --rm seizu-node bun add <package>          # install
docker compose run --rm seizu-node bun test --watchAll=false   # all tests
docker compose run --rm seizu-node bun test src/path/to.test.tsx --watchAll=false
docker compose run --rm seizu-node bun run type-check
```

### Backend (`seizu`)

```bash
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit"
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit/path/test.py::test_name"
docker compose run --rm seizu pipenv install <package>
```

> **Always `pipenv sync --dev` before pytest** — the `.venv` is project-dir-persisted and may be stale after new packages are added.
> **After editing `Pipfile`**, run `docker compose run --rm seizu pipenv lock` then `make lock` to regenerate `requirements.txt`. Commit both `Pipfile` and `Pipfile.lock` together.

### Docs (Sphinx)

Docs have their own isolated virtualenv under `docs/.venv` with pinned deps in `docs/requirements.txt`. Sphinx and its extensions are **not** part of the main project's `Pipfile` — do not add them there. `docs/build.sh` bootstraps the venv on first run and is invoked by `make docs`.

```bash
make docs   # runs docs/build.sh on the host using docs/.venv
```

To add or update a docs dependency, edit `docs/requirements.txt` and re-run `make docs` (the venv will pick up the change on next `pip install`).

### Linting

Run pre-commit **on the host** (the `seizu` container lacks git):
```bash
pre-commit run --all-files
make lint   # same thing
```

### Makefile shortcuts

```bash
make test / make test_unit / make test_frontend
make lint
make schema             # regenerate schema/reporting-schema.json and schema/openapi.json
make generate_openapi   # export schema/openapi.json (no running server needed)
make generate_client LANG=go  # generate client from schema/openapi.json
make seed_dashboard [ARGS="--force|--dry-run|export"]
make auth_enable / make auth_disable
make sqlmodel_enable / make sqlmodel_disable
```

## Adjacent Services Configuration

Config for adjacent dev services lives in `.config/`. Reference that path in `docker-compose.yml`.

`.config/setup.sh` (called by `make up`) copies `.config/dev/` → `.compose/` **only if the destination doesn't exist**. To apply a change to a source file, manually copy it or delete the destination and re-run `make up`. New env vars go in `.env.example`.

**Gunicorn** socket/PID/workdir are set to `/run/seizu` (ephemeral tmpfs) to avoid `EINVAL` errors on macOS Docker bind mounts.

## Architecture

### Frontend (`src/`)

React 19 + TypeScript + Bun + Material-UI + MUI X Charts + `@xyflow/react`.

**Key files:**
- `src/config.context.ts` — `ConfigContext` from `GET /api/v1/config`; OIDC + stats config; Cypher query resolution is per-report via `Report.queries`
- `src/authConfig.context.ts` — `AuthConfigContext`; holds `auth_required`; gates API calls until a token is present
- `src/auth.context.ts` — `AuthContext`; OIDC `user` + `accessToken`
- `src/userManager.ts` — `oidc-client-ts` `UserManager` singleton; returns `null` when auth is off
- `src/components/AuthProvider.tsx` — OIDC flow; registers events, calls `getUser()`, triggers `signinRedirect()` when unauthenticated
- `src/components/OidcCallback.tsx` — `/auth/callback`; calls `signinRedirectCallback()` then navigates to `/`
- `src/hooks/useCypherQuery.ts` — wraps `POST /api/v1/query`; skips if `auth_required` and no token; `saveHistory` param forwards `save_history: true` to record in console history
- `src/hooks/useQueryHistory.ts` — fetches `GET /api/v1/query-history` for the current user; returns `{ loading, error, data, fetchHistory }`
- `src/hooks/useReportsApi.ts` — `useReportsList()`, `useReport(id)`, `useDashboardReport()`, `useAllReports()`, `useReportVersionsList(id)`, `useReportVersion(id, v)`; `useReportsMutations()` for create/save-version/set-dashboard/delete
- `src/components/ReportView.tsx` — shared report renderer; resolves panel `cypher` against `report.queries`
- `src/components/reports/` — panel components (`CypherCount`, `CypherTable`, `CypherBar`, etc.)
- `src/components/reports/CypherGraph.tsx` — graph panel (`@xyflow/react`); accepts map, path, or any format; Graph/Table/Raw tabs; collapsible detail panel
- `src/pages/QueryConsole.tsx` — ad-hoc console at `/app/query-console`; Ctrl+Enter runs query
- `src/components/QueryConsoleSchemaPanel.tsx` — collapsible schema browser; inserts/runs discovery queries on click

**User identity:**
- `src/hooks/useCurrentUser.ts` — `useCurrentUser()` → `GET /api/v1/me`
- `src/hooks/useUser.ts` — `useUser(userId)` → `GET /api/v1/users/<userId>`
- `src/components/UserAvatar.tsx` — `boring-avatars` pixel avatar; use `<UserAvatar name={...} />`
- `src/components/UserDisplay.tsx` — resolves `created_by` user_id to `display_name ?? email`; use `<UserDisplay userId={...} />`
- **Never** display raw user_ids or `sub` values in the UI.

### Backend (`reporting/`)

FastAPI, Python 3.12, Gunicorn + UvicornWorker (ASGI). All I/O is async (neo4j async driver, aioboto3, async SQLAlchemy).

**Key files:**
- `reporting/asgi.py` — ASGI entrypoint: `application = create_app()`
- `reporting/app.py` — `create_app()`; FastAPI with `openapi_url="/api/openapi.json"`, `docs_url="/api/docs"`; registers security headers (`secure`), routers, static files, and SPA fallback via `lifespan`
- `reporting/settings.py` — all config via env vars (Pydantic)
- `reporting/routes/` — `APIRouter`s: `config.py`, `me.py`, `query.py`, `reports.py`, `users.py`, `validate.py`, `scheduled_queries.py`, `static.py` (healthcheck only)
- `reporting/authnz/__init__.py` — `HTTPBearer` + FastAPI `Depends(get_current_user)`; `CurrentUser` dataclass (`user: User`, `jwt_claims: dict`); `sync_user_profile` dependency chains on `get_current_user`; tests override via `app.dependency_overrides[get_current_user]`
- `reporting/services/` — all async: `reporting_neo4j.py` (async Neo4j driver + distributed locking), `report_store/` (pluggable store), `query_validator.py`
- `reporting/schema/reporting_config.py` — Pydantic models for the YAML config
- `reporting/schema/report_config.py` — Pydantic models for DynamoDB items and API schemas

**Async I/O notes:**
- Neo4j: `AsyncGraphDatabase.driver()` for app/worker; a separate `GraphDatabase.driver()` is kept only for CyVer validators (run via `asyncio.to_thread`)
- DynamoDB/SQS: `aioboto3.Session().resource(...)` / `.client(...)` as async context managers
- PostgreSQL: `create_async_engine(...)` + `AsyncSession` from `sqlalchemy.ext.asyncio`; URL prefix `postgresql+asyncpg://`

**Query validation** (`reporting/services/query_validator.py`): `async def validate_query()` returns `ValidationResult(errors, warnings)`. Errors block execution; warnings don't.
1. Syntax + read-only check via `EXPLAIN` (async Neo4j driver)
2. SSRF/exfiltration guard (regex)
3. Schema warnings (CyVer `SchemaValidator` via `asyncio.to_thread` with sync driver)
4. Property warnings (CyVer `PropertiesValidator` via `asyncio.to_thread` with sync driver)

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/config` | OIDC config, stats config, JSON schema |
| POST | `/api/v1/query` | Execute validated read-only Cypher; returns `{results, errors, warnings}`; pass `save_history: true` to record in console history |
| POST | `/api/v1/validate` | Validate Cypher without executing; returns `{errors, warnings}` |
| GET | `/api/v1/query-history` | Paginated query history for the current user; params `page`, `per_page` (1–100) |
| GET | `/api/v1/reports` | List reports (metadata only) |
| POST | `/api/v1/reports` | Create report; 201 |
| GET | `/api/v1/reports/dashboard` | Latest dashboard report; 404 if none |
| PUT | `/api/v1/reports/<id>/dashboard` | Set default dashboard |
| PUT | `/api/v1/reports/<id>/pin` | Pin or unpin report (`{"pinned": bool}`); requires `reports:write` |
| GET | `/api/v1/reports/<id>` | Latest version of a report |
| GET | `/api/v1/reports/<id>/versions` | All versions |
| GET | `/api/v1/reports/<id>/versions/<n>` | Specific version |
| POST | `/api/v1/reports/<id>/versions` | Save new version; 201 |
| DELETE | `/api/v1/reports/<id>` | Delete report + all versions |
| GET | `/api/v1/me` | Current user profile + resolved permissions |
| GET | `/api/v1/users/<user_id>` | User profile by ID; 404 if not found |
| GET | `/api/v1/roles/builtin` | Built-in role definitions (Viewer/Editor/Admin) |
| GET/POST | `/api/v1/roles` | List / create user-defined roles |
| GET/PUT/DELETE | `/api/v1/roles/<id>` | Get / update / delete user-defined role |
| GET | `/api/v1/roles/<id>/versions` | Version history for a role |
| GET | `/api/v1/roles/<id>/versions/<n>` | Specific role version |
| GET/POST | `/api/v1/scheduled-queries` | List / create |
| GET/PUT/DELETE | `/api/v1/scheduled-queries/<id>` | Get / update / delete |
| GET | `/api/v1/scheduled-queries/<id>/versions` | All versions |
| GET | `/api/v1/scheduled-queries/<id>/versions/<n>` | Specific version |
| GET/POST | `/api/v1/toolsets` | List / create toolsets |
| GET/PUT/DELETE | `/api/v1/toolsets/<id>` | Get / update / delete toolset |
| GET | `/api/v1/toolsets/<id>/versions` | All toolset versions |
| GET | `/api/v1/toolsets/<id>/versions/<n>` | Specific toolset version |
| GET/POST | `/api/v1/toolsets/<id>/tools` | List / create tools |
| GET/PUT/DELETE | `/api/v1/toolsets/<id>/tools/<tool_id>` | Get / update / delete tool |
| GET | `/api/v1/toolsets/<id>/tools/<tool_id>/versions` | All tool versions |
| GET | `/api/v1/toolsets/<id>/tools/<tool_id>/versions/<n>` | Specific tool version |
| GET | `/healthcheck` | Healthcheck |
| GET | `/api/openapi.json` | OpenAPI 3.x spec |
| GET | `/api/docs` | Swagger UI |

### CLI (`seizu_cli/`)

Typer app calling the REST API. Invoked via `python -m seizu_cli`.

**Key files:**
- `seizu_cli/main.py` — entry point; global options `--api-url`, `--token`, `--credentials-file`, `--config-file`
- `seizu_cli/config.py` — `SeizuConfig` + `load_config()` reading `~/.config/seizu/seizu.conf`
- `seizu_cli/client.py` — `SeizuClient`; Bearer auth
- `seizu_cli/state.py` — module-level state; `get_client()` lazy factory
- `seizu_cli/commands/` — `reports.py`, `scheduled_queries.py`, `toolsets.py`, `seed.py`, `auth.py`
- `seizu_cli/auth.py` — OS-native keyring or `--credentials-file` fallback; Device Authorization Grant

**Config file** (`~/.config/seizu/seizu.conf`): `api_url` and `seed_file`. Resolution: CLI flag → env var → conf file → default.

**Auth (Device Authorization Grant, RFC 8628):** `seizu login` → device endpoint → user approves in browser → CLI polls → token stored in keyring.

**Usage (inside `seizu` container):**
```bash
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 login
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 reports list
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 toolsets list
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 toolsets tools list <toolset_id>
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 toolsets tools call <toolset_id> <tool_id> --arg limit=10
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed [--force|--dry-run]
PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 export
```
Prefer `make seed_dashboard [ARGS="--force|--dry-run|export"]`.

### MCP Server (`reporting/services/mcp_server.py`)

Seizu exposes an MCP (Model Context Protocol) server at `/api/v1/mcp` when `MCP_ENABLED=true` (default). LLM agents such as Claude can connect and call tools as a standard MCP client.

**Key details:**
- Transport: StreamableHTTP, wired into FastAPI via `_MCPMiddleware` (pure ASGI middleware in `reporting/app.py`) that intercepts `/api/v1/mcp*` before FastAPI routing; avoids a Starlette 1.0.0 issue where `Mount("/api/v1/mcp")` requires a trailing slash and the SPA catch-all returns 405
- Auth: `_MCPAuthMiddleware` validates Bearer JWT tokens using the same `PyJWKClient` logic as the REST API; passes through unauthenticated in dev (`DEVELOPMENT_ONLY_REQUIRE_AUTH=false`). It populates two `contextvars.ContextVar`s for the duration of the request: `_mcp_permissions` (the resolved `frozenset[str]` of permissions) and `_mcp_current_user` (a `CurrentUser`). Built-in handlers that need to attribute writes to a user (e.g. `reports__create`) read the latter.
- Tool names: namespaced as `{group}__{action}` (built-ins) or `{toolset_name}__{tool_name}` (user-defined), both using double underscore
- Tool listing: `@server.list_tools()` merges `list_builtin_tools(settings.MCP_ENABLED_BUILTINS)` with `report_store.list_enabled_tools()` at request time, filtering built-ins by the caller's resolved permissions
- Tool execution: `@server.call_tool()` dispatches to `find_builtin(name, settings.MCP_ENABLED_BUILTINS)` first, falling back to user-defined tools executed via `reporting_neo4j.run_query()`. Built-in handlers enforce their own `required_permissions` before running.

**Built-in tools** live in `reporting/services/mcp_builtins/` — one module per group, registered in `reporting/services/mcp_builtins/__init__.py`. Each tool is a `BuiltinTool` dataclass (see `base.py`) with `name`, `group`, `description`, `input_schema`, `required_permissions`, and an async `handler(args, current_user)`. Handlers share the same service-layer code (`report_store`, `validate_action_configs`, `validate_query`, etc.) used by the REST routes — no logic is duplicated. Permission requirements mirror the REST endpoints.

**Built-in groups** (all enabled by default via `MCP_ENABLED_BUILTINS`):
- `graph` — `graph__schema` (Neo4j schema introspection), `graph__query` (validated read-only Cypher)
- `reports` — list/get/create/delete/pin/set_dashboard/get_dashboard reports, plus version history operations
- `scheduled_queries` — full CRUD + version history; create/update reuse `validate_action_configs` and `validate_query`
- `toolsets` — full CRUD for toolsets and nested tools + version history; create/update tool calls reuse `validate_query`
- `roles` — list built-in + user-defined roles, CRUD for user-defined roles, version history

To add a new built-in group, drop a new `reporting/services/mcp_builtins/<group>.py` exporting a `GROUP_DEF: BuiltinGroup`, then append it to `_GROUPS` in `reporting/services/mcp_builtins/__init__.py` and the default list in `settings.MCP_ENABLED_BUILTINS`.

**OAuth metadata endpoint:** `GET /api/v1/mcp/.well-known/oauth-authorization-server` (RFC 8414). Enabled when `MCP_OAUTH_AUTHORIZATION_ENDPOINT` and `MCP_OAUTH_TOKEN_ENDPOINT` are set. Allows MCP clients (e.g. Claude Desktop) to discover the OIDC provider and authenticate users without a pre-issued token. The auth middleware passes `.well-known` requests through unauthenticated. Settings: `MCP_OAUTH_ISSUER`, `MCP_OAUTH_AUTHORIZATION_ENDPOINT`, `MCP_OAUTH_TOKEN_ENDPOINT`.

**Toolsets and Tools** are user-managed groupings of Cypher-backed tools, stored in the same report store backend (DynamoDB or SQL) with full version history. CRUD is via the REST API. Cypher is validated at create/update time — write queries are blocked.

**DynamoDB key space:**
```
TOOLSET#{id} / #METADATA, VERSION#NNNNNNNNNN
TOOLSET_LIST / TOOLSET#{id}
TOOL#{id}    / #METADATA, VERSION#NNNNNNNNNN
TOOL_LIST#{toolset_id} / TOOL#{id}
```

**SQL tables:** `toolsets`, `toolset_versions`, `tools`, `tool_versions`

### Configuration System

Reports and scheduled queries are stored in DynamoDB (default) or PostgreSQL (`sqlmodel` backend). The YAML config (`.config/dev/seizu/reporting-dashboard.yaml`, mounted as `/reporting-dashboard.yaml`) is a seed source.

**YAML top-level sections:**
- `queries` — named Cypher strings for `scheduled_queries` references only; not served to frontend
- `dashboard` — key pointing to the default dashboard report
- `reports` — report definitions to seed into DynamoDB; each has its own `queries` dict
- `scheduled_queries` — **list** of recurring query definitions (SQS, Slack, log actions)
- `toolsets` — dict of toolset definitions (key → `ToolsetDef`); each has a `tools` dict (key → `ToolDef`) with `name`, `description`, `cypher`, `parameters`, `enabled`

**Report storage** (`reporting/services/report_store/`):
- `base.py` — `ReportStore` ABC
- `dynamodb.py` — single-table design; composite PK/SK; Snowflake IDs; `SNOWFLAKE_MACHINE_ID`
- `sql.py` — SQLModel/SQLAlchemy; 5 tables; configured via `SQL_DATABASE_URL`
- `__init__.py` — `get_store()` factory (env `REPORT_STORE_BACKEND`, default `dynamodb`)

Use `from reporting.services import report_store` — backend is transparent.

**Switching backends:** `make sqlmodel_enable / sqlmodel_disable` then `make down && make up`.

**DynamoDB key design:** `#METADATA`, `#LATEST`, `VERSION#<n>` per report; `SQ#<id>` + `SCHEDULED_QUERY_LIST` per scheduled query; `#DASHBOARD/#POINTER` for the default dashboard.

**Seeding:** Existing reports/queries unchanged unless content differs or `--force`. `cypher` fields resolved against top-level `queries` dict, falling back to literal string. The `Report` TypeScript interface in `src/config.context.ts` must stay in sync with the Pydantic `Report` in `reporting/schema/reporting_config.py`.

### Cartography Data Sync

`nostart` profile. Entrypoint is already `cartography` — do not prefix with it.

```bash
make sync_cve / sync_aws / sync_github / sync_crowdstrike / sync_k8s
```

### Scheduled Query Action Plugins

Located in `reporting/scheduled_query_modules/`. Implement `ModuleInterface` from `__init__.py`.

Required methods: `action_name()`, `setup()`, `handle_results(scheduled_query_id, action, results)`, `action_config_schema()` → `List[ActionConfigFieldDef]` (types: `string`, `text`, `number`, `boolean`, `string_list`, `select`).

Action schemas served via `GET /api/v1/config` as `scheduled_query_action_schemas`.

### Docker Services

| Service | Role |
|---------|------|
| `seizu` | FastAPI backend + static frontend |
| `seizu-node` | Bun dev server |
| `seizu-scheduled-queries` | Scheduled query worker |
| `neo4j` | Graph database |
| `dynamodb` | DynamoDB Local (default backend) |
| `postgres` | PostgreSQL (`sqlmodel` profile) |
| `sqs` | ElasticMQ (local SQS) |
| `authentik-*` | OIDC provider (profile: `auth`) |
| `cartography` | Graph data sync (profile: `nostart`) |

Dev URLs: frontend `http://localhost:3000`, backend `http://localhost:8080`, Authentik `http://localhost:9000`.

**Dockerfile stages:**
- `base` — Python + pipenv + user setup + `Pipfile`/`Pipfile.lock` copied in. No deps installed.
- `dev` — `pipenv install --system --dev`; used by `docker-compose.yml` (`target: dev`) for everything local.
- `nodebuilder` — `oven/bun` image that produces the frontend build.
- `production` — `pipenv install --system --deploy` (prod-only, strict lock) + built frontend. The published image (`publish.yml`) explicitly builds `target: production`, so pytest/pre-commit/etc. never ship.

**Reset named volumes:**
```bash
docker compose down
docker volume rm seizu_neo4j_data seizu_dynamodb_data
docker compose up && make seed_dashboard
```

### Authentication

Backend validates JWTs via `PyJWKClient` (PyJWT) against any OIDC JWKS endpoint.

| Env var | Default | Notes |
|---------|---------|-------|
| `JWKS_URL` | `""` | JWKS endpoint |
| `JWT_EMAIL_CLAIM` | `email` | JWT claim for email |
| `JWT_ISSUER` | `""` | Optional issuer check |
| `JWT_AUDIENCE` | `""` | Must match OIDC client ID when using Authentik |
| `DEVELOPMENT_ONLY_REQUIRE_AUTH` | `true` | Set `false` to bypass auth in dev |
| `TALISMAN_FORCE_HTTPS` | `true` | Set `false` in dev/behind LB |
| `OIDC_AUTHORITY` | `""` | Served to frontend via `/api/v1/config` |
| `OIDC_CLIENT_ID` | `""` | Served to frontend |
| `OIDC_SCOPE` | `"openid email"` | Served to frontend |

Frontend PKCE flow is driven entirely by runtime config from `GET /api/v1/config` — no build-time `REACT_APP_OIDC_*` vars. `redirect_uri` is always derived from `window.location.origin`.

### RBAC

Every authenticated request resolves a role from the JWT, then maps it to a `frozenset[str]` of permission strings. Permissions are enforced at the route level via `require_permission(*perms)` (a FastAPI dependency factory in `reporting/authnz/__init__.py`). The MCP server enforces `tools:call` / `query:execute` via a `contextvars.ContextVar` set in `_MCPAuthMiddleware`.

**Built-in roles** (hierarchical — Admin ⊇ Editor ⊇ Viewer) are defined in `reporting/authnz/permissions.py`. No store I/O needed.

**User-defined roles** are stored in the report store with version history. Resolution does a single `get_role_by_name` lookup.

| Env var | Default | Notes |
|---------|---------|-------|
| `RBAC_ROLE_CLAIM` | `seizu_role` | JWT claim the IDP embeds the role name into |
| `RBAC_DEFAULT_ROLE` | `seizu-viewer` | Role when JWT has no `RBAC_ROLE_CLAIM`; `""` denies access |

**Key files:**
- `reporting/authnz/permissions.py` — `Permission` enum, `BUILTIN_ROLES`, `ALL_PERMISSIONS`, `resolve_permissions(jwt_claims)`
- `reporting/authnz/__init__.py` — `CurrentUser.permissions`, `require_permission()` factory, `get_current_user()` permission resolution
- `reporting/routes/roles.py` — CRUD for user-defined roles

**Dev mode** (`DEVELOPMENT_ONLY_REQUIRE_AUTH=false`): `ALL_PERMISSIONS` is set on every request — no RBAC enforcement.

**Local Authentik setup:**
```bash
make auth_enable && make down && make up   # enable; first run ~2 min
# visit http://localhost:3000, log in as developer/devpassword
make auth_disable && make down && make up  # revert
```
Setup is fully automated via `.config/dev/authentik/blueprints/seizu.yaml`. Device code flow requires `flow_device_code` set on the **Brand** (not the OAuth2Provider). Registered redirect URIs: `http://localhost:3000/auth/callback` and `http://localhost:8080/auth/callback`. Dev credentials: `akadmin/devpassword`, `developer/devpassword`.

### Testing Patterns

- **Backend:** pytest + pytest-mock + pytest-asyncio (`asyncio_mode = auto` in `setup.cfg`) in `tests/unit/reporting/`. All test functions are `async def`. Use `httpx.AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")` for route tests. Override auth via `app.dependency_overrides[get_current_user] = lambda: CurrentUser(...)`. Mock async service calls with `AsyncMock`. See `tests/unit/reporting/routes/query_test.py` for the reference pattern.
- **Frontend:** React Testing Library + Jest (Bun) in `__tests__/` subdirs next to components

### Query Validator Fuzzing

The query validator (`reporting/services/query_validator.py`) enforces three layers:
1. **EXPLAIN write check** — `query_type != 'r'` blocks all write/schema queries
2. **SSRF regex guard** — `_DANGEROUS_RE` scanned against both the original query and the comment-stripped version (see below)
3. **CyVer warnings** — schema and property checks; never block execution

**Running the validator test suite:**
```bash
docker compose run --rm seizu bash -c "pipenv sync --dev && pipenv run pytest tests/unit/reporting/services/query_validator_test.py -v"
```

**Enabling APOC for deeper testing** (APOC procedures are read-classified but can make outbound HTTP requests):
```bash
make apoc_enable   # sets NEO4J_PLUGINS=["apoc"] in .env
make down && make up   # Neo4j downloads APOC on first start
# ... run tests ...
make apoc_disable && make down && make up   # restore default
```

**Fuzzing log:** `tests/data/query-fuzzing.csv` — columns: `Technique, Cypher, Result, Blocked_By, Notes`. Append a row for every new attack vector you try (blocked or not). Useful for regression tracking and audits.

**Key attack categories and their current status:**

| Category | Example | Blocked by |
|---|---|---|
| Write queries (`CREATE`, `MERGE`, `DELETE`, etc.) | `CREATE (n:Test)` | EXPLAIN write check |
| DDL / schema (`CREATE INDEX`, `DROP CONSTRAINT`) | `CREATE INDEX FOR (n:Test) ON (n.id)` | EXPLAIN write check (type `s`) |
| Built-in procedures (`CALL db.clearQueryCaches`) | `CALL db.clearQueryCaches()` | EXPLAIN write check |
| `LOAD CSV` SSRF | `LOAD CSV FROM 'http://169.254.169.254/...' AS row RETURN row` | SSRF regex (original query) |
| `LOAD CSV` comment injection | `LOAD /* bypass */ CSV FROM '...' AS row RETURN row` | SSRF regex (comment-stripped query) |
| APOC procedure SSRF | `CALL apoc.load.json('http://169.254.169.254/...')` | SSRF regex (original query) |
| APOC procedure comment injection | `CALL /* x */ apoc.load.json('...')` | SSRF regex (comment-stripped query) |
| APOC cypher functions (no `CALL`) | `RETURN apoc.cypher.runFirstColumnSingle('SHOW PROCEDURES', {})` | SSRF regex (`\bapoc\.cypher\.`) |
| Dynamic string construction | `WITH 'apoc.load.json(...)' AS q RETURN apoc.cypher.runFirstColumnSingle(q, {})` | SSRF regex (`\bapoc\.cypher\.` matches outer call) |
| Unicode/homoglyph bypass | Zero-width spaces in `CALL`, Cyrillic chars | Neo4j rejects unknown identifiers; still checked |

**Two-sided comment check rationale:**
- Checking the **comment-stripped** query catches `CALL /* x */ apoc.` and `LOAD /* x */ CSV` injection.
- Checking the **original** query catches cases where `//` appears inside a string literal (e.g. a URL `http://...`). The comment stripper treats `//` as a line comment and removes everything after it on that line, which could hide a `CALL apoc.` or `apoc.cypher.` that follows — so the original must also be checked.

**Adding new test cases:**
1. Identify the bypass vector and confirm whether Neo4j executes it (check server logs for `ExternalResourceFailed` or write side effects).
2. Add a row to `tests/data/query-fuzzing.csv`.
3. Add a unit test to `tests/unit/reporting/services/query_validator_test.py` — mock `_get_async_neo4j_client` and `_get_sync_neo4j_client`, set `execute_query` to return a mock summary with `query_type='r'` and no notifications, then assert `result.has_errors` is `True` for blocked inputs.
4. If the vector is not blocked, fix `reporting/services/query_validator.py` first, then write the test to prove the fix.

### Typing

Strict mypy: `check_untyped_defs = true`, `disallow_untyped_defs = true`.
- All functions must have complete type annotations.
- Fix type errors rather than suppressing with `# type: ignore`.
- When touching existing `# type: ignore` comments, fix the underlying issue and remove them.
- Use `typing.cast` only for known-safe invariants the type system can't express.

## Branding

Seizu's brand is a deep-space observatory: a dark navy canvas, starlight-blue as the primary accent, and an amber "ember" as the warm accent. The mark is a dashed-orbit ring wrapping a six-node constellation with one amber anchor star; the wordmark is **Manrope ExtraBold (800)** at tight tracking. The tagline is "A star chart for your security graph." When in doubt, stick to these tokens — don't introduce additional brand colors or fonts.

### Color system

| Token | Hex | RGB | Role |
|---|---|---|---|
| Space | `#0A0F22` | `rgb(10 15 34)` | Primary background (dark surfaces), body text on light surfaces |
| Starlight | `#8FB4FF` | `rgb(143 180 255)` | Primary accent on dark. Shift to `#3A5AA5` on light surfaces for AAA contrast. |
| Ember | `#F5C16C` | `rgb(245 193 108)` | Warm accent on dark. Shift to `#C77B2A` on light surfaces for AAA contrast. |
| Paper | `#F5F6FB` | `rgb(245 246 251)` | Light surface (docs, README background) |

Don't invent shades. If you need opacity variants of Starlight, use `rgba(143, 180, 255, <alpha>)` — the splash page uses `0.04 / 0.08 / 0.12 / 0.25` as the common rungs.

**Extended constellation accents** — for charts and supporting UI. Each has a light tone for dark surfaces and an AAA-contrast dark tone for light surfaces. Defined in `src/theme/brand.ts`; don't add one-off colors for data viz, extend this list instead.

| Name | On dark | On light |
|---|---|---|
| Aurora (teal-green) | `#7AD4B3` | `#2E8866` |
| Pulsar (violet) | `#C9A8FF` | `#7352B8` |
| Flare (coral) | `#F08B7B` | `#B5463A` |
| Beacon (cyan) | `#5DD1F0` | `#1F7FA3` |

`chartColorsFor(mode)` exposes an ordered 6-color palette (Starlight → Ember → Aurora → Pulsar → Flare → Beacon) that MUI X Charts cycles through; both `CypherBar` and `CypherPie` consume it. Keep new chart components on this palette rather than bringing in MUI's stock `colorPalettes`.

### Typography

- **Wordmark:** Manrope 800, `letter-spacing: -0.04em` to `-0.05em` (tighter at larger sizes). Only used inside the Seizu logo/lockup.
- **Display (headings, taglines):** Instrument Serif 400 — for the web app and brand collateral. The docs splash page opts into EB Garamond italic for editorial tone; both are sanctioned.
- **UI / body:** Inter (web app), IBM Plex Sans (docs splash). Don't mix across a single surface.
- **Mono (code, tags, mono labels):** JetBrains Mono.

All four fonts are loaded from Google Fonts; the docs splash already preconnects. New pages should preconnect `https://fonts.googleapis.com` + `https://fonts.gstatic.com` before the stylesheet.

### Logo assets

The canonical SVGs live in two places: `public/static/images/` (served by the React app at `/static/images/`) and `images/` (top-level; `docs/root/images` is a symlink, so docs pick these up automatically, and the GitHub README links them via `/images/...`). Keep the two copies in sync when updating the mark.

| File | When to use |
|---|---|
| `favicon.svg` (`public/` + `images/`) | Browser tab + PWA icon. Simplified form: orbit ring + amber core on Space fill. |
| `logo-horizontal-white.svg` | Full lockup on dark surfaces (navbar, dark README, splash). |
| `logo-horizontal-black.svg` | Full lockup on light surfaces (docs light mode, README light mode). |
| `logo-mark.svg` | Mark-only on dark surfaces (social avatars, OG cards). |
| `logo-mark-light.svg` | Mark-only on light surfaces. |

**Favicon fallback:** `public/favicon.png` is kept only as a legacy fallback for browsers without SVG favicon support. Modern paths reference `favicon.svg` first via `<link rel="icon" type="image/svg+xml">`. Regenerating the PNG to match the new mark is a TODO — no tooling is wired into this repo yet.

**Mark geometry (for reference, don't redraw from scratch):** `viewBox="0 0 140 140"`, orbit `r=54` centered at `(70,70)`, crosshair ticks at 12/3/6/9 o'clock, six constellation nodes at `(40,55)`, `(62,42)`, `(86,52)`, `(100,78)`, `(68,78)`, `(50,98)`. The amber anchor is the `(62,42)` node. At sub-24px, drop the constellation and use orbit ring + amber core only.

### Where these tokens show up today

- **Reporting app** — `src/components/Logo.tsx` (horizontal white lockup), `public/favicon.svg`, `public/manifest.json` (`theme_color: #0a0f22`), `index.html` meta. MUI theme and component styles don't inherit these yet; introduce them deliberately when touching theme code.
- **Docs (Sphinx)** — `docs/conf.py` wires `html_logo`, `html_favicon`, and Shibuya `light_logo`/`dark_logo`. The splash template `docs/root/_templates/splash.html` declares `--brand-space / --brand-starlight / --brand-ember / --brand-paper` custom properties at `:root`; reuse those rather than hardcoding hex in new CSS.
- **README.md** — references `/images/logo-horizontal-{black,white}.svg` with GitHub's `#gh-{light,dark}-mode-only` fragments.

## Frontend Style Guide

### List Views

- Top bar: `<Typography variant="h1">` left, `<Button variant="contained">` right.
- Loading: `<CircularProgress />` inline. Error: `<Error />` icon + `<Typography>` in flex row.
- Table: `<TableContainer component={Paper} variant="outlined">` wrapping `<Table>`.
- Empty state: `<TableRow>` with `<TableCell colSpan={N}>` + `<Typography color="text.secondary">` — not a separate card.
- Rows: `<TableRow hover>`. Metadata cells: `sx={{ color: 'text.secondary' }}`. Dates: `new Date(v).toLocaleString()`. Users: `<UserDisplay userId={...} />`.

**Column name conventions:** Latest Update, Updated By, Created By, Version, Status.

**Per-row actions:** `RowMenu` (three-dot `<IconButton size="small"><MoreVertIcon /></IconButton>` in `<Tooltip title="More actions">`). `anchorOrigin/transformOrigin` bottom/top right. `minWidth: 180`. Destructive actions at bottom behind `<Divider />` with `color: 'error.main'`. Disabled items wrapped in `<Tooltip>` + `<span>`.

**Clickable names:** `sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}` on `<Typography>` (not `<Link>`) when click opens a dialog.

**Detail dialogs (read-only):** Shared component in `src/components/`. Title + optional secondary label + close `<IconButton>`. `<Divider />` below title. `Section` sub-component with `color="text.secondary"` label. Code blocks: `<Box component="pre">` with `bgcolor: 'action.hover'`, `fontFamily: 'monospace'`, `whiteSpace: 'pre-wrap'`, `wordBreak: 'break-word'`.

**Create/delete dialogs:** `maxWidth="sm" fullWidth` (create), `maxWidth="xs" fullWidth` (delete with `<DialogContentText>` + `<strong>` name). `<CircularProgress size={20} />` in submit button while in-flight. Errors in `<Alert severity="error">` at top of `<DialogContent>`.

**Version history pages:** Route `<entity>/:id/history`. Back button `<Button startIcon={<ArrowBackIcon />}>`. Title: `<HistoryIcon color="action" />` + `<Typography variant="h1">Version history – {name}</Typography>`. Columns: Version, Saved, Created By, Comment, actions. Current version: bold + `"current"` in `color="primary"`. Restore: disabled on current with tooltip; `comment: \`Restored from version ${version}\``. Helmet: `History – {name} | Seizu`.

## Keeping Supporting Files Up to Date

When changing the codebase, update as needed:
- **`Makefile`** — new build/test/tool targets
- **`.github/workflows/`** — CI for new test/lint steps
- **`Dockerfile` / `docker-compose.yml`** — new services, files, env vars
- **`.pre-commit-config.yaml`** — linting/formatting changes
- **`Pipfile` + `Pipfile.lock`** — always commit together; run `pipenv lock` then `make lock` after edits
- **`docs/`** — update for any user-facing changes; grep for removed items
- **`schema/reporting-schema.json`** — `make schema` after Pydantic schema changes
- **`.env.example`** — add/remove env vars
- **`AGENTS.MD`** — update when conventions or tooling change
