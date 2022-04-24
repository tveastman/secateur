"""
OpenTelemetry Configuration
"""
import os

import opentelemetry
import opentelemetry.sdk.trace
import opentelemetry.sdk.trace.export
import opentelemetry.exporter.otlp.proto.grpc.trace_exporter

import opentelemetry.instrumentation.django
import opentelemetry.instrumentation.celery
import opentelemetry.instrumentation.requests
import opentelemetry.instrumentation.psycopg2

opentelemetry.instrumentation.django.DjangoInstrumentor().instrument()
opentelemetry.instrumentation.celery.CeleryInstrumentor().instrument()
opentelemetry.instrumentation.requests.RequestsInstrumentor().instrument()
opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor().instrument()

opentelemetry.trace.set_tracer_provider(opentelemetry.sdk.trace.TracerProvider())

# opentelemetry.trace.get_tracer_provider().add_span_processor(
#     opentelemetry.sdk.trace.export.BatchSpanProcessor(
#         opentelemetry.sdk.trace.export.ConsoleSpanExporter()
#     )
# )

# if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
#     opentelemetry.trace.get_tracer_provider().add_span_processor(
#         opentelemetry.sdk.trace.export.BatchSpanProcessor(
#             opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter()
#         )
#     )

## metrics

import opentelemetry.sdk._metrics
import opentelemetry.sdk._metrics.export
import opentelemetry.exporter.otlp.proto.grpc._metric_exporter


if os.environ.get("EXPORT_METRICS"):
    metric_exporter = (
        opentelemetry.exporter.otlp.proto.grpc._metric_exporter.OTLPMetricExporter(
            endpoint="http://otel:4317",
        )
    )
else:
    metric_exporter = opentelemetry.sdk._metrics.export.ConsoleMetricExporter()

opentelemetry._metrics.set_meter_provider(
    opentelemetry.sdk._metrics.MeterProvider(
        metric_readers=[
            opentelemetry.sdk._metrics.export.PeriodicExportingMetricReader(
                metric_exporter
            ),
        ]
    )
)
meter = opentelemetry._metrics.get_meter(__name__)

homepage_counter = meter.create_counter(
    name="homepage",
    description="Incremented for every hit on the home page.",
    unit="1",
)
twitter_block_counter = meter.create_counter(
    name="twitter_block",
    unit="1",
)
twitter_unblock_counter = meter.create_counter(
    name="twitter_unblock",
    unit="1",
)
twitter_mute_counter = meter.create_counter(
    name="twitter_mute",
    unit="1",
)
twitter_unmute_counter = meter.create_counter(
    name="twitter_unmute",
    unit="1",
)
