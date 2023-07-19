# SPDX-FileCopyrightText: 2022 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# GlideinWMS documentation for GlideFactoryLib.py, constructing
# a Tracer and Trace class to give Glidein's unique TRACE_ID
# and methods to send child spans or print the TRACE_ID of Glidein
import os

# fmt: on
import time

from opentelemetry import propagate, trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# fmt: off
os.environ["OTEL_PROPAGATORS"] = "jaeger"



# Global variables to establish tracing to Jaeger
# ideally, these are read from the environment and have defaults (ex: server = "localhost", port = 6831)
jaeger_collector_endpoint = "http://fermicloud296.fnal.gov:14268/api/traces?format=jaeger.thrift"


class Tracer:
    def __init__(self, collector_endpoint, jaeger_service_name="glidein"):
        """Initializes a tracer with OpenTelemetry and Jaeger when operated in the GlideinWMS Factory

        Args:
            collector_endpoint (str): the http url for the collector endpoint (ex: "http://localhost:14268/api/traces?format=jaeger.thrift")
            jaeger_service_name (str): the service to which the trace sends to through Jaeger
        Variables:
            GLIDEIN_TRACE_ID (hex): the parent trace_id of each submitted glidein instance
            tracer: a tracer instance for each glidein to generate more spans
            carrier = the injected SpanContext to be used to propogate child spans
        """
        self.collector_endpoint = collector_endpoint
        self.jaeger_service_name = jaeger_service_name
        self.GLIDEIN_TRACE_ID = None
        self.tracer = None
        self.carrier = None

    def initial_trace(self,tags={}):
        self.tags = tags

        trace.set_tracer_provider(TracerProvider(resource=Resource.create({SERVICE_NAME:self.jaeger_service_name})))

        self.tracer = trace.get_tracer(__name__)

        jaeger_exporter = JaegerExporter(collector_endpoint=self.collector_endpoint)
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        self.carrier = {}  # used to propogate spanContext to child spans

        with self.tracer.start_as_current_span("parent") as parent: # this is the parent span for each submitted glidein
            for key,value in self.tags.items():
                parent.set_attribute(key,value)
            TraceContextTextMapPropagator().inject(carrier=self.carrier)
            c = {}
            propagate.inject(c)
            self.GLIDEIN_TRACE_ID = c["uber-trace-id"]



class Trace:
    def __init__(self, tracer, carrier):
        """Initializes tracing with an established tracer, with send_span and get_span_ID methods

        Args:
            tracer (opentelemetry.sdk.trace.Tracer): tracer initialized from Tracer class (each glidein instance
            has its own tracer)
            carrier (SpanContext): the SpanContext of the parent trace initialized for each glidein to propogate to
            child spans so that they are linked

        Variables:
            GLIDEIN_SPAN_ID = the span_id of the glidein operation
            SpanContext = the SpanContext of the parent trace so that child spans are linked
            ctx = the context extracted from SpanContext so that it can be used for child span
        """
        self.tracer = tracer
        self.carrier = carrier
        self.GLIDEIN_SPAN_ID = []
        self.SpanContext = None
        self.ctx = None


    def send_span(self):
        self.ctx = TraceContextTextMapPropagator().extract(carrier=self.carrier)
        with self.tracer.start_as_current_span("child_init", context=self.ctx) as child:
            c={}
            propagate.inject(c)
            self.GLIDEIN_SPAN_ID.append(c['uber-trace-id'])


def main():  # use classes above to initialize a tracer and send a span and print trace id
    T = Tracer(jaeger_collector_endpoint)
    T.initial_trace({"entry":"entry_name","client":"client_name"})
    t = Trace(T.tracer, T.carrier)
    t.send_span()




if __name__ == "__main__":
    main()
