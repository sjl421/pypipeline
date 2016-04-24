from pypipeline.core.DummySource import DummySource
from .Pipeline import Pipeline
from .Source import Source
from .Destination import Destination
from .PipelineBuilder import PipelineBuilder
from pypipeline.eip.split.Splitter import Splitter
from pypipeline.eip.filter.Filter import Filter
from pypipeline.eip.multicast.Multicast import Multicast
from pypipeline.eip.aggregate.Aggregator import Aggregator
from pypipeline.eip.cbr.ContentBasedRouter import ContentBasedRouter


class DslPipelineBuilder(PipelineBuilder):

    def __init__(self):
        super().__init__()
        self.destination_stack = []
        self.builder_stack = [self,]
        self.when_condition = None

    def source(self, endpoint, params=None):
        if params is None:
            params = {}
        assert issubclass(endpoint, Source), "The source class should be a subclass of Source"
        assert self.builder_stack[-1].source_class is None, "There can only be one source in a pipeline"
        self.builder_stack[-1].source_class = endpoint
        self.builder_stack[-1].source_params = params
        assert issubclass(self.builder_stack[-1].source_class, Source), "The source class should be a subclass of Source"
        return self

    def to(self, endpoint, params=None):
        if params is None:
            params = {}
        assert issubclass(endpoint, Destination), "The destination class should be a subclass of Destination"
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        to_class = endpoint
        self.builder_stack[-1].to_list.append((to_class, params))
        return self

    def process(self, method):
        assert callable(method), "You need to provide a callable function"
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        to_class = type("", (Destination,), {"process": lambda self, exchange: method(exchange)})
        self.builder_stack[-1].to_list.append((to_class, None))
        return self

    def split(self, method):
        assert callable(method), "You need to provide a callable function"
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        to_class = type("", (Splitter,), {"split": lambda self, exchange: method(exchange)})
        self.builder_stack[-1].to_list.append((to_class, None))
        return self

    def filter(self, method):
        assert callable(method), "You need to provide a callable function"
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        to_class = type("", (Filter,), {"filter": lambda self, exchange: method(exchange)})
        self.builder_stack[-1].to_list.append((to_class, None))
        return self

    def aggregate(self, params):
        assert "method" in params, "You need to provide the method to use for aggregation"
        assert callable(params["method"]), "You need to provide a callable method"
        assert ~("timeout" not in params and "count" not in params), "You need to provide atlease one termination condition: timeout, count"
        to_class = type("", (Aggregator,), {"aggregate": lambda self, old_exchange, current_exchange: params["method"](old_exchange, current_exchange)})
        self.builder_stack[-1].to_list.append((to_class, params))
        return self

    def multicast(self, params):
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        assert isinstance(params, dict), "The parameters must be a dict"
        if "aggregate_method" in params:
            aggregate_class = type("", (Aggregator,), {"aggregate": lambda self, old_exchange, current_exchange: params["aggregate_method"](old_exchange, current_exchange)})
        else:
            aggregate_class = Aggregator
        params["aggregator"] = aggregate_class
        self.destination_stack.append({"type": Multicast, "params": params})
        return self

    def end_multicast(self):
        assert self.destination_stack[-1]["type"] == Multicast
        to_class = Multicast
        self.to_list.append((to_class, self.destination_stack[-1]["params"]))
        self.destination_stack.pop()
        return self

    def content_based_router(self, params=None):
        if params is None:
            params = {}
        assert self.builder_stack[-1].source_class is not None, "Pipeline definition must start with a source"
        assert isinstance(params, dict), "The parameters must be a dict"
        self.destination_stack.append({"type": ContentBasedRouter, "params": params})
        return self

    def end_content_based_router(self):
        assert self.destination_stack[-1]["type"] == ContentBasedRouter
        to_class = ContentBasedRouter
        self.to_list.append((to_class, self.destination_stack[-1]["params"]))
        self.destination_stack.pop()
        return self

    def when(self, condition):
        assert self.builder_stack[-1].when_condition is None, "Another when block still not complete"
        self.builder_stack[-1].when_condition = condition
        return self

    def otherwise(self):
        assert self.builder_stack[-1].when_condition is None, "Another when block still not complete"
        self.builder_stack[-1].when_condition = lambda ex: True
        return self

    def pipeline(self):
        builder = DslPipelineBuilder()
        builder.source_class = DummySource
        builder.source_params = {}
        self.builder_stack.append(builder)
        return self

    def end_pipeline(self):
        if self.destination_stack[-1]["type"] == Multicast:
            self.destination_stack[-1]["params"].setdefault('pipelines', []).append(self.builder_stack[-1])
        pipeline = self.builder_stack.pop()
        if self.destination_stack[-1]["type"] == ContentBasedRouter:
            self.destination_stack[-1]["params"].setdefault('branches', []).append((self.builder_stack[-1].when_condition, pipeline))
            self.builder_stack[-1].when_condition = None
        return self

    def id(self, name):
        self.id = name

    def auto_start(self, value):
        assert isinstance(value, bool), "auto_start parameter accepts only boolean values"
        self.auto_start = value

    def build(self):
        return self.build_with_plumber(None)

    def build_with_plumber(self, plumber):
        assert len(self.to_list) > 0, "Pipeline needs to have atleast one destination"
        return Pipeline(self, plumber)