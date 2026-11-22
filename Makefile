UV_RUN := uv run --locked
CLI := $(UV_RUN) python -m pipeline.cli

.PHONY: setup check prepare protocol report promote table verify export-models test lint all

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
	$(UV_RUN) ruff check pipeline tests
	$(UV_RUN) basedpyright

all:
	$(CLI) all
