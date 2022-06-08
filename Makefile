# bash needed for pipefail
SHELL := /bin/bash

args = `arg="$(filter-out $@,$(MAKECMDGOALS))" && echo $${arg:-${1}}`

.PHONY: clean
clean:
	find . -name "*.pyc" -delete

.PHONY: pipenv_install
pipenv_install:
	pipenv install --dev

junit:
	mkdir -p junit

.PHONY: test
test: test_unit

.PHONY: test_unit
test_unit: clean junit pipenv_install
	pipenv run pytest --strict --junitxml=coverage/unit.xml --cov=reporting --cov-report=html:coverage/cov_html --cov-report=xml:coverage/cov.xml --cov-report=term --no-cov-on-fail tests/unit

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

.PHONY: yarn
yarn:
	@docker-compose run seizu-node yarn $(call args)

.PHONY: add_ssl
add_ssl:
	@./add-ssl.sh

.PHONY: setup
config_setup:
	@./.config/setup.sh

.PHONY: up
up: config_setup
	docker-compose up $(call args)

.PHONY: down
down:
	docker-compose down

.PHONY: restart
restart:
	docker-compose restart $(call args)

.PHONY: logs
logs:
	docker-compose logs -f $(call args)

.PHONY: sync_aws
sync_aws:
	docker-compose run cartography cartography --neo4j-password-env-var=NEO4J_PASSWORD --neo4j-user=neo4j --neo4j-uri=bolt://neo4j:7687 --aws-sync-all-profiles --permission-relationships-file=/etc/cartography/permission_relationships.yaml

.PHONY: sync_k8s
sync_k8s:
	docker-compose run cartography cartography --neo4j-password-env-var=NEO4J_PASSWORD --neo4j-user=neo4j --neo4j-uri=bolt://neo4j:7687 --k8s-kubeconfig=/etc/cartography/kube.config

.PHONY: sync_crowdstrike
sync_crowdstrike:
	docker-compose run cartography cartography --neo4j-password-env-var=NEO4J_PASSWORD --neo4j-user=neo4j --neo4j-uri=bolt://neo4j:7687 --crowdstrike-client-id-env-var=CROWDSTRIKE_CLIENT_ID --crowdstrike-client-secret-env-var=CROWDSTRIKE_CLIENT_SECRET

.PHONY: sync_github
sync_github:
	docker-compose run cartography cartography --neo4j-password-env-var=NEO4J_PASSWORD --neo4j-user=neo4j --neo4j-uri=bolt://neo4j:7687 --github-config-env-var=GITHUB_TOKEN

.PHONY: sync_cve
sync_cve:
	docker-compose run cartography cartography --neo4j-password-env-var=NEO4J_PASSWORD --neo4j-user=neo4j --neo4j-uri=bolt://neo4j:7687 --cve-enabled
