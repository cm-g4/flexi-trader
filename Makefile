.PHONY: help install test coverage lint format clean db-up db-down docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run all tests"
	@echo "  make test-fast     - Run tests without coverage"
	@echo "  make coverage      - Run tests with coverage report"
	@echo "  make lint          - Run linting checks"
	@echo "  make format        - Format code with black and isort"
	@echo "  make clean         - Clean cache and temp files"
	@echo "  make db-up         - Start database services (docker-compose)"
	@echo "  make db-down       - Stop database services"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make run           - Run the application locally"

install:
	pip install -r requirements.txt

test:
	pytest -v --cov=app --cov-report=term-missing tests/

test-fast:
	pytest -v tests/

coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing tests/
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	flake8 app/ tests/
	mypy app/

format:
	black app/ tests/
	isort app/ tests/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf htmlcov/
	rm -rf .coverage

db-up:
	docker-compose up -d

db-down:
	docker-compose down

db-logs:
	docker-compose logs -f

docker-build:
	docker build -t trading-bot:latest .

docker-run:
	docker run --env-file .env trading-bot:latest

run:
	python main.py

dev-setup: install db-up
	@echo "Development environment setup complete!"
	@echo "Database is running on localhost:5432"
	@echo "Next: Configure .env file and run 'make run'"

dev-clean: clean
	docker-compose down
	@echo "Development environment cleaned up"