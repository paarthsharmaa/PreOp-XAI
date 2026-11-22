UV_RUN := uv run --locked
CLI := $(UV_RUN) python -m pipeline.cli

.PHONY: setup check prepare protocol report promote table verify export-models test lint all \
	app app-data app-static app-test app-e2e app-screenshots

setup:
	uv sync --locked

check:
	$(CLI) check

prepare:
	$(CLI) prepare

protocol:
	$(CLI) protocol

report:
	$(CLI) report

promote:
	$(CLI) report --promote
	$(UV_RUN) python -m pipeline.reporting.render_table

table:
	$(UV_RUN) python -m pipeline.reporting.render_table

verify:
	$(CLI) verify

export-models:
	$(CLI) export-models

test:
	$(UV_RUN) pytest

lint:
	$(UV_RUN) ruff check app pipeline tests
	$(UV_RUN) basedpyright

all:
	$(CLI) all

app-data:
	$(UV_RUN) python -m app.build_data

app: app-data
	bash app/run.sh

app-static: app-data
	npm --prefix app/web ci
	npm --prefix app/web run build:static

app-test: app-data
	$(UV_RUN) --group app pytest app/tests

app-e2e: app-data
	npm --prefix app/web run build
	npm --prefix app/web run build:static
	npm --prefix app/web run test:e2e

app-screenshots: app-data
	npm --prefix app/web run build
	npm --prefix app/web run build:static
	npm --prefix app/web run screenshots
