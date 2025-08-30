# Healthcare Conversational AI Service Justfile
# This service handles conversational AI for healthcare appointment management

# Default task - lists all available commands
_default:
    @just --list

# Variables
PYTHON_VERSION := "3.13"
DOCKER_IMAGE := "healthcare-ai"
VENV_NAME := ".venv"
DEV_PORT := "9001"

# --- Development Environment ---

# Sets up the complete development environment
setup: _install_uv _install_python _create_venv _install_deps _install_precommit_hooks
    #!/usr/bin/env bash
    echo "✅ Healthcare AI service setup complete"
    echo "Activate your virtual environment: just activate"
    echo "Start development server: just dev"

# Activate the virtual environment
# Note: Cannot directly activate from justfile because:
# 1. 'source' modifies the current shell environment
# 2. justfile runs commands in subshells that exit immediately
# 3. Environment changes don't persist to the parent shell
# User must run the source command in their current shell
activate:
    #!/usr/bin/env bash
    echo "To activate the virtual environment, run:"
    echo "source {{VENV_NAME}}/bin/activate"

# Installs the uv Python package manager
_install_uv:
    #!/usr/bin/env bash
    if command -v uv &> /dev/null; then
        echo "uv is already installed, skipping installation"
        exit 0
    fi
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo "Updating uv..."
    uv self update

# Installs Python using uv
_install_python:
    #!/usr/bin/env bash
    if uv python list | grep -q "{{PYTHON_VERSION}}"; then
        echo "Python {{PYTHON_VERSION}} is already installed"
        exit 0
    fi
    echo "Installing Python {{PYTHON_VERSION}}..."
    uv python install {{PYTHON_VERSION}}

# Creates a Python virtual environment
_create_venv:
    #!/usr/bin/env bash
    if [ -d "{{VENV_NAME}}" ]; then
        echo "Virtual environment already exists"
        exit 0
    fi
    echo "Creating virtual environment '{{VENV_NAME}}'..."
    uv venv {{VENV_NAME}} --python {{PYTHON_VERSION}}

# Installs Python dependencies
_install_deps:
    #!/usr/bin/env bash
    echo "Installing Python dependencies..."
    uv pip install -e .
    echo "Installing development dependencies..."
    uv pip install -e .[dev]

# Installs pre-commit hooks
_install_precommit_hooks:
    #!/usr/bin/env bash
    echo "Installing pre-commit hooks..."
    uv run pre-commit install
    echo "Pre-commit hooks installed"

# Starts the service in development mode (local)
dev:
    #!/usr/bin/env bash
    echo "===================================="
    echo "🚀 API READY: http://localhost:{{DEV_PORT}}"
    echo "===================================="
    echo ""
    echo "Starting Healthcare AI service in development mode..."
    echo "Press Ctrl+C to stop"
    echo ""
    uv run uvicorn app.main:app --host 0.0.0.0 --port {{DEV_PORT}}

# Starts the service with hot reload
dev_reload:
    #!/usr/bin/env bash
    echo "===================================="
    echo "🚀 API READY: http://localhost:{{DEV_PORT}}"
    echo "===================================="
    echo ""
    echo "Starting Healthcare AI service with hot reload..."
    echo "Press Ctrl+C to stop"
    echo ""
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port {{DEV_PORT}}

# --- Code Quality ---

# Runs all checks (linting, type checking, security)
check: lint typecheck security

# Runs linting on code
lint:
    #!/usr/bin/env bash
    echo "Linting code..."
    uv run ruff check .

# Runs type checking on code
typecheck:
    #!/usr/bin/env bash
    echo "Type checking code..."
    uv run mypy --config-file pyproject.toml app/

# Runs security scanning on code
security:
    #!/usr/bin/env bash
    echo "Running security scan..."
    uv run bandit -r app/ -f json | jq -r '.results[] | "\(.filename):\(.line_number): \(.test_id) \(.issue_text)"' || echo "No security issues found"

# Fixes linting issues
lint_fix:
    #!/usr/bin/env bash
    echo "Fixing linting issues..."
    uv run ruff check --fix .

# Formats code
format:
    #!/usr/bin/env bash
    echo "Formatting code..."
    uv run ruff format .

# Runs pre-commit hooks on all files
run_precommit *ARGS:
    #!/usr/bin/env bash
    ARGS={{ARGS}}
    echo "Running pre-commit hooks${ARGS:+ with args: $ARGS}..."
    uv run pre-commit run {{ARGS}}

# --- Testing ---

# Runs all tests with coverage reporting
test:
    #!/usr/bin/env bash
    echo "Running tests..."
    mkdir -p .build
    uv run pytest --verbose --tb=short \
        --cov=app \
        --cov-report=xml:.build/coverage.xml \
        --cov-report=term-missing \
        --cov-report=html:.build/coverage_html \
        | tee .build/test_output.txt

# Runs tests in watch mode
test_watch:
    #!/usr/bin/env bash
    echo "Running tests in watch mode..."
    uv run pytest-watch -- --verbose --tb=short

# --- Docker ---

# Builds the Docker image
build:
    #!/usr/bin/env bash
    echo "Building Docker image..."
    docker build -t {{DOCKER_IMAGE}}:latest .

