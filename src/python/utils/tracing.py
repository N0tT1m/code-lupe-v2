"""OpenTelemetry distributed tracing for Python services."""

import os
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracer(service_name: str) -> trace.Tracer:
    """
    Initialize OpenTelemetry tracing.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Tracer instance
    """
    # Create resource
    resource = Resource(attributes={
        SERVICE_NAME: service_name,
        "service.version": os.getenv("APP_VERSION", "dev"),
    })
    
    # Create Jaeger exporter
    jaeger_endpoint = os.getenv("JAEGER_ENDPOINT", "localhost")
    jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))
    
    jaeger_exporter = JaegerExporter(
        agent_host_name=jaeger_endpoint,
        agent_port=jaeger_port,
    )
    
    # Create trace provider
    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)
    
    # Set global trace provider
    trace.set_tracer_provider(provider)
    
    return trace.get_tracer(service_name)


# Example usage:
#
# from src.python.utils.tracing import init_tracer
#
# tracer = init_tracer("trainer")
#
# with tracer.start_as_current_span("training_batch"):
#     # Your training code here
#     pass
