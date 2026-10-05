# AI usage and verification

The user requested Homework 4 in a separate GitHub repository, following the
principles of the earlier three assignments, with human-readable commit messages.
OpenAI Codex acted as the coding assistant.

The interactive assistant read the assignments and existing homework repositories,
wrote the plan and backlog, instrumented the starter, provisioned the telemetry
stack, built the responder and checked the results through tests and real HTTP.
The existing product scope was retained.

For Questions 5 and 6, the responder launched **separate real headless Codex
processes**. These were triggered by the test webhook and Grafana's firing
notification respectively. The latter agent read captured telemetry, created
regression tests, demonstrated failures, and changed the date arithmetic.
The supervising assistant reviewed the diff, ran the suite, committed the fix,
rebuilt the container and checked the formerly failing request.

The agent was not given the root cause in its incident prompt. It received the
evidence directory and instructions to investigate, reproduce, test and repair.
Its exact response and test-command output are saved under `evidence/06-incident/`.
The test agent's actual final line is saved separately for the submission form.
Raw sessions, authentication files and local runtime directories are not published.

Checks included:

- Three original tests before implementation; 21 offline tests after the fix.
- Correct metric status and trace/log correlation for 200, 404 and simulated 500.
- Durable webhook deduplication, ignored resolved alerts, invalid input,
  agent failures, interrupted jobs and partial telemetry collection.
- Requests to the deployed app and all three Grafana data source proxies.
- Grafana UI inspection and screenshots of Normal and Firing alert states.
- Regression failures before the fix, followed by successful tests and repeated
  requests after rebuilding without resetting the database.

Newly provisioned Grafana notification routing took roughly a minute to reach
the running Alertmanager. The first evaluation used the old default receiver;
no SMTP was configured. Once the new route loaded, Grafana delivered the actual
webhook successfully. The runbook records this delay. Optional preinstalled
Grafana drilldown plugins also produced a frontend compatibility error; they are
disabled, and the dashboard uses built-in panels and data sources.

References used for implementation:

- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Loki native OpenTelemetry ingestion](https://grafana.com/docs/loki/latest/send-data/otel/)
- [Tempo with an OpenTelemetry Collector](https://grafana.com/docs/tempo/latest/set-up-for-tracing/instrument-send/set-up-collector/otel-collector/)
- [Grafana alert provisioning](https://grafana.com/docs/grafana/latest/alerting/set-up/provision-alerting-resources/file-provisioning/)

Known limits are explicit in the README: this is a local demo, the webhook is
unauthenticated, the agent's file scope is prompt-enforced, deploy is supervised,
and there is no automatic rollback or production incident queue.
