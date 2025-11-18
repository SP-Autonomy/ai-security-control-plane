# AI Security Control Plane - Makefile

# Force use of bash instead of sh
SHELL := /bin/bash

.PHONY: help install dev init health test clean

# Default target
.DEFAULT_GOAL := help

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

## help: Show this help
help:
	@echo "$(BLUE)AI Security Control Plane - Available Commands$(NC)"
	@echo ""
	@grep -E '^## ' Makefile | sed 's/## /  $(GREEN)/' | sed 's/:/ $(NC)-/'

## install: Install all dependencies
install:
	@echo "$(BLUE)Installing dependencies...$(NC)"
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

## init: Initialize database and policies
init:
	@echo "$(BLUE)Initializing control plane...$(NC)"
	python -m control_plane.api.init_db
	python -m control_plane.policy.load_bundles
	@echo "$(GREEN)✓ Control plane initialized$(NC)"

## setup: Complete first-time setup
setup: install init
	@echo "$(GREEN)✓ Setup complete! Run 'make dev' to start$(NC)"

## dev: Start all services
dev:
	@echo "$(BLUE)Starting AI Security Control Plane...$(NC)"
	@trap 'kill 0' INT; \
	python -m control_plane.api.main & \
	python -m gateway.app & \
	streamlit run ui/dashboard.py & \
	wait

## dev-api: Start control plane API only
dev-api:
	@echo "$(BLUE)Starting Control Plane API...$(NC)"
	python -m control_plane.api.main

## dev-gateway: Start gateway only
dev-gateway:
	@echo "$(BLUE)Starting Gateway...$(NC)"
	python -m gateway.app

## dev-ui: Start dashboard only
dev-ui:
	@echo "$(BLUE)Starting Dashboard...$(NC)"
	streamlit run ui/dashboard.py

## db-init: Initialize database
db-init:
	@echo "$(BLUE)Initializing database...$(NC)"
	python -m control_plane.api.init_db
	@echo "$(GREEN)✓ Database initialized$(NC)"

## db-reset: Reset database (WARNING: deletes all data)
db-reset:
	@echo "$(YELLOW)⚠ WARNING: This will delete all data!$(NC)"
	@echo -n "Are you sure? [y/N] " && read ans && [ $${ans:-N} = y ]
	@rm -f control_plane.db
	@python -m control_plane.api.init_db
	@echo "$(GREEN)✓ Database reset$(NC)"

## policy-load: Load policy bundles
policy-load:
	@echo "$(BLUE)Loading policy bundles...$(NC)"
	python -m control_plane.policy.load_bundles
	@echo "$(GREEN)✓ Policies loaded$(NC)"

## posture-compute: Calculate posture scores
posture-compute:
	@echo "$(BLUE)Computing posture scores...$(NC)"
	python -m control_plane.scoring.compute
	@echo "$(GREEN)✓ Posture scores computed$(NC)"

## eval-run: Run security evaluations
eval-run:
	@echo "$(BLUE)Running security evaluations...$(NC)"
	python -m evals.run_suite --suite all --compare
	@echo "$(GREEN)✓ Evaluations complete$(NC)"

## test: Run unit tests
test:
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✓ Tests passed$(NC)"

## coverage: Generate coverage report
coverage:
	@echo "$(BLUE)Generating coverage...$(NC)"
	pytest --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report: htmlcov/index.html$(NC)"

## health: Check service health
health:
	@echo "$(BLUE)Checking health...$(NC)"
	@curl -sf http://localhost:8000/health && echo "$(GREEN)✓ Control Plane$(NC)" || echo "$(YELLOW)✗ Control Plane$(NC)"
	@curl -sf http://localhost:8001/health && echo "$(GREEN)✓ Gateway$(NC)" || echo "$(YELLOW)✗ Gateway$(NC)"

## clean: Remove generated files
clean:
	@echo "$(BLUE)Cleaning up...$(NC)"
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

## clean-db: Remove database only
clean-db:
	@echo "$(YELLOW)⚠ Removing database...$(NC)"
	@rm -f control_plane.db
	@echo "$(GREEN)✓ Database removed$(NC)"

## demo: Run demo workflow
demo:
	@echo "$(BLUE)Running demo...$(NC)"
	python examples/demo_workflow.py
	@echo "$(GREEN)✓ Demo complete$(NC)"