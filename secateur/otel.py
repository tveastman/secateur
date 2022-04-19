"""
OpenTelemetry Configuration
"""

#import opentelemetry
import opentelemetry.sdk.trace
import opentelemetry.sdk.trace.export
import opentelemetry.exporter.otlp.proto.grpc.trace_exporter

import opentelemetry.instrumentation.django
import opentelemetry.instrumentation.celery
import opentelemetry.instrumentation.requests
# import opentelemetry.instrumentation.psycopg2

opentelemetry.instrumentation.django.DjangoInstrumentor().instrument()
opentelemetry.instrumentation.celery.CeleryInstrumentor().instrument()
opentelemetry.instrumentation.requests.RequestsInstrumentor().instrument()

# opentelemetry.instrumentation.psycopg2.Psycopg2Instrumentor().instrument()

opentelemetry.trace.set_tracer_provider(
    opentelemetry.sdk.trace.TracerProvider()
)

# opentelemetry.trace.get_tracer_provider().add_span_processor(
#     opentelemetry.sdk.trace.export.BatchSpanProcessor(
#         opentelemetry.sdk.trace.export.ConsoleSpanExporter()
#     )
# )

opentelemetry.trace.get_tracer_provider().add_span_processor(
    opentelemetry.sdk.trace.export.BatchSpanProcessor(
        opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter()
    )
)
