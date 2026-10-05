.PHONY: install test up down responder check-app check-stack deploy

install:
	uv sync --frozen

test:
	uv run --frozen pytest -q

up:
	docker compose up --build -d --wait

down:
	docker compose down

responder:
	uv run --frozen uvicorn responder:app --app-dir incident-response --host 127.0.0.1 --port 8001

check-app:
	uv run --frozen python scripts/check_app.py

check-stack:
	uv run --frozen python scripts/check_stack.py

deploy:
	uv run --frozen python scripts/deploy.py
