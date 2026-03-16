# bash needed for pipefail
SHELL := /bin/bash

args = `arg="$(filter-out $@,$(MAKECMDGOALS))" && echo $${arg:-${1}}`

# Automatically include --profile auth if auth is enabled in .env
AUTH_PROFILE := $(shell grep -q 'DEVELOPMENT_ONLY_REQUIRE_AUTH=true' .env 2>/dev/null && echo '--profile auth' || echo '')
# Automatically include --profile sqlmodel if the sqlmodel backend is selected in .env
SQL_PROFILE := $(shell grep -q 'REPORT_STORE_BACKEND=sqlmodel' .env 2>/dev/null && echo '--profile sqlmodel' || echo '')
COMPOSE_PROFILES := $(AUTH_PROFILE) $(SQL_PROFILE)

.PHONY: clean
clean:
	find . -name "*.pyc" -delete

.PHONY: pipenv_install
pipenv_install:
	pipenv install --dev

junit:
	mkdir -p junit

.PHONY: test
test: test_unit test_frontend

.PHONY: test_unit
test_unit: clean junit pipenv_install
	pipenv run pytest --strict --junitxml=coverage/unit.xml --cov=reporting --cov-report=html:coverage/cov_html --cov-report=xml:coverage/cov.xml --cov-report=term --no-cov-on-fail tests/unit

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

.PHONY: build
build: clean
	docker build . -t paypay/seizu

.PHONY: rebuild
rebuild:
	docker compose build seizu

.PHONY: drop_db
drop_db: down
	@if grep -q 'REPORT_STORE_BACKEND=sqlmodel' .env 2>/dev/null; then \
		echo "Removing postgres_data volume..."; \
		docker volume rm seizu_postgres_data; \
	else \
		echo "Removing dynamodb_data volume..."; \
		docker volume rm seizu_dynamodb_data; \
	fi
	@echo "Done. Run 'make up' to recreate and 'make seed_reports' to reseed."

.PHONY: seed_reports
seed_reports:
	docker compose $(COMPOSE_PROFILES) run --rm seizu bash -c "pipenv sync --dev && PYTHONPATH=/home/seizu/seizu pipenv run python scripts/seed_reports_from_yaml.py --config .config/dev/seizu/reporting-dashboard.yaml $(ARGS)"

.PHONY: schema
schema:
	FLASK_APP=reporting.schema.cli pipenv run flask schema export > schema/reporting-schema.json

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
	@sed -i '' 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/' .env
	@echo "Auth enabled in .env. Run 'make down && make up' to apply."

.PHONY: auth_disable
auth_disable:
	@sed -i '' 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/' .env
	@echo "Auth disabled in .env. Run 'make down && make up' to apply."

.PHONY: sqlmodel_enable
sqlmodel_enable:
	@grep -q 'REPORT_STORE_BACKEND=' .env 2>/dev/null \
		&& sed -i '' 's/REPORT_STORE_BACKEND=.*/REPORT_STORE_BACKEND=sqlmodel/' .env \
		|| echo 'REPORT_STORE_BACKEND=sqlmodel' >> .env
	@echo "SQLModel backend enabled in .env. Run 'make down && make up' to apply."

.PHONY: sqlmodel_disable
sqlmodel_disable:
	@grep -q 'REPORT_STORE_BACKEND=' .env 2>/dev/null \
		&& sed -i '' 's/REPORT_STORE_BACKEND=.*/REPORT_STORE_BACKEND=dynamodb/' .env \
		|| echo 'REPORT_STORE_BACKEND=dynamodb' >> .env
	@echo "DynamoDB backend restored in .env. Run 'make down && make up' to apply."

.PHONY: restart
restart:
	docker compose restart $(call args)

.PHONY: logs
logs:
	docker compose logs -f $(call args)

.PHONY: sync_aws
sync_aws:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=aws --aws-sync-all-profiles --permission-relationships-file=/etc/cartography/permission_relationships.yaml

.PHONY: sync_k8s
sync_k8s:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=kubernetes --k8s-kubeconfig=/etc/cartography/kube.config

.PHONY: sync_crowdstrike
sync_crowdstrike:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=crowdstrike --crowdstrike-client-id-env-var=CROWDSTRIKE_CLIENT_ID --crowdstrike-client-secret-env-var=CROWDSTRIKE_CLIENT_SECRET

.PHONY: sync_github
sync_github:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=github --github-config-env-var=GITHUB_TOKEN

.PHONY: sync_cve
sync_cve:
	docker compose run cartography --neo4j-uri=bolt://neo4j:7687 --selected-modules=cve --cve-enabled
