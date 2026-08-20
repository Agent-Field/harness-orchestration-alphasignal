# blast-radius -- companion repo for the AgentField webinar.
#
# Python 3.13 ONLY.  agentfield 0.1.132 declares >=3.10,<3.14, so a system
# python3.14 resolves to *no* installable version.  Every target below goes
# through .venv, which `make setup` pins to 3.13.

SHELL       := /bin/bash
UV          ?= $(shell command -v uv 2>/dev/null || echo $(HOME)/.af/portfolio/bin/uv)
PY313       ?= $(shell command -v python3.13 2>/dev/null || echo /opt/homebrew/bin/python3.13)
VENV        := .venv
PY          := $(VENV)/bin/python
PIP_ENV     := VIRTUAL_ENV=$(CURDIR)/$(VENV)
SERVER      ?= http://localhost:8080
NODE_DIR    := node
NODE_MAIN   := $(NODE_DIR)/main.py
RUN_DIR     := .run
TRACE_DIR   := traces
NODE_PORT   ?= 8001

.DEFAULT_GOAL := help
.PHONY: help setup up down demo check traces notebooks check-outputs test clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[1m%-10s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup ----
setup: $(VENV)/.stamp ## Create the 3.13 venv and install requirements
$(VENV)/.stamp: requirements.txt
	@test -x "$(UV)" || { echo "!! uv not found. Set UV=/path/to/uv"; exit 1; }
	@test -x "$(PY313)" || { echo "!! python3.13 not found. Set PY313=/path/to/python3.13"; exit 1; }
	$(UV) venv --python $(PY313) $(VENV)
	$(PIP_ENV) $(UV) pip install -r requirements.txt
	@$(PY) -c 'import sys; assert sys.version_info[:2]==(3,13), sys.version; print("venv python", sys.version.split()[0])'
	@touch $@
	@test -f .env || { cp .env.example .env; echo ">> wrote .env from .env.example -- add your OPENROUTER_API_KEY"; }

# ------------------------------------------------------------------- up ----
up: setup ## Start the control plane and the agent node
	@mkdir -p $(RUN_DIR)
	@if curl -sf -m 3 $(SERVER)/health >/dev/null 2>&1; then \
	  echo ">> control plane already up at $(SERVER)"; \
	else \
	  echo ">> starting control plane"; \
	  ( af server >$(RUN_DIR)/control-plane.log 2>&1 & echo $$! > $(RUN_DIR)/control-plane.pid ); \
	  for i in $$(seq 1 40); do \
	    curl -sf -m 2 $(SERVER)/health >/dev/null 2>&1 && break; sleep 0.5; \
	  done; \
	  curl -sf -m 2 $(SERVER)/health >/dev/null 2>&1 \
	    || { echo "!! control plane did not come up; see $(RUN_DIR)/control-plane.log"; exit 1; }; \
	  echo ">> control plane healthy"; \
	fi
	@if [ -f $(NODE_MAIN) ]; then \
	  if [ -f $(RUN_DIR)/node.pid ] && kill -0 $$(cat $(RUN_DIR)/node.pid) 2>/dev/null; then \
	    echo ">> node already running (pid $$(cat $(RUN_DIR)/node.pid))"; \
	  else \
	    echo ">> starting node"; \
	    ( set -a; [ -f .env ] && . ./.env; set +a; \
	      $(CURDIR)/$(PY) $(NODE_MAIN) >$(RUN_DIR)/node.log 2>&1 & echo $$! > $(RUN_DIR)/node.pid ); \
	    sleep 2; echo ">> node started (pid $$(cat $(RUN_DIR)/node.pid)); logs: $(RUN_DIR)/node.log"; \
	  fi; \
	else \
	  echo ">> NOTE: $(NODE_MAIN) does not exist yet -- control plane only."; \
	fi

# ----------------------------------------------------------------- down ----
down: ## Stop the node (and the control plane if we started it)
	@for p in node control-plane; do \
	  if [ -f $(RUN_DIR)/$$p.pid ]; then \
	    pid=$$(cat $(RUN_DIR)/$$p.pid); \
	    kill $$pid 2>/dev/null && echo ">> stopped $$p (pid $$pid)" || echo ">> $$p not running"; \
	    rm -f $(RUN_DIR)/$$p.pid; \
	  fi; \
	done
	@echo ">> down. (an `af service`-managed control plane is left alone on purpose)"

# ----------------------------------------------------------------- demo ----
demo: up ## setup + up + open JupyterLab on the notebooks
	$(PY) -m jupyterlab --notebook-dir=notebooks

# ---------------------------------------------------------------- check ----
check: setup ## Verify python, SDK, control plane, and lib/dag.py import
	@echo "-- python"
	@$(PY) -c 'import sys; v=sys.version_info; print(f"   {v.major}.{v.minor}.{v.micro}"); \
	  sys.exit(0 if v[:2]==(3,13) else "!! expected 3.13")'
	@echo "-- agentfield"
	@$(PY) -c 'import agentfield as a; print("  ", a.__version__)'
	@echo "-- control plane"
	@curl -sf -m 5 $(SERVER)/health >/dev/null \
	  && echo "   healthy at $(SERVER)" \
	  || { echo "   NOT reachable at $(SERVER) -- run 'make up'"; exit 1; }
	@echo "-- lib/dag.py"
	@$(PY) -c 'import sys; sys.path.insert(0,"lib"); import dag; print("   ok, endpoint", dag.RUN_ENDPOINT)'
	@echo "-- registered nodes"
	@$(PY) lib/dag.py
	@echo "-- notebook outputs"
	@$(PY) lib/notebooks.py check | sed 's/^/   /'
	@echo "OK"

# ------------------------------------------------------------ notebooks ----
# Notebooks are committed WITH their outputs on purpose: most people meet this
# repo by scrolling it on GitHub, and GitHub renders saved outputs. An
# unexecuted notebook is a blank page to them. Run this before every commit
# that touches a notebook or anything a notebook renders.
notebooks: setup ## Execute every notebook in place and save its outputs
	$(PY) lib/notebooks.py run

check-outputs: setup ## Fail if any notebook is committed without its outputs
	$(PY) lib/notebooks.py check

test: setup ## Run the meter's self-checks
	PYTHONPATH=$(CURDIR) $(PY) meter/test_meter.py

traces: ## Export a self-contained HTML trace per run id in RUNS="id1 id2"
	@mkdir -p $(TRACE_DIR)
	@test -n "$(RUNS)" || { echo "usage: make traces RUNS=\"<run_id> ...\""; exit 1; }
	@for r in $(RUNS); do \
	  echo ">> af share $$r"; \
	  af share $$r -o $(TRACE_DIR)/$$r.html || echo "!! failed for $$r"; \
	done
	@ls -la $(TRACE_DIR)

clean: ## Remove venv, run artifacts, notebook checkpoints
	# NOTE: never strips notebook outputs -- they are committed on purpose.
	rm -rf $(VENV) $(RUN_DIR) .ipynb_checkpoints notebooks/.ipynb_checkpoints
