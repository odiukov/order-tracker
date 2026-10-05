"""Lookup telemetry with the same instruments for console and OTLP export."""

import os
import traceback
from time import perf_counter

from opentelemetry._logs import SeverityNumber
from opentelemetry.propagate import extract
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

ROUTE = "/api/orders/{order_id}"


class Telemetry:
    def __init__(self, readers, span_processors, log_processors):
        resource = Resource.create({"service.name": "order-tracker"})
        self.traces = TracerProvider(resource=resource)
        for processor in span_processors:
            self.traces.add_span_processor(processor)
        self.logs = LoggerProvider(resource=resource)
        for processor in log_processors:
            self.logs.add_log_record_processor(processor)
        self.metrics = MeterProvider(resource=resource, metric_readers=readers)
        self.tracer = self.traces.get_tracer(__name__)
        self.logger = self.logs.get_logger(__name__)
        meter = self.metrics.get_meter(__name__)
        self.requests = meter.create_counter("http.server.requests", description="Order lookup requests")
        self.duration = meter.create_histogram("http.server.duration", unit="s")
        # Establish a baseline so a single first 5xx is visible to increase().
        for status in (200, 404, 500):
            self.requests.add(0, self.attributes(status))

    @staticmethod
    def attributes(status):
        return {"http.route": ROUTE, "http.request.method": "GET", "http.response.status_code": status}

    def shutdown(self):
        self.traces.shutdown()
        self.logs.shutdown()
        self.metrics.shutdown()


def make_telemetry():
    mode = os.getenv("TELEMETRY_EXPORTER", "none")
    if mode == "none":
        return None
    if mode == "console":
        metric_exporter = ConsoleMetricExporter()
        span_exporter = ConsoleSpanExporter()
        log_exporter = ConsoleLogRecordExporter()
    elif mode == "otlp":
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter

        metric_exporter = OTLPMetricExporter()
        span_exporter = OTLPSpanExporter()
        log_exporter = OTLPLogExporter()
    else:
        raise ValueError(f"Unknown TELEMETRY_EXPORTER: {mode}")
    return Telemetry(
        [PeriodicExportingMetricReader(metric_exporter, export_interval_millis=3000)],
        [BatchSpanProcessor(span_exporter, schedule_delay_millis=1000)],
        [BatchLogRecordProcessor(log_exporter, schedule_delay_millis=1000)],
    )


class LookupTelemetry:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        telemetry = getattr(scope.get("app").state, "telemetry", None) if scope.get("app") else None
        if (scope["type"] != "http" or scope["method"] != "GET" or telemetry is None
                or not path.startswith("/api/orders/") or len(path.split("/")) != 4):
            return await self.app(scope, receive, send)

        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        started = perf_counter()
        status = 500
        failure = None
        with telemetry.tracer.start_as_current_span(
            f"GET {ROUTE}", context=extract(headers), kind=SpanKind.SERVER,
            record_exception=False, set_status_on_exception=False,
        ) as span:
            async def tracked_send(message):
                nonlocal status
                if message["type"] == "http.response.start":
                    status = message["status"]
                    message["headers"] = list(message.get("headers", [])) + [
                        (b"x-trace-id", f"{span.get_span_context().trace_id:032x}".encode())
                    ]
                await send(message)

            try:
                await self.app(scope, receive, tracked_send)
            except Exception as exc:
                failure = exc
                span.record_exception(exc)
                raise
            finally:
                attrs = telemetry.attributes(status)
                span.set_attributes(attrs)
                span.set_attribute("url.path", path)
                if status >= 500:
                    span.set_status(Status(StatusCode.ERROR, str(failure) if failure else "Server error"))
                telemetry.requests.add(1, attrs)
                telemetry.duration.record(perf_counter() - started, attrs)
                log_attrs = {**attrs, "url.path": path}
                if failure:
                    log_attrs.update({"exception.type": type(failure).__name__,
                                      "exception.message": str(failure),
                                      "exception.stacktrace": "".join(traceback.format_exception(failure))})
                telemetry.logger.emit(
                    body="Order lookup failed" if status >= 500 else "Order lookup completed",
                    severity_number=SeverityNumber.ERROR if status >= 500 else SeverityNumber.INFO,
                    severity_text="ERROR" if status >= 500 else "INFO", attributes=log_attrs,
                )
