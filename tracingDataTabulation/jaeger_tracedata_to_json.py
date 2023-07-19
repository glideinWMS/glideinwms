#!/usr/bin/env python3

import argparse
import json
import os

import requests

# ----------------------------------------------------------------
# Here is where you put the link to your JAEGER COLLECTOR ENDPOINT
# (ex: "http://localhost:16686/api/traces?limit=20000&")
# For each service at that collector endpoint, a directory will be
# made with all traces under it
# ----------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("endpoint", help="Manually input the jaeger host you would like to retrieve from (ex: localhost).")
args = parser.parse_args()
endpoint = args.endpoint

JAEGER_TRACES_ENDPOINT = f"http://{endpoint}:16686/api/traces?limit=20000&"
JAEGER_TRACES_PARAMS = "service="


def get_traces(service):
    """
    Returns list of all traces for a service
    """
    url = JAEGER_TRACES_ENDPOINT + JAEGER_TRACES_PARAMS + service
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise err

    response = json.loads(response.text)
    traces = response["data"]
    return traces


JAEGER_SERVICES_ENDPOINT = f"http://{endpoint}:16686/api/services"


def get_services():
    """
    Returns list of all services
    """
    try:
        response = requests.get(JAEGER_SERVICES_ENDPOINT)
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        raise err

    response = json.loads(response.text)
    services = response["data"]
    return services


def write_traces(directory, traces):
    """
    Write traces locally to files
    """
    for trace in traces:
        traceid = trace["traceID"]
        path = directory + "/" + traceid + ".json"
        with open(path, "w") as fd:
            fd.write(json.dumps(trace, indent=2))


# Pull traces for all the services & store locally as json files
for service in get_services():
    if not os.path.exists(service):
        os.makedirs(service)
    traces = get_traces(service)
    write_traces(service, traces)
