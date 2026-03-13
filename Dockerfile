FROM oven/bun AS nodebuilder

ENV INLINE_RUNTIME_CHUNK=false

WORKDIR /home/node/seizu

COPY package*.json bun.lock .eslintrc .prettierrc .prettierignore jsconfig.json .

RUN bun install

COPY . .

RUN bun run build --production

FROM python:3.9-slim

RUN groupadd seizu && \
    useradd -s /bin/bash -d /home/seizu -m -g seizu seizu

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

RUN mkdir /run/seizu && chown seizu:seizu /run/seizu

USER seizu

WORKDIR /home/seizu/seizu

COPY --chown=seizu:seizu --from=nodebuilder /home/node/seizu/build /build

COPY . .

EXPOSE 8080

CMD ["gunicorn", "--config", "/home/seizu/seizu/gunicorn.conf", "reporting.wsgi:app", "--workers=2", "-k", "gevent", "--access-logfile=-", "--error-logfile=-"]
