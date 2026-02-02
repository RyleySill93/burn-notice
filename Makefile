.PHONY: frontend install build clean help requirements backend setup-db

# Default target
default: help

# Run development server
frontend:
	@echo "Starting frontend development server..."
	cd frontend && npm run dev

# Install dependencies
install:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Build for production
build:
	@echo "Building frontend for production..."
	cd frontend && npm run build

# Clean node_modules and dist
clean:
	@echo "Cleaning frontend build and dependencies..."
	rm -rf frontend/node_modules frontend/dist

# Run both install and frontend
setup: install frontend

# Generate TypeScript types from backend API
generate:
	@echo "Generating TypeScript types from API..."
	cd frontend && npm run generate

# Backend commands
requirements:
	@echo "Installing backend Python dependencies..."
	cd backend && pip install -r requirements.txt

backend:
	@echo "Starting FastAPI backend server..."
	cd backend && PYTHONBREAKPOINT="pdbr.set_trace" uvicorn src.network.http.server:server --reload --port 8000

setup-db:
	@echo "Setting up PostgreSQL database..."
	cd backend && bash management/setup_db.sh

reset-db:
	python backend/management/reset_db.py
	make migrate
	echo "database has been reset"

reset-test-db:
	@echo "Resetting test database..."
	dropdb burn_notice-test || true
	createdb -O burn_notice -E UTF8 -T template1 burn_notice-test
	psql -d burn_notice-test -c "ALTER DATABASE \"burn_notice-test\" SET timezone TO 'UTC';"
	DB_NAME=burn_notice-test make migrate
	@echo "Test database has been reset"

shell:
	@echo "Starting interactive Python shell..."
	cd backend && PYTHONBREAKPOINT="pdbr.set_trace" python management/shell.py

migrations:
	cd backend && alembic revision --autogenerate -m '$(m)'

upgrade-db:
	@echo "Running database migrations..."
	cd backend && alembic upgrade head

migrate: upgrade-db

downgrade-db:
	@echo "Rolling back last migration..."
	cd backend && alembic downgrade -1

migration-history:
	@echo "Showing migration history..."
	cd backend && alembic history

# Redis & Queue commands
redis:
	@echo "Starting Redis server..."
	redis-server

worker:
	@echo "Starting Dramatiq worker..."
	cd backend && PYTHONBREAKPOINT="pdbr.set_trace" dramatiq src.network.queue.worker -v --threads=2

worker-prod:
	@echo "Starting Dramatiq worker (production)..."
	cd backend && dramatiq src.network.queue.worker --processes 4

redis-shell:
	@echo "Opening Redis CLI..."
	redis-cli

clear-cache:
	@echo "Clearing Redis cache (careful!)..."
	redis-cli FLUSHDB

# Linting functions
lint-backend:
	cd backend && ruff check --fix

format-backend:
	cd backend && ruff format

type-check:
	cd backend && mypy

clean-backend:
	make lint-backend && make format-backend && make type-check

# Frontend linting and formatting
lint-frontend:
	cd frontend && npm run lint

lint-frontend-fix:
	cd frontend && npm run lint:fix

format-frontend:
	cd frontend && npm run format

format-frontend-check:
	cd frontend && npm run format:check

check-frontend:
	cd frontend && npm run check

clean-frontend:
	make format-frontend && make lint-frontend-fix

# Lint and format everything
lint: lint-backend lint-frontend

format: format-backend format-frontend

clean-all: clean-backend clean-frontend

# Development servers (run in parallel)
dev-all:
	@echo "Starting all development servers..."
	@echo "Run these commands in separate terminals:"
	@echo "  1. make redis"
	@echo "  2. make backend"
	@echo "  3. make worker"
	@echo "  4. make frontend"

# Help command
help:
	@echo "Available commands:"
	@echo "  Frontend:"
	@echo "    make frontend        - Start the frontend development server"
	@echo "    make install         - Install frontend dependencies"
	@echo "    make build           - Build frontend for production"
	@echo "    make clean           - Remove node_modules and dist folders"
	@echo "    make setup           - Install dependencies and start frontend server"
	@echo "    make generate        - Generate TypeScript types from API"
	@echo "  Backend:"
	@echo "    make requirements    - Install backend Python dependencies"
	@echo "    make backend         - Run the FastAPI backend server (with pdbr debugger)"
	@echo "    make shell           - Start interactive Python shell with models loaded"
	@echo "    make setup-db        - Create PostgreSQL database and run migrations"
	@echo "    make reset-db        - Reset the database (drops and recreates schema)"
	@echo "    make reset-test-db   - Reset the test database"
	@echo "    make migrations m='message' - Create new Alembic migration"
	@echo "    make upgrade-db      - Apply pending migrations"
	@echo "    make downgrade-db    - Roll back last migration"
	@echo "    make migration-history - Show migration history"
	@echo "  Redis & Queue:"
	@echo "    make redis           - Start Redis server"
	@echo "    make worker          - Start Dramatiq worker (development)"
	@echo "    make worker-prod     - Start Dramatiq worker (production)"
	@echo "    make redis-shell     - Open Redis CLI"
	@echo "    make clear-cache     - Clear Redis cache (careful!)"
	@echo "  Linting & Formatting:"
	@echo "    Backend:"
	@echo "      make lint-backend    - Run Ruff linter with auto-fix"
	@echo "      make format-backend  - Format code with Ruff"
	@echo "      make type-check      - Run mypy type checker"
	@echo "      make clean-backend   - Run lint, format, and type check"
	@echo "    Frontend:"
	@echo "      make lint-frontend   - Run ESLint"
	@echo "      make lint-frontend-fix - Run ESLint with auto-fix"
	@echo "      make format-frontend - Format with Prettier"
	@echo "      make format-frontend-check - Check Prettier formatting"
	@echo "      make check-frontend  - Run Prettier check and ESLint"
	@echo "      make clean-frontend  - Format and lint with fixes"
	@echo "    All:"
	@echo "      make lint            - Lint both backend and frontend"
	@echo "      make format          - Format both backend and frontend"
	@echo "      make clean-all       - Clean both backend and frontend"
	@echo "  Development:"
	@echo "    make dev-all         - Instructions to run all services"
	@echo "  General:"
	@echo "    make help            - Show this help message"

# Test functions
test-unit:
	pytest backend/tests/unit

test-unit-dev:
	pytest backend/tests/unit --pdb --pdbcls=pdbr:RichPdb

test-api:
	DB_NAME=burn_notice-test make migrate && pytest backend/tests/api

test-api-fast:
	DB_NAME=burn_notice-test pytest backend/tests/api

test-integration:
	DB_NAME=burn_notice-test make migrate && pytest backend/tests/integration

test-integration-fast:
	DB_NAME=burn_notice-test pytest backend/tests/integration

test:
	make test-unit && make test-api && make test-integration

test-fast:
	make test-unit && make test-api-fast && make test-integration-fast
