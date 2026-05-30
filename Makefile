# ============================================================================
# Motifold Makefile
#
# All targets are thin wrappers around `docker compose`. The help output is
# generated automatically from `##` comments next to each target — to add a
# new command, just add a target with a `## description` annotation.
#
# Common variables:
#   TAG=<tag>      Image tag used for motifold-{backend,frontend} (default: latest)
#   SERVICE=<svc>  Target a specific service for `logs`, `shell`, `restart`, etc.
#   FORCE=1        Skip the interactive confirmation prompt on destructive targets
# ============================================================================

# Show `help` when `make` is run with no arguments.
.DEFAULT_GOAL := help

# Tag applied to locally built images (motifold-backend, motifold-frontend, ...).
# Override via `make up TAG=v1.0`.
TAG ?= latest
export MOTIFOLD_TAG := $(TAG)

# Default service selector for the `*-one` family of targets.
SERVICE ?=

# Make sure BuildKit is enabled even on older docker daemons, so the
# `--mount=type=cache` and `# syntax=docker/dockerfile:1` directives in our
# Dockerfiles work.
DOCKER_ENV := DOCKER_BUILDKIT=1 COMPOSE_DOCKER_CLI_BUILD=1

COMPOSE      := $(DOCKER_ENV) docker compose -f compose.yaml
DEV_COMPOSE  := $(DOCKER_ENV) docker compose -f compose.yaml -f compose.dev.yaml

# All `up` invocations should sweep stale containers from previous configs.
UP_FLAGS := --build -d --remove-orphans

.PHONY: help \
        up start down restart logs ps build rebuild pull \
        dev dev-up dev-down dev-restart dev-logs dev-ps dev-build \
        migrate test shell api-shell celery-shell psql redis-cli exec \
        clean dev-clean clean-images nuke

# ============================================================================
##@ Help
# ============================================================================

help: ## Show this help message
	@awk 'BEGIN { \
	        FS = ":.*?## "; \
	        printf "\n\033[1mUsage:\033[0m make \033[36m<target>\033[0m [VAR=value ...]\n"; \
	      } \
	      /^##@ / { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } \
	      /^[a-zA-Z_-]+:.*?## / { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 } \
	     ' $(MAKEFILE_LIST)
	@printf "\n\033[1mCommon variables:\033[0m\n"
	@printf "  TAG=<tag>      Image tag (current: \033[33m$(TAG)\033[0m)\n"
	@printf "  SERVICE=<svc>  Target service for logs/shell/restart\n"
	@printf "  FORCE=1        Skip confirmation on destructive targets\n\n"

# ============================================================================
##@ Production (built images)
# ============================================================================

up: ## Build and start the prod stack in the background
	$(COMPOSE) up $(UP_FLAGS)

start: ## Start the prod stack without rebuilding (uses existing images)
	$(COMPOSE) up -d --remove-orphans

down: ## Stop the prod stack (keep volumes)
	$(COMPOSE) down --remove-orphans

restart: ## Restart a service: make restart SERVICE=api
	@test -n "$(SERVICE)" || (echo "Usage: make restart SERVICE=<name>" && exit 1)
	$(COMPOSE) restart $(SERVICE)

logs: ## Tail logs (all services, or SERVICE=<name>)
	$(COMPOSE) logs -f $(SERVICE)

ps: ## Show prod service status
	$(COMPOSE) ps

build: ## Incremental rebuild of prod images (uses cache)
	$(COMPOSE) build

rebuild: ## Force a full rebuild from scratch (--no-cache --pull)
	$(COMPOSE) build --no-cache --pull

pull: ## Pull the external images (postgres, redis, ...) only
	$(COMPOSE) pull postgres redis

# ============================================================================
##@ Development (source-mounted, hot reload)
# ============================================================================

dev: ## Build and start the dev stack in the background
	@mkdir -p backend/logs backend/.venv
	$(DEV_COMPOSE) up $(UP_FLAGS)

