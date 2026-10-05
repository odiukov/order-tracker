# Order Tracker: Homework 4 plan

## Scope

Extend the [Order Tracker starter](https://github.com/alexeygrigorev/order-tracker)
for [Homework 4](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/cohorts/2026/homework/04-devops/homework.md).
Keep its FastAPI API, single-page UI and SQLite database.

1. Record order lookup metrics, structured logs and correlated traces with OpenTelemetry.
2. Route all three signals through a Collector into Prometheus, Loki and Tempo, with a provisioned Grafana dashboard.
3. Alert on recent server errors and collect evidence when Grafana calls the responder.
4. Launch a headless coding agent, verify its fix with regression tests, rebuild and confirm recovery.

## Boundaries

The stack runs locally with Docker Compose. Public cloud deployment, Kubernetes,
new product features and a UI redesign are outside this assignment. Services bind
published ports to loopback. The responder runs on the host to use the installed
Codex login; credentials are never mounted into application containers.

The responder stores alerts and bounded telemetry snapshots in an incident
directory. It ignores resolved alerts and deduplicates repeated firing alerts.
Only one repair agent runs at a time. Test alerts run without source edits.
Real incidents allow application and test changes; deployment remains a separate,
test-gated step. Agent failures and telemetry failures are recorded explicitly.

## Acceptance criteria

- The original tests pass and `/healthz` answers successfully in Docker.
- `standard-1001` has a console metric carrying its actual HTTP status.
- `standard-1002` has a metric, log and trace queryable through Grafana's data sources.
- A 5xx rule includes endpoint, window and dashboard link; no errors means Normal.
- `POST /alerts` on port 8001 persists evidence and automatically launches Codex.
- The Q5 answer quotes the real completed agent response.
- An express lookup triggers a real Grafana webhook, the agent repairs the incident,
  and tests plus a rebuilt app verify the same lookup succeeds.
- The repository includes configuration, reviewed evidence, fix, reproducible commands
  and `HOMEWORK.md` with answers supported by actual observations.

