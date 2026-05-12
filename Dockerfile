FROM python:3.14-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.1 /uv /uvx /usr/local/bin/

RUN groupadd seizu && \
    useradd -s /bin/bash -d /home/seizu -m -g seizu seizu

RUN mkdir /run/seizu && chown seizu:seizu /run/seizu

WORKDIR /home/seizu/seizu

ENV UV_PROJECT_ENVIRONMENT=/usr/local \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

COPY pyproject.toml uv.lock ./
COPY packages/seizu-cli/pyproject.toml packages/seizu-cli/pyproject.toml

# Dev image: prod + dev deps (pytest, pre-commit, aiosqlite, etc.).
# Used by docker-compose services for local development, testing, seeding,
# and anything else that may need the dev toolchain.
FROM base AS dev

RUN uv sync --frozen --all-groups --all-packages --no-install-workspace

USER seizu

COPY . .

EXPOSE 8080

FROM oven/bun AS nodebuilder

WORKDIR /home/node/seizu

COPY package.json bun.lock .eslintrc .prettierrc .prettierignore tsconfig.json vite.config.ts .

RUN bun install

COPY . .

RUN bun run build

# Production image: prod-only deps + the built frontend.
# No pytest, pre-commit, or other dev tooling — keeps the image small and
# avoids shipping code paths that are not part of the runtime.
FROM base AS production

RUN uv sync --frozen --no-dev --package seizu --no-install-workspace

USER seizu

COPY --chown=seizu:seizu . .

COPY --chown=seizu:seizu --from=nodebuilder /home/node/seizu/build /build

CMD ["gunicorn", "--config", "/home/seizu/seizu/gunicorn.conf", "reporting.asgi:application", "--workers=2", "-k", "uvicorn.workers.UvicornWorker", "--access-logfile=-", "--error-logfile=-"]
