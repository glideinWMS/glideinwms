#!/bin/env python

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
servicePerf.py

This module provides classes and functions to track performance metrics for different events in a service.

Author:
    Parag Mhashilkar (November 2016)

License:
    Fermitools
"""

import time


class PerfMetric:
    """
    A class to store performance metrics for different events in a service.

    Attributes:
        name (str): The name of the service being monitored.
        metric (dict): A dictionary that stores the start and end times for various events.
    """

    def __init__(self, name):
        """
        Initialize a PerfMetric object.

        Args:
            name (str): The name of the service.
        """
        self.name = name
        self.metric = {}

    def register_event_time(self, event_name, t_tag, t=None):
        """
        Register a time for a specific event.

        Args:
            event_name (str): The name of the event.
            t_tag (str): The tag for the time (e.g., 'start_time', 'end_time').
            t (float, optional): The time to register. If not provided, the current time is used.
        """
        if not t:
            t = time.time()
        if event_name not in self.metric:
            self.metric[event_name] = {}
        self.metric[event_name][t_tag] = t

    def deregister_event(self, event_name):
        """
        Remove an event from the metric tracking.

        Args:
            event_name (str): The name of the event to remove.
        """
        self.metric.pop(event_name, None)

    def event_start(self, event_name, t=None):
        """
        Register the start time of an event.

        Args:
            event_name (str): The name of the event.
            t (float, optional): The start time of the event. If not provided, the current time is used.
        """
        self.register_event_time(event_name, "start_time", t=t)

    def event_end(self, event_name, t=None):
        """
        Register the end time of an event.

        Args:
            event_name (str): The name of the event.
            t (float, optional): The end time of the event. If not provided, the current time is used.
        """
        self.register_event_time(event_name, "end_time", t=t)

    def event_lifetime(self, event_name, check_active_event=True):
        """
        Calculate the lifetime of an event.

        Args:
            event_name (str): The name of the event.
            check_active_event (bool, optional): Whether to check if the event is still active (i.e., has no end time).
                                                 If True, the current time is used as the end time if the event is still active.

        Returns:
            float: The lifetime of the event in seconds, rounded to three decimal places.
        """
        lifetime = -1
        if event_name in self.metric:
            if ("start_time" in self.metric[event_name]) and ("end_time" in self.metric[event_name]):
                lifetime = self.metric[event_name]["end_time"] - self.metric[event_name]["start_time"]
                if (lifetime < 0) and check_active_event:
                    lifetime = time.time() - self.metric[event_name]["start_time"]
        return float(f"{lifetime:.3f}")

    def __str__(self):
        """Return a string representation of the PerfMetric object."""
        return self.__repr__()

    def __repr__(self):
        """Return a detailed string representation of the PerfMetric object."""
        return f"{{'{self.name}': {self.metric}}}"


# Internal global dict of performance metric objects
# Should not be used directly
_perf_metric = {}


################################################################################
# User functions
################################################################################

def startPerfMetricEvent(name, event_name, t=None):
    """
    Start tracking an event's performance for a given service.

    Args:
        name (str): The name of the service.
        event_name (str): The name of the event to start tracking.
        t (float, optional): The start time of the event. If not provided, the current time is used.
    """
    perf_metric = getPerfMetric(name)
    perf_metric.event_start(event_name, t=t)


def endPerfMetricEvent(name, event_name, t=None):
    """
    Stop tracking an event's performance for a given service.

    Args:
        name (str): The name of the service.
        event_name (str): The name of the event to stop tracking.
        t (float, optional): The end time of the event. If not provided, the current time is used.
    """
    perf_metric = getPerfMetric(name)
    perf_metric.event_end(event_name, t=t)


def getPerfMetricEventLifetime(name, event_name):
    """
    Get the lifetime of a specific event for a given service.

    Args:
        name (str): The name of the service.
        event_name (str): The name of the event.

    Returns:
        float: The lifetime of the event in seconds, rounded to three decimal places.
    """
    return getPerfMetric(name).event_lifetime(event_name)


def getPerfMetric(name):
    """
    Retrieve or create a PerfMetric object for a given service.

    Args:
        name (str): The name of the service.

    Returns:
        PerfMetric: The PerfMetric object for the service.
    """
    global _perf_metric
    if name not in _perf_metric:
        _perf_metric[name] = PerfMetric(name)
    return _perf_metric[name]
