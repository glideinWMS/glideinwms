#!/bin/env python

###############################################################################
# servicePerf.py
#
# Description:
#
# Author:
#   Parag Mhashilkar (November 2016)
#
# License:
#  Fermitools
#
###############################################################################

import time

class PerfMetric:
    """
    Class to store performance metrics for different events in a service
    """

    def __init__(self, name):
        self.name = name
        # metric is a dict of dict with following structure
        # {event_name: {'start_time': time(), 'end_time': time()}}
        self.metric = {}


    def register_event_time(self, event_name, t_tag, t=None):
        if not t:
            t = time.time()
        if event_name not in self.metric:
            self.metric[event_name] = {}
        self.metric[event_name][t_tag] = t


    def deregister_event(self, event_name):
        self.metric.pop(event_name, None)


    def event_start(self, event_name, t=None):
        self.register_event_time(event_name, 'start_time', t=t)
    

    def event_end(self, event_name, t=None):
        self.register_event_time(event_name, 'end_time', t=t)


    def event_lifetime(self, event_name, check_active_event=True):
        lifetime = -1
        if event_name in self.metric:
            if (('start_time' in self.metric[event_name]) and
                ('end_time' in self.metric[event_name])):
                lifetime = self.metric[event_name]['end_time'] - self.metric[event_name]['start_time']
                # Event still alive, consider current time instead of end time
                if (lifetime < 0) and (check_active_event):
                    lifetime = time.time() - self.metric[event_name]['start_time']
        return float('{0:.3f}'.format(lifetime))


    def __str__(self):
        return self.__repr__()


    def __repr__(self):
        return "{'%s': %s}" % (self.name, self.metric)



# Internal global dict of performance metric objects
# Should not be used directly
_perf_metric = {}


################################################################################
# User functions
################################################################################


def startPerfMetricEvent(name, event_name, t=None):
    perf_metric = getPerfMetric(name)
    perf_metric.event_start(event_name, t=t)


def endPerfMetricEvent(name, event_name, t=None):
    perf_metric = getPerfMetric(name)
    perf_metric.event_end(event_name, t=t)


def getPerfMetricEventLifetime(name, event_name):
    return getPerfMetric(name).event_lifetime(event_name)


def getPerfMetric(name):
    """
    Given the name of the service, return the PerfMetric object
    """

    global _perf_metric
    if name not in _perf_metric:
        _perf_metric[name] = PerfMetric(name)
    return _perf_metric[name]



