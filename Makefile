VIRTUAL_ENV ?= .venv

# =============
#  Development
# =============

$(VIRTUAL_ENV): poetry.lock
	@poetry install --with dev --extras redislite
	@poetry run pre-commit install --hook-type pre-push
	@touch $(VIRTUAL_ENV)

.PHONY: test
# target: test - Runs tests
t test: $(VIRTUAL_ENV)
	@poetry run pytest tests.py

.PHONY: lint
# target: lint - Check code
lint: $(VIRTUAL_ENV)
	@poetry run mypy
	@poetry run ruff muffin_redis

# ==============
#  Bump version
# ==============

.PHONY: release
VPART?=minor
# target: release - Bump version
release:
	@git checkout develop
	@git pull
	@poetry version $(VPART)
	@git commit -am "Bump version: `poetry version -s`"
	@git tag `poetry version -s`
	@git checkout master
	@git pull
	@git merge develop
	@git checkout develop
	@git push --tags origin develop master

.PHONY: minor
minor: release

.PHONY: patch
patch:
	make release VPART=patch

.PHONY: major
major:
	make release VPART=major

.PHONY: v version
v version:
	@poetry version -s
