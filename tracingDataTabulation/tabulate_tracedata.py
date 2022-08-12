#!/usr/bin/env python3

import os
import json
import sys
import argparse
import itertools
from prettytable import PrettyTable
from datetime import datetime

# ----------------------------------------------
# This script must be run in the same directory 
# in which the service name directories exist
# See line 80 to manage the file tree navigation
# ----------------------------------------------

# variable 'service' is to be the service you would 
# like to look under to tabulate a traceID, this is 
# the directory os uses 

# ARGPARSE the traceID and service
# TO FIND TRACEID - copy and paste under its respective directory
# (would be service name) and use as an argument along with service name
# when running executable
parser = argparse.ArgumentParser()
parser.add_argument("traceID", help = "Manually input the traceID you would like to tabulate.")
parser.add_argument("service", help = "Manually input the name of the directory (the service name) your traceID is under.")
args = parser.parse_args()
traceID = args.traceID
service = args.service

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
        span_list = (self.data["spans"])
        for i in span_list:
            self.spans.append(i["spanID"])
                        
    def get_trace_id(self):
        self.traceID = self.data["traceID"]
    
    def get_tags(self):
        span_list = (self.data["spans"])
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
        span_list=(self.data["spans"])
        time_ref_list = []
        for i in span_list:
            self.duration.append(i["duration"])
        for i in span_list:
            time_ref_list.append(i["startTime"])
        for i in time_ref_list:
            time = datetime.utcfromtimestamp(i/1000000).strftime(('%Y-%m-%d %H:%M:%S'))
            self.startTime.append(time)
        
            
    def get_parentID(self):
        span_list = (self.data["spans"])
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
                    
with open(f"{directory}/{service}/{traceID}.json") as f:
    data = json.loads(f.read())

if __name__ == "__main__":
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

# TABULATION
A=PrettyTable()
A.field_names=["TraceID:SpanID", "Parent Span", "Entry", "Client", "Start Time (UTC)", "Duration(μs)"]
for (i,j,z,k) in zip(T.spans,T.duration, T.parentID, T.startTime):
    A.add_row([f"{T.traceID}:{i}",f"{z}",T.entry, T.client,f"{k}",f"{j}"])
print(A)
