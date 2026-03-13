# Agent Guidelines

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

# Run tests
docker compose run --rm seizu-node bun test --watchAll=false
```

### Backend (Python/pipenv)

Use the `seizu` service for Python-related commands:

```bash
# Run Python tests
docker compose run --rm seizu pipenv run pytest

# Install Python packages
docker compose run --rm seizu pipenv install <package>
```

### General Rules

- Never install bun, node, pipenv, or Python packages directly on the host machine.
- Always use `docker compose run --rm <service>` for one-off commands.
- Use `docker compose up <service>` for long-running services.
- The `--rm` flag ensures temporary containers are cleaned up after the command completes.
