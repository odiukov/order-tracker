# Homework 4: DevOps and Observability

Submission URL: **https://github.com/odiukov/order-tracker**

Answers for the [2026 assignment](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/cohorts/2026/homework/04-devops/homework.md),
verified against the local Docker stack on October 5, 2026.

| # | Answer |
| --- | --- |
| 1 | **`{"status":"ok"}`** |
| 2 | **200** |
| 3 | **404** |
| 4 | **Normal** |
| 5 | The agent acknowledged the test notification and made no changes. Exact response below. |
| 6 | **The express delivery date calculation tried to use a day that does not exist in that month.** |

## 1. Health check

Started the starter with `docker compose up --build -d --wait`, then requested
`GET /healthz`. The body was `{"status":"ok"}`. The three original tests passed.

Evidence: [health response](evidence/01-health.json).

## 2. Console telemetry

Added OpenTelemetry metrics, logs and traces, rebuilt the app with the console
exporter and requested `GET /api/orders/standard-1001`. Both HTTP and the request
counter recorded **200**, with `http.route=/api/orders/{order_id}`.

Evidence: [HTTP response](evidence/02-lookup.http),
[actual console metric, log and span](evidence/02-console.json).

## 3. Grafana telemetry

The assignment asks for `standard-1002`. That order does not exist in the seed
data: the ID ending in 1002 is `express-1002`. The missing-order request therefore
returns **404**. The response, Loki log and Tempo trace share trace ID
`b00939dc7b9e9fd8f3df106cc899c77b`.

The verification script queried all three backends through Grafana's data source
proxy. It found a 404 counter sample, the correlated log and the trace with
HTTP status 404.

Evidence: [Grafana data source responses](evidence/03-grafana-signals.json).

## 4. Alert state

Repeated `GET /api/orders/standard-1002`, then waited for evaluation. The rule's
health was `ok`, the instance state was **Normal**, and the API rule state was
`inactive`. A 404 is not a server error and does not trigger the 5xx rule.

Evidence: [request](evidence/04-lookup.http),
[Grafana rule state](evidence/04-alert-normal.json),
[Grafana screenshot](evidence/04-alert-normal.png).

## 5. Automatic responder

Sent the exact test notification from the assignment to `POST /alerts` on port
8001. The responder saved the webhook and telemetry, launched a real `codex exec`
process with a read-only sandbox, and saved its final response:

> Acknowledged. Reviewed the evidence in `.incidents/d5b3f803283b701d620d`: this is a test notification with no incident to fix. No files were modified.

That response is one line, so **the entire quotation above is also its last line**.
It was read from the agent's output file, not generated as a placeholder.

Evidence: [webhook](evidence/05-test-notification/alert.json),
[completed status](evidence/05-test-notification/status.json),
[unaltered agent response](evidence/05-test-notification/response.txt).

## 6. Real incident and repair

Connected Grafana's contact point to the responder and requested
`GET /api/orders/express-1002`. It returned **500**. Grafana changed to **Firing**
and sent a real webhook with receiver `incident-responder`; the service created
incident `37832860a71fd98fd938` and automatically started Codex.

The log and trace contained `ValueError: day is out of range for month` in
`order_detail`. The seed order was placed on September 30. This code tried to
construct September 32:

```python
estimated_at = placed_at.replace(day=placed_at.day + 2)
```

The agent added regression tests, observed five failures before the repair,
then replaced the calculation with calendar-aware date arithmetic:

```python
estimated_at = placed_at + timedelta(days=2)
```

The complete suite passed **21 tests**. Coverage includes month and year
boundaries, leap and non-leap Februaries, ordinary express dates and unchanged
standard-order behavior. Two deprecation warnings come from the installed
FastAPI/Starlette test-client dependencies.

After reviewing and committing the fix, the deployment script ran the tests,
built image `order-tracker:21f18e6-20261005180718`, waited for the app and performed
ten successful express lookups. The same stored order returned **200** with
`estimated_delivery=2026-10-02`. A second HTTP check also passed ten lookups;
Grafana reported Normal again. The database was not reset.

Evidence:

- [Original HTTP 500](evidence/06-before.http)
- [Firing rule state](evidence/06-alert-firing.json) and [screenshot](evidence/06-alert-firing.png)
- [Actual Grafana webhook](evidence/06-incident/alert.json)
- [Exception logs](evidence/06-incident/logs.json) and [incident telemetry files](evidence/06-incident/)
- [Agent's final explanation](evidence/06-incident/response.txt)
- [Failing and passing regression runs](evidence/06-incident/regression-checks.txt)
- [Rebuilt app's HTTP 200](evidence/06-after.http), [HTTP verification](evidence/06-recovery.json), [recovered alert](evidence/06-alert-recovered.json)

## Reproduction and history

GitHub CI passed both jobs (offline tests and the real Compose stack):
[run 37353715624](https://github.com/odiukov/order-tracker/actions/runs/37353715624).
The run details are saved in [07-ci.json](evidence/07-ci.json).
The [dashboard screenshot](evidence/07-dashboard.png) shows successful requests
after recovery and zero recent server errors.

See [README.md](README.md) for installation, verification and responder commands.
The history separates planning, console telemetry, storage, alerting, responder,
webhook connection and the agent's fix. The commit immediately before
`21f18e6` is `ceac5cf`; it contains the original bug and the complete responder/alert setup.
Run that version only in a separate checkout with the existing stack stopped;
it intentionally reproduces a broken app.

The same principles as Homeworks 1–3 were used: specification first, a small
backlog, tests of real behavior, focused commits, reproducible Docker deployment
and no deployment on failed tests.