# Runs the service in Docker
run_docker: build
    #!/usr/bin/env bash
    echo "===================================="
    echo "🚀 API READY: http://localhost:{{DEV_PORT}}"
    echo "===================================="
    echo ""
    echo "Starting Healthcare AI service in Docker..."
    echo "(uvicorn logs below can be ignored)"
    echo "Press Ctrl+C to stop"
    echo ""
    docker run --rm -p {{DEV_PORT}}:8000 --name healthcare-ai-dev {{DOCKER_IMAGE}}:latest

# Runs the service in Docker with environment file
run_docker_env: build
    #!/usr/bin/env bash
    if [ ! -f ".env" ]; then
        echo "❌ .env file not found. Create one with required environment variables."
        exit 1
    fi
    echo "===================================="
    echo "🚀 API READY: http://localhost:{{DEV_PORT}}"
    echo "===================================="
    echo ""
    echo "Starting Healthcare AI service in Docker with .env file..."
    echo "(uvicorn logs below can be ignored)"
    echo "Press Ctrl+C to stop"
    echo ""
    docker run --rm -p {{DEV_PORT}}:8000 --env-file .env --name healthcare-ai-dev {{DOCKER_IMAGE}}:latest

# Opens a shell in the Docker container
shell_docker: build
    #!/usr/bin/env bash
    docker run --rm -it --entrypoint /bin/bash {{DOCKER_IMAGE}}:latest

# --- API Testing ---

# Tests the API endpoint with curl
test_api:
    #!/usr/bin/env bash
    echo "Testing API endpoint..."
    echo "Testing POST /conversation endpoint:"
    curl -X POST http://localhost:{{DEV_PORT}}/conversation \
        -H "Content-Type: application/json" \
        -d '{"message": "Hello, I need help with my appointments", "session_id": "test-session-123"}' \
        -w "\nStatus: %{http_code}\n"

# Tests the health endpoint
test_health:
    #!/usr/bin/env bash
    echo "Testing health endpoint..."
    curl -X GET http://localhost:{{DEV_PORT}}/health -w "\nStatus: %{http_code}\n"

# Open API documentation in browser
docs:
    #!/usr/bin/env bash
    echo "Opening Swagger UI..."
    if command -v open &> /dev/null; then
        open http://localhost:{{DEV_PORT}}/docs
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:{{DEV_PORT}}/docs
    else
        echo "Please open http://localhost:{{DEV_PORT}}/docs in your browser"
    fi

# Open ReDoc documentation in browser
redoc:
    #!/usr/bin/env bash
    echo "Opening ReDoc..."
    if command -v open &> /dev/null; then
        open http://localhost:{{DEV_PORT}}/redoc
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:{{DEV_PORT}}/redoc
    else
        echo "Please open http://localhost:{{DEV_PORT}}/redoc in your browser"
    fi

# --- Utilities ---

# Updates all dependencies
update_deps:
    #!/usr/bin/env bash
    echo "Updating Python dependencies..."
    uv pip install -e . --upgrade
    echo "Updating development dependencies..."
    uv pip install -e .[dev] --upgrade

# Validates the development environment setup
validate_setup:
    #!/usr/bin/env bash
    echo "🔍 Validating development environment setup..."
    echo ""

    # Check Python
    if command -v python &> /dev/null; then
        echo "✅ Python: $(python --version)"
    else
        echo "❌ Python: Not found"
    fi

    # Check uv
    if command -v uv &> /dev/null; then
        echo "✅ uv: $(uv --version)"
    else
        echo "❌ uv: Not found"
    fi

    # Check virtual environment
    if [ -d "{{VENV_NAME}}" ]; then
        echo "✅ Python virtual environment: Found"
    else
        echo "❌ Python virtual environment: Not found"
    fi

    # Check pre-commit
    if uv run pre-commit --version &> /dev/null; then
        echo "✅ pre-commit: Available"
    else
        echo "❌ pre-commit: Not found"
    fi

    # Check Docker
    if command -v docker &> /dev/null; then
        echo "✅ Docker: $(docker --version)"
    else
        echo "❌ Docker: Not found"
    fi

    echo ""
    echo "💡 Run 'just setup' to install missing components"

# Shows current environment variables
env:
    #!/usr/bin/env bash
    echo "Service Environment Variables:"
    echo "PYTHON_VERSION: {{PYTHON_VERSION}}"
    echo "DOCKER_IMAGE: {{DOCKER_IMAGE}}"
    echo "VENV_NAME: {{VENV_NAME}}"
    echo "DEV_PORT: {{DEV_PORT}}"
    echo ""
    echo "Installed Versions:"
    echo "Python: $(python --version 2>/dev/null || echo 'Not available')"
    echo "uv: $(uv --version 2>/dev/null || echo 'Not available')"

# --- Cleanup ---

# Removes the Python virtual environment
clean_venv:
    #!/usr/bin/env bash
    if [ -d "{{VENV_NAME}}" ]; then
        echo "Removing virtual environment..."
        rm -rf "{{VENV_NAME}}"
        echo "Virtual environment removed"
    else
        echo "No virtual environment found"
    fi

# Removes Python bytecode cache files
clean_pycache:
    #!/usr/bin/env bash
    echo "Removing Python cache files..."
    find . -type f -name '*.py[co]' -delete -o -type d -name __pycache__ -delete

# Removes Docker images
clean_docker:
    #!/usr/bin/env bash
    echo "Cleaning Docker artifacts..."
    docker rmi {{DOCKER_IMAGE}}:latest 2>/dev/null || echo "No Docker image to remove"
    docker system prune -f

# Cleans up all artifacts
clean: clean_pycache
    #!/usr/bin/env bash
    echo "✅ Service cleanup complete"
