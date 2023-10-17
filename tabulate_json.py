import itertools
import json
import os

from datetime import datetime

from prettytable import PrettyTable

# the .json files save under a directory with the jaeger_service_name as its name
# so, would need to make sure the filepath is accessible to read the traceid.json files
service = None

# this would need to be passed
trace_id = "cbedb06686ef4e101a19cad348317c05"

directory = os.curdir


class TraceData:
    def __init__(self, data):
        self.data = data
        self.traceID = None
        self.spans = []
        self.entry = None
        self.client = None
        self.duration = []
        self.parentID = []
        self.startTime = []

    def get_spans(self):
        span_list = self.data["spans"]
        for i in span_list:
            self.spans.append(i["spanID"])

    def get_trace_id(self):
        self.traceID = self.data["traceID"]

    def get_tags(self):
        span_list = self.data["spans"]
        tags_list = []
        for i in span_list:
            if i["tags"] == []:
                pass
            else:
                tags_list.append(i["tags"])
        for tags in tags_list:
            for tag in tags:
                if tag["key"] == "entry":
                    self.entry = tag["value"]
                if tag["key"] == "client":
                    self.client = tag["value"]

    def get_duration(self):
        span_list = self.data["spans"]
        time_ref_list = []
        for i in span_list:
            self.duration.append(i["duration"])
        for i in span_list:
            time_ref_list.append(i["startTime"])
        for i in time_ref_list:
            time = datetime.utcfromtimestamp(i / 1000000).strftime("%Y-%m-%d %H:%M:%S")
            self.startTime.append(time)

    def get_parentID(self):
        span_list = self.data["spans"]
        ref_list = []
        for i in span_list:
            if i["references"] == []:
                ref_list.append(0)
            else:
                ref_list.append(i["references"])
        for j in ref_list:
            if j == 0:
                self.parentID.append("None")
            else:
                self.parentID.append(j[0]["spanID"])


with open(f"{directory}/glidein/{trace_id}.json") as f:
    data = json.loads(f.read())

T = TraceData(data)
T.get_spans()
print(T.spans)
T.get_trace_id()
print(T.traceID)
T.get_duration()
print(T.duration)
T.get_parentID()
print(T.parentID)
T.get_tags()

A = PrettyTable()
A.field_names = ["TraceID:SpanID", "Parent Span", "Entry", "Client", "Start Time (UTC)", "Duration(μs)"]
for (i, j, z, k) in zip(T.spans, T.duration, T.parentID, T.startTime):
    A.add_row([f"{T.traceID}:{i}", f"{z}", T.entry, T.client, f"{k}", f"{j}"])


print(A)
