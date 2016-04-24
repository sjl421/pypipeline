import unittest
from pypipeline.core import EndpointRegistry
from pypipeline.core.Plumber import Plumber
from pypipeline.core.DslPipelineBuilder import DslPipelineBuilder
from pypipeline.core.Destination import Destination
from pypipeline.components.Timer import Timer
import time


class PlumberTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        EndpointRegistry.add_endpoint("timer", Timer)
        EndpointRegistry.add_endpoint("mm", MessageModifier)

    def test_simple_pipeline(self):
        plumber = Plumber()
        builder1 = DslPipelineBuilder()
        builder2 = DslPipelineBuilder()
        pipeline1 = builder1.source("timer://test?period=1.0").to("mm://test").process(lambda ex: print(ex.in_msg.body + " Pipeline1"))
        pipeline2 = builder2.source("timer://test?period=2.0").to("mm://test").process(lambda ex: print(ex.in_msg.body + " Pipeline2"))
        plumber.add_pipeline(pipeline1)
        plumber.add_pipeline(pipeline2)
        plumber.start()
        time.sleep(10)
        plumber.stop()


class MessageModifier(Destination):
    def process(self, exchange):
        exchange.in_msg.body += " modified"