.PHONY: all format lint test tests test_watch integration_tests docker_tests help extended_tests \
        serve dashboard benchmarks health validate docker-build docker-up clean

# ============================================================
# PlaceGuard Makefile — VOYGR Place Validation Service
# ============================================================

# Default target executed when no arguments are given to make.
all: help

# Define a variable for the test file path.
TEST_FILE ?= tests/unit_tests/
SRC_DIR   := src

# ---- Running ----

serve:			## Start the FastAPI server (port 8080)
	@echo "Starting PlaceGuard API on http://localhost:8080"
	PYTHONPATH=$(SRC_DIR) uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

dashboard:		## Start the Streamlit dashboard (port 8501)
	@echo "🎨 Starting PlaceGuard Dashboard on http://localhost:8501"
	PYTHONPATH=$(SRC_DIR) streamlit run $(SRC_DIR)/dashboard/app.py \
		--server.port 8501

start-all:		## Start both API and dashboard simultaneously
	@trap 'kill %1 %2 2>/dev/null; exit' INT; \
	PYTHONPATH=$(SRC_DIR) uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload & \
	sleep 2 && \
	PYTHONPATH=$(SRC_DIR) streamlit run $(SRC_DIR)/dashboard/app.py --server.port 8501 & \
	wait

# ---- Testing ----

test:
	PYTHONPATH=$(SRC_DIR) python -m pytest $(TEST_FILE)

integration_tests:
	PYTHONPATH=$(SRC_DIR) python -m pytest tests/integration_tests

test-unit:
	PYTHONPATH=$(SRC_DIR) python -m pytest tests/unit_tests -v --tb=short

test-benchmarks:	## Run benchmark scenarios (requires API server running)
	PYTHONPATH=$(SRC_DIR) python -m pytest tests/integration_tests/test_benchmarks.py -v --tb=short

test-cov:		## Run tests with coverage
	PYTHONPATH=$(SRC_DIR) python -m pytest tests/unit_tests \
		--cov=$(SRC_DIR)/agent --cov-report=term-missing -v

test_watch:
	python -m ptw --snapshot-update --now . -- -vv tests/unit_tests

test_profile:
	python -m pytest -vv tests/unit_tests/ --profile-svg

extended_tests:
	python -m pytest --only-extended $(TEST_FILE)


# ---- Utilities ----

health:			## Check API health
	curl -s http://localhost:8080/health | python3 -m json.tool

validate:		## Quick validation test (requires API running)
	curl -s -X POST http://localhost:8080/validate-place \
		-H "Content-Type: application/json" \
		-d '{"query": "Rooftop bar with cocktails under $$20"}' \
		| python3 -m json.tool

benchmarks:		## Run benchmarks via API (requires API running)
	curl -s -X POST http://localhost:8080/run-benchmark | python3 -m json.tool

docker-build:
	docker build -t placeguard:latest .

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
	@echo "✅ Cleaned"


######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
PYTHON_FILES=src/
MYPY_CACHE=.mypy_cache
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$|\.ipynb$$')
lint_package: PYTHON_FILES=src
lint_tests: PYTHON_FILES=tests
lint_tests: MYPY_CACHE=.mypy_cache_test

lint lint_diff lint_package lint_tests:
	python -m ruff check .
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff format $(PYTHON_FILES) --diff
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff check --select I $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || python -m mypy --strict $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || mkdir -p $(MYPY_CACHE) && python -m mypy --strict $(PYTHON_FILES) --cache-dir $(MYPY_CACHE)

format format_diff:
	ruff format $(PYTHON_FILES)
	ruff check --select I --fix $(PYTHON_FILES)

spell_check:
	codespell --toml pyproject.toml

spell_fix:
	codespell --toml pyproject.toml -w

######################
# HELP
######################

help:
	@echo ''
	@echo 'PlaceGuard — VOYGR Place Validation Service'
	@echo '============================================'
	@echo 'serve              - Start FastAPI API (port 8000)'
	@echo 'dashboard          - Start Streamlit dashboard (port 8501)'
	@echo 'start-all          - Start API + dashboard together'
	@echo 'test               - Run unit tests'
	@echo 'test-benchmarks    - Run VOYGR benchmark scenarios'
	@echo 'health             - Check API health'
	@echo 'validate           - Quick validation test'
	@echo 'benchmarks         - Run all benchmark scenarios'
	@echo 'format             - run code formatters'
	@echo 'lint               - run linters'
	@echo ''



######################
# LINTING AND FORMATTING
######################

# Define a variable for Python and notebook files.
PYTHON_FILES=src/
MYPY_CACHE=.mypy_cache
lint format: PYTHON_FILES=.
lint_diff format_diff: PYTHON_FILES=$(shell git diff --name-only --diff-filter=d main | grep -E '\.py$$|\.ipynb$$')
lint_package: PYTHON_FILES=src
lint_tests: PYTHON_FILES=tests
lint_tests: MYPY_CACHE=.mypy_cache_test

lint lint_diff lint_package lint_tests:
	python -m ruff check .
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff format $(PYTHON_FILES) --diff
	[ "$(PYTHON_FILES)" = "" ] || python -m ruff check --select I $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || python -m mypy --strict $(PYTHON_FILES)
	[ "$(PYTHON_FILES)" = "" ] || mkdir -p $(MYPY_CACHE) && python -m mypy --strict $(PYTHON_FILES) --cache-dir $(MYPY_CACHE)

format format_diff:
	ruff format $(PYTHON_FILES)
	ruff check --select I --fix $(PYTHON_FILES)

spell_check:
	codespell --toml pyproject.toml

spell_fix:
	codespell --toml pyproject.toml -w

######################
# HELP
######################

help:
	@echo '----'
	@echo 'format                       - run code formatters'
	@echo 'lint                         - run linters'
	@echo 'test                         - run unit tests'
	@echo 'tests                        - run unit tests'
	@echo 'test TEST_FILE=<test_file>   - run all tests in file'
	@echo 'test_watch                   - run unit tests in watch mode'

