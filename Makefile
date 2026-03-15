# bash needed for pipefail
SHELL := /bin/bash

args = `arg="$(filter-out $@,$(MAKECMDGOALS))" && echo $${arg:-${1}}`

# Automatically include --profile auth if auth is enabled in .env
AUTH_PROFILE := $(shell grep -q 'DEVELOPMENT_ONLY_REQUIRE_AUTH=true' .env 2>/dev/null && echo '--profile auth' || echo '')

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

.PHONY: test_frontend
test_frontend:
	@docker compose run --rm seizu-node bun run type-check

.PHONY: lock
lock:
	pipenv lock --keep-outdated --requirements > requirements.txt

.PHONY: lock_update
lock_update:
	pipenv lock --requirements > requirements.txt

.PHONY: lock_dev
lock_dev:
	pipenv lock --requirements --dev-only > test-requirements.txt

.PHONY: build
build: clean
	docker build . -t paypay/seizu

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
	docker compose $(AUTH_PROFILE) up $(call args)

.PHONY: down
down:
	docker compose $(AUTH_PROFILE) down

.PHONY: auth_enable
auth_enable:
	@docker compose --profile auth up -d
	@echo "Waiting for Authentik to become healthy..."
	@until [ "$$(docker inspect --format='{{.State.Health.Status}}' seizu-authentik-server-1 2>/dev/null)" = "healthy" ]; do sleep 5; done
	@sed -i '' 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/' .env
	@docker compose up -d seizu seizu-node
	@echo "Auth enabled. Visit http://localhost:3000 and log in as developer/devpassword"

.PHONY: auth_disable
auth_disable:
	@sed -i '' 's/DEVELOPMENT_ONLY_REQUIRE_AUTH=true/DEVELOPMENT_ONLY_REQUIRE_AUTH=false/' .env
	@docker compose up -d seizu seizu-node
	@docker compose --profile auth stop authentik-server authentik-worker authentik-postgresql authentik-redis
	@echo "Auth disabled. Visit http://localhost:3000"

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
