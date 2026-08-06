import logging
from typing import Iterable

from app.common.config import config
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.grpc import GrpcAioInstrumentorClient, GrpcAioInstrumentorServer
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger(__name__)

_configured = False


def setup_telemetry(service_name: str | None = None) -> None:
    """
    Configure OpenTelemetry once per process.

    The app exports traces to Tempo through OTLP gRPC. Local dev keeps working even
    when Tempo is not running because the exporter batches in the background and
    does not block request handling.
    """

    global _configured
    if _configured:
        return

    if config.OTEL_SDK_DISABLED:
        _configured = True
        return

    service = service_name or config.OTEL_SERVICE_NAME
    resource = Resource.create(
        {
            SERVICE_NAME: service,
            SERVICE_VERSION: config.APP_VERSION,
            DEPLOYMENT_ENVIRONMENT: config.ENVIRONMENT,
        }
    )

    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    endpoint = config.OTEL_EXPORTER_OTLP_ENDPOINT
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=endpoint, insecure=True)
        )
    )

    if config.OTEL_CONSOLE_EXPORTER:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    DjangoInstrumentor().instrument()
    GrpcAioInstrumentorClient().instrument()
    GrpcAioInstrumentorServer().instrument()
    HTTPXClientInstrumentor().instrument()
    RequestsInstrumentor().instrument()
    RedisInstrumentor().instrument()
    Psycopg2Instrumentor().instrument()
    CeleryInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=False)

    _configured = True
    logger.info("OpenTelemetry configured for %s -> %s", service, endpoint)


def tracer(name: str):
    return trace.get_tracer(name)


def current_trace_headers() -> dict[str, str]:
    carrier: dict[str, str] = {}
    propagate.inject(carrier)
    return carrier


def context_from_metadata(metadata: Iterable[tuple[str, str]]):
    carrier = {str(key): str(value) for key, value in metadata}
    return propagate.extract(carrier)


def record_exception(span, exc: Exception) -> None:
    span.record_exception(exc)
    span.set_status(Status(StatusCode.ERROR, str(exc)))


def set_span_attributes(span, attributes: dict[str, object]) -> None:
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)


__all__ = [
    "SpanKind",
    "context_from_metadata",
    "current_trace_headers",
    "record_exception",
    "set_span_attributes",
    "setup_telemetry",
    "tracer",
]
