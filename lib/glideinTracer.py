# SPDX-FileCopyrightText: 2022 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# GlideinWMS documentation for GlideFactoryLib.py, constructing 
# a Tracer and Trace class to give Glidein's unique TRACE_ID 
# and methods to send child spans or print the TRACE_ID of Glidein
import os
os.environ['OTEL_PROPAGATORS']='jaeger'
from opentelemetry import propagate
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import \
    TraceContextTextMapPropagator


# Global variables to establish tracing to Jaeger
# ideally, these are read from the environment and have defaults (ex: server = "localhost", port = 6831)
jaeger_service = "glidein"
jaeger_collector_endpoint = "http://fermicloud296.fnal.gov:14268/api/traces?format=jaeger.thrift"


class Tracer:
    def __init__(self, collector_endpoint):
        """Initializes a tracer with OpenTelemetry and Jaeger when operated in the GlideinWMS Factory

        Args:
            server (str): if not "localhost", then the host where the Jaeger Agent is running in a container
            port (int): the port to which traces will talk to Jaeger
            
        Variables:
            GLIDEIN_TRACE_ID (hex): the parent trace_id of each submitted glidein instance
            tracer: a tracer instance for each glidein to generate more spans
            carrier = the injected SpanContext to be used to propogate child spans
        """
        self.collector_endpoint = collector_endpoint
        self.GLIDEIN_TRACE_ID = None
        self.tracer = None
        self.carrier = None

    def initial_trace(self):
        trace.set_tracer_provider(
        TracerProvider(
                resource=Resource.create({SERVICE_NAME:jaeger_service})
            )
        )
        
        self.tracer = trace.get_tracer(__name__)
        
        jaeger_exporter = JaegerExporter(
            collector_endpoint=self.collector_endpoint
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        self.carrier = {} #used to propogate spanContext to child spans
        
        with self.tracer.start_as_current_span("parent") as parent: #this is the parent span for each submitted glidein
            TraceContextTextMapPropagator().inject(carrier=self.carrier)
            c={}
            propagate.inject(c)
            self.GLIDEIN_TRACE_ID=c['uber-trace-id']
            
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
        self.GLIDEIN_SPAN_ID = None
        self.SpanContext = None
        self.ctx = None
        

    def send_span(self):
        self.ctx = TraceContextTextMapPropagator().extract(carrier=self.carrier)
        with self.tracer.start_as_current_span("child", context=self.ctx) as child:
            c={}
            propagate.inject(c)
            self.GLIDEIN_SPAN_ID=c['uber-trace-id']
    
    def get_span_ID(self):
        print(self.GLIDEIN_SPAN_ID)

def main(): # use classes above to initialize a tracer and send a span and print trace id
    T = Tracer(jaeger_collector_endpoint)
    T.initial_trace()
    print(T.GLIDEIN_TRACE_ID)
    t = Trace(T.tracer,T.carrier)
    print(t.GLIDEIN_SPAN_ID)


if __name__ == "__main__":
    main()
