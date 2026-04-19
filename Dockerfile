FROM python:3.12-slim AS base

RUN groupadd seizu && \
    useradd -s /bin/bash -d /home/seizu -m -g seizu seizu

RUN pip3 install pipenv

RUN mkdir /run/seizu && chown seizu:seizu /run/seizu

WORKDIR /home/seizu/seizu

COPY Pipfile Pipfile.lock ./

# Dev image: prod + dev deps (pytest, pre-commit, aiosqlite, etc.).
# Used by docker-compose services for local development, testing, seeding,
# and anything else that may need the dev toolchain.
FROM base AS dev

RUN pipenv install --system --dev

USER seizu

COPY . .

EXPOSE 8080

FROM oven/bun AS nodebuilder

WORKDIR /home/node/seizu

COPY package*.json bun.lock .eslintrc .prettierrc .prettierignore tsconfig.json vite.config.ts .

RUN bun install

COPY . .

RUN bun run build

# Production image: prod-only deps + the built frontend.
# No pytest, pre-commit, or other dev tooling — keeps the image small and
# avoids shipping code paths that are not part of the runtime.
FROM base AS production

RUN pipenv install --system --deploy

USER seizu

COPY --chown=seizu:seizu . .

COPY --chown=seizu:seizu --from=nodebuilder /home/node/seizu/build /build

CMD ["gunicorn", "--config", "/home/seizu/seizu/gunicorn.conf", "reporting.asgi:application", "--workers=2", "-k", "uvicorn.workers.UvicornWorker", "--access-logfile=-", "--error-logfile=-"]
