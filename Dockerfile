FROM python:3.12-slim AS backend

RUN groupadd seizu && \
    useradd -s /bin/bash -d /home/seizu -m -g seizu seizu

RUN pip3 install pipenv

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --dev

RUN mkdir /run/seizu && chown seizu:seizu /run/seizu

USER seizu

WORKDIR /home/seizu/seizu

COPY . .

EXPOSE 8080

FROM oven/bun AS nodebuilder

WORKDIR /home/node/seizu

COPY package*.json bun.lock .eslintrc .prettierrc .prettierignore tsconfig.json vite.config.ts .

RUN bun install

COPY . .

RUN bun run build

FROM backend AS production

COPY --chown=seizu:seizu --from=nodebuilder /home/node/seizu/build /build

CMD ["gunicorn", "--config", "/home/seizu/seizu/gunicorn.conf", "reporting.wsgi:app", "--workers=2", "-k", "gevent", "--access-logfile=-", "--error-logfile=-"]