dev-up: dev  ## Alias for `dev`

dev-down: ## Stop the dev stack (keep volumes)
	$(DEV_COMPOSE) down --remove-orphans

dev-restart: ## Restart a dev service: make dev-restart SERVICE=api
	@test -n "$(SERVICE)" || (echo "Usage: make dev-restart SERVICE=<name>" && exit 1)
	$(DEV_COMPOSE) restart $(SERVICE)

dev-logs: ## Tail dev logs (all, or SERVICE=<name>)
	$(DEV_COMPOSE) logs -f $(SERVICE)

dev-ps: ## Show dev service status
	$(DEV_COMPOSE) ps

dev-build: ## Incremental rebuild of dev images (uses cache)
	$(DEV_COMPOSE) build

# ============================================================================
##@ Operations (run-time helpers)
# ============================================================================

migrate: ## Apply pending Alembic migrations (idempotent)
	$(COMPOSE) run --rm db-migration

test: ## Run pytest inside a one-off dev backend container
	$(DEV_COMPOSE) run --rm api pytest

shell: ## Open bash in a running service: make shell SERVICE=api
	@test -n "$(SERVICE)" || (echo "Usage: make shell SERVICE=<name>" && exit 1)
	$(COMPOSE) exec $(SERVICE) bash

api-shell: ## Bash shell inside the running api container
	$(COMPOSE) exec api bash

celery-shell: ## Bash shell inside the running celery container
	$(COMPOSE) exec celery bash

psql: ## Open psql against the running postgres
	$(COMPOSE) exec postgres psql -U user -d motifold

redis-cli: ## Open redis-cli against the running redis
	$(COMPOSE) exec redis redis-cli

exec: ## Run an ad-hoc command: make exec SERVICE=api CMD="python -c 'print(1)'"
	@test -n "$(SERVICE)" || (echo "Usage: make exec SERVICE=<name> CMD='<command>'" && exit 1)
	@test -n "$(CMD)" || (echo "Usage: make exec SERVICE=<name> CMD='<command>'" && exit 1)
	$(COMPOSE) exec $(SERVICE) sh -c "$(CMD)"

# ============================================================================
##@ Cleanup (destructive — require FORCE=1 or interactive confirmation)
# ============================================================================

# Helper macro: emit a red warning and read one line of input.
# Aborts the recipe unless the user types `y` / `Y`, or `FORCE=1` is set.
define _confirm
	@if [ "$(FORCE)" != "1" ]; then \
	    printf "\033[31m%s\033[0m\nContinue? [y/N] " "$(1)"; \
	    read ans; \
	    case "$$ans" in y|Y|yes|YES) ;; *) echo "Aborted." ; exit 1 ;; esac; \
	fi
endef

clean: ## ⚠️  Stop prod and DELETE all data volumes
	$(call _confirm,⚠️  This will DELETE postgres + redis volumes for the prod stack.)
	$(COMPOSE) down -v --remove-orphans

dev-clean: ## ⚠️  Stop dev and DELETE all data volumes (incl. backend_venv, node_modules)
	$(call _confirm,⚠️  This will DELETE all dev volumes (postgres/redis/venv/node_modules).)
	$(DEV_COMPOSE) down -v --remove-orphans

clean-images: ## Remove locally built motifold-* images
	$(call _confirm,Remove all locally built motifold-* images.)
	-docker images --format '{{.Repository}}:{{.Tag}}' \
	  | grep '^motifold-' \
	  | xargs -r docker rmi -f
	docker builder prune -f

nuke: ## ☠️  WARNING: host-wide docker prune (affects OTHER projects too)
	@printf '\033[31m☠️  This affects ALL projects on this host. Type "nuke" to confirm: \033[0m'; \
	  read ans; \
	  [ "$$ans" = "nuke" ] || (echo "Aborted." && exit 1)
	docker system prune -a --volumes -f
