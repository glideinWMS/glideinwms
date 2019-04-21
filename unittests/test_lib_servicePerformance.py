#!/usr/bin/env python
"""
Project:
   glideinWMS

 Description:
   unit test for glideinwms/lib/servicePerformance.py

 Author:
   Dennis Box dbox@fnal.gov
"""


from __future__ import absolute_import
from __future__ import print_function
import unittest2 as unittest
import xmlrunner

from glideinwms.lib.servicePerformance import PerfMetric
from glideinwms.lib.servicePerformance import startPerfMetricEvent
from glideinwms.lib.servicePerformance import endPerfMetricEvent
from glideinwms.lib.servicePerformance import getPerfMetricEventLifetime
from glideinwms.lib.servicePerformance import getPerfMetric

# define these globally for convenience
name = "timing_test"
expected_repr = "{'timing_test': {}}"
event_name = "test_start"
event_begin = 1518767040
event_begin_repr = "{'timing_test': {'test_start': {'start_time': 1518767040}}}"
event_end = 1518768040
event_end_repr = "{'timing_test': {'test_start': {'start_time': 1518767040, 'end_time': 1518768040}}}"
t_tag = 't_tag'
tagged_event_repr = "{'timing_test': {'test_start': {'t_tag': 1518767040}}}"


class TestPerfMetric(unittest.TestCase):

    def test___init__(self):
        perf_metric = PerfMetric(name)
        self.assertNotEqual(perf_metric, None)

    def test___repr__(self):
        perf_metric = PerfMetric(name)
        self.assertEqual(expected_repr, perf_metric.__repr__())

    def test___str__(self):
        perf_metric = PerfMetric(name)
        self.assertEqual(expected_repr, perf_metric.__str__())

    def test_deregister_event(self):
        perf_metric = PerfMetric(name)
        perf_metric.register_event_time(event_name, t_tag, event_begin)
        perf_metric.deregister_event(event_name)
        self.assertEqual(expected_repr, perf_metric.__repr__())

    def test_event_end(self):
        perf_metric = PerfMetric(name)
        perf_metric.event_start(event_name, event_begin)
        perf_metric.event_end(event_name, event_end)
        self.assertEqual(event_end_repr, perf_metric.__repr__())

    def test_event_lifetime(self):
        perf_metric = PerfMetric(name)
        perf_metric.event_start(event_name, event_begin)
        perf_metric.event_end(event_name, event_end)
        self.assertEqual(
            1000, perf_metric.event_lifetime(
                event_name, check_active_event=True))

    def test_event_start(self):
        perf_metric = PerfMetric(name)
        perf_metric.event_start(event_name, event_begin)
        self.assertEqual(event_begin_repr, perf_metric.__repr__())

    def test_register_event_time(self):
        perf_metric = PerfMetric(name)
        perf_metric.register_event_time(event_name, t_tag, event_begin)
        self.assertEqual(tagged_event_repr, perf_metric.__repr__())


class TestGetPerfMetricEventLifetime(unittest.TestCase):

    def test_get_perf_metric_event_lifetime(self):
        startPerfMetricEvent(name, event_name, event_begin)
        endPerfMetricEvent(name, event_name, event_end)
        self.assertEqual(1000, getPerfMetricEventLifetime(name, event_name))


class TestGetPerfMetric(unittest.TestCase):

    def test_get_perf_metric(self):
        startPerfMetricEvent(name, event_name, event_begin)
        endPerfMetricEvent(name, event_name, event_end)
        self.assertEqual(event_end_repr, getPerfMetric(name).__repr__())


if __name__ == '__main__':
    unittest.main(
        testRunner=xmlrunner.XMLTestRunner(
            output='unittests-reports'))
