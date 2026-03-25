# bash needed for pipefail
SHELL := /bin/bash

args = `arg="$(filter-out $@,$(MAKECMDGOALS))" && echo $${arg:-${1}}`

# Automatically include --profile auth if auth is enabled in .env
AUTH_PROFILE := $(shell grep -q 'DEVELOPMENT_ONLY_REQUIRE_AUTH=true' .env 2>/dev/null && echo '--profile auth' || echo '')
# Automatically include --profile sqlmodel if the sqlmodel backend is selected in .env
SQL_PROFILE := $(shell grep -q 'REPORT_STORE_BACKEND=sqlmodel' .env 2>/dev/null && echo '--profile sqlmodel' || echo '')
COMPOSE_PROFILES := $(AUTH_PROFILE) $(SQL_PROFILE)

.PHONY: pipenv_install
pipenv_install:
	pipenv install --dev

junit:
	mkdir -p junit

.PHONY: test
test: test_unit test_frontend

.PHONY: test_unit
test_unit: junit pipenv_install
	pipenv run pytest --strict --junitxml=coverage/unit.xml --cov=reporting --cov=seizu_schema --cov-report=html:coverage/cov_html --cov-report=xml:coverage/cov.xml --cov-report=term --no-cov-on-fail tests/unit

.PHONY: test_integration
test_integration:
	docker compose run --rm seizu pipenv run pytest tests/integration -v

.PHONY: test_frontend
test_frontend:
	@docker compose run --rm seizu-node bun run type-check

.PHONY: lock
lock:
	docker compose run --rm seizu bash -c "cd /home/seizu/seizu && pipenv requirements" > requirements.txt

.PHONY: lock_update
lock_update:
	docker compose run --rm seizu bash -c "cd /home/seizu/seizu && pipenv lock && pipenv requirements" > requirements.txt

.PHONY: lock_dev
lock_dev:
	docker compose run --rm seizu bash -c "cd /home/seizu/seizu && pipenv requirements --dev-only" > test-requirements.txt

.PHONY: rebuild
rebuild:
	docker compose build seizu
	docker compose run --rm seizu-node bun run build

.PHONY: drop_db
drop_db: down
	@if grep -q 'REPORT_STORE_BACKEND=sqlmodel' .env 2>/dev/null; then \
		echo "Removing postgres_data volume..."; \
		docker volume rm seizu_postgres_data; \
	else \
		echo "Removing dynamodb_data volume..."; \
		docker volume rm seizu_dynamodb_data; \
	fi
	@echo "Done. Run 'make up' to recreate and 'make seed_dashboard' to reseed."

.PHONY: seed_dashboard
seed_dashboard:
	docker compose $(COMPOSE_PROFILES) run --rm seizu bash -c "pipenv sync --dev && PYTHONPATH=/home/seizu/seizu pipenv run python -m seizu_cli --api-url http://seizu:8080 seed --config .config/dev/seizu/reporting-dashboard.yaml $(ARGS)"

.PHONY: schema
schema: generate_openapi
	FLASK_APP=reporting.schema.cli pipenv run flask schema export > schema/reporting-schema.json

# Export the OpenAPI spec from the running APIFlask app (no backend connections required).
.PHONY: generate_openapi
generate_openapi:
	FLASK_APP=reporting.app:create_app DYNAMODB_CREATE_TABLE=false pipenv run flask spec --output schema/openapi.json

# Generate a client library from schema/openapi.json using openapi-generator-cli.
# Usage: make generate_client LANG=go
#        make generate_client LANG=typescript-fetch
#        make generate_client LANG=java
# See https://openapi-generator.tech/docs/generators for all supported languages.
LANG ?= python
.PHONY: generate_client
generate_client: generate_openapi
	docker run --rm \
		-v $(PWD):/local \
		openapitools/openapi-generator-cli generate \
		-i /local/schema/openapi.json \
		-g $(LANG) \
		-o /local/generated/$(LANG)-client \
		--package-name seizu_client

# Build the seizu-cli pip-installable distribution (wheel + sdist).
# Output lands in dist/. Requires the `build` package (pip install build).
.PHONY: build_cli
build_cli:
	docker compose run --rm seizu bash -c "pip install --quiet build && python -m build"

.PHONY: docs
docs: schema
	@bash docs/build.sh

.PHONY: bun
bun:
	@docker compose run seizu-node bun $(call args)

.PHONY: setup
config_setup:
	@./.config/setup.sh

.PHONY: up
up: config_setup
	docker compose $(COMPOSE_PROFILES) up $(call args)

.PHONY: down
down:
	docker compose $(COMPOSE_PROFILES) down

.PHONY: auth_enable
auth_enable:
	@perl -pi -e 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/' .env
	@echo "Auth enabled in .env. Run 'make down && make up' to apply."

.PHONY: auth_disable
auth_disable:
	@perl -pi -e 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/' .env
	@echo "Auth disabled in .env. Run 'make down && make up' to apply."

.PHONY: sqlmodel_enable
sqlmodel_enable:
	@grep -q 'REPORT_STORE_BACKEND=' .env 2>/dev/null \
		&& perl -pi -e 's/REPORT_STORE_BACKEND=.*/REPORT_STORE_BACKEND=sqlmodel/' .env \
		|| echo 'REPORT_STORE_BACKEND=sqlmodel' >> .env
	@echo "SQLModel backend enabled in .env. Run 'make down && make up' to apply."

.PHONY: sqlmodel_disable
sqlmodel_disable:
	@grep -q 'REPORT_STORE_BACKEND=' .env 2>/dev/null \
		&& perl -pi -e 's/REPORT_STORE_BACKEND=.*/REPORT_STORE_BACKEND=dynamodb/' .env \
		|| echo 'REPORT_STORE_BACKEND=dynamodb' >> .env
	@echo "DynamoDB backend restored in .env. Run 'make down && make up' to apply."

.PHONY: restart
restart:
	docker compose restart $(call args)

.PHONY: logs
logs:
	docker compose logs -f $(call args)

.PHONY: send_stats
send_stats:
	docker compose $(COMPOSE_PROFILES) run --rm seizu-dashboard-stats

.PHONY: sync_aws
sync_aws:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=create-indexes,aws,analysis --aws-sync-all-profiles --permission-relationships-file=/etc/cartography/permission_relationships.yaml

.PHONY: sync_k8s
sync_k8s:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=create-indexes,kubernetes,analysis --k8s-kubeconfig=/etc/cartography/kube.config

.PHONY: sync_crowdstrike
sync_crowdstrike:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=create-indexes,crowdstrike,analysis --crowdstrike-client-id-env-var=CROWDSTRIKE_CLIENT_ID --crowdstrike-client-secret-env-var=CROWDSTRIKE_CLIENT_SECRET

.PHONY: sync_github
sync_github:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=create-indexes,github,analysis --github-config-env-var=GITHUB_TOKEN

.PHONY: sync_cve
sync_cve:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=create-indexes,cve,analysis --cve-enabled
