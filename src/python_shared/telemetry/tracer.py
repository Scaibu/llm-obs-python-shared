import os
from typing import Optional, Any, Iterator, Dict
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode, Span
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
except ImportError:
    trace = None
    Status = None
    StatusCode = None
    Span = None
    TracerProvider = None
    BatchSpanProcessor = None
    ConsoleSpanExporter = None
    Resource = None
    SERVICE_NAME = None

def setup_telemetry(service_name: str, otlp_endpoint: Optional[str] = None) -> None:
    if not trace or not TracerProvider or not Resource or not SERVICE_NAME:
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

def get_tracer(name: str = "python-shared") -> Optional[Any]:
    if trace:
        return trace.get_tracer(name)
    return None

class NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None: ...
    def set_status(self, status: Any) -> None: ...
    def record_exception(self, exception: Exception) -> None: ...

@contextmanager
def trace_pipeline_stage(
    stage_name: str,
    attributes: Optional[Dict[str, Any]] = None,
    tracer_name: str = "server.ingress.pipeline",
) -> Iterator[Any]:
    tracer = get_tracer(tracer_name)
    if tracer is not None:
        with tracer.start_as_current_span(stage_name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield span
    else:
        yield NoOpSpan()
