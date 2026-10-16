# Strategy Backtester — common tasks. Run from the project root.
VENV := .venv/bin
# Own ports so this project can run next to the other QuantProjects.
API_PORT ?= 8020
WEB_PORT ?= 5190
# Optional linter (no ruff in this venv); override with RUFF=ruff if installed globally.
RUFF ?= ../06-financial-terminal/backend/.venv/bin/ruff

.PHONY: install dev api web test lint build serve streamlit

install:            ## Python venv + requirements, then the web app's node modules
	test -d .venv || python3 -m venv .venv
	$(VENV)/pip install -q --upgrade pip
	$(VENV)/pip install -q -r requirements.txt
	@if [ -f web/package.json ]; then cd web && npm install; fi

dev:                ## API on :8020 + Vite on :5190 (open http://localhost:5190)
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory api & \
	$(MAKE) --no-print-directory web & \
	wait

api:                ## FastAPI dev server with reload
	$(VENV)/fastapi dev api/main.py --port $(API_PORT)

web:                ## Vite dev server (proxies /api to :8020)
	cd web && npx vite --port $(WEB_PORT) --strictPort

test:               ## Python tests (offline); web unit tests when web/ defines a test script
	$(VENV)/python -m pytest -q
	@if [ -f web/package.json ] && grep -q '"test"[[:space:]]*:' web/package.json; then \
		cd web && npm test; \
	else \
		echo "web: no test script, skipping"; \
	fi

lint:               ## Ruff check of the API and tests (skipped if ruff is unavailable)
	@if [ -x "$(RUFF)" ] || command -v "$(RUFF)" >/dev/null 2>&1; then \
		$(RUFF) check api tests/test_api.py; \
	else \
		echo "ruff not found at $(RUFF); skipping lint"; \
	fi

build:              ## Production build of the web app (served by FastAPI from web/dist)
	cd web && npm run build

serve: build        ## Single process: API + built UI on http://localhost:8020
	$(VENV)/fastapi run api/main.py --port $(API_PORT)

streamlit:          ## The original Streamlit UI
	$(VENV)/python -m streamlit run app.py
