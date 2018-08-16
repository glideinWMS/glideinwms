from operator import attrgetter
import re
from datetime import datetime
import numpy as np
import os
import argparse

class QueryInfo:
    def __init__(self, log="", query_type=None, query_pid = -1, time_stamp=None, query_time=-1, send_time=-1, query_info_type=None, requirements=None, projections=None):
        self.log = log.strip()
        self.query_type = query_type
        self.query_pid = query_pid
        self.time_stamp = time_stamp
        self.query_time = query_time
        self.send_time = send_time
        self.query_info_type = query_info_type
        self.requirements = requirements
        self.projections = projections
        self.error = ""

    def __repr__(self):
        out_str = "query_type = %s;" % self.query_type
        out_str += "query_pid = %s;" % self.query_pid
        out_str += "time_stamp = %s;" % datetime.strftime(self.time_stamp, "%Y-%m-%d %H:%M:%S")
        out_str += "query_time = %s;" % self.query_time
        out_str += "send_time = %s;" % self.send_time
        out_str += "type = %s;" % self.query_info_type
        out_str += "requirements = %s;" % self.requirements
        out_str += "projections = {%s};" % self.projections

        return out_str

"""
Separate queries are line separated, and separate properties of a query are separated by semicolons
"""
def cache_queries(query_info_list, out_file_name=""):
    if out_file_name == "":
        min_time = min([qi.time_stamp for qi in query_info_list])
        max_time = max([qi.time_stamp for qi in query_info_list])
        out_file_name = "Condor_Queries %s-%s" % (datetime.strftime(min_time, '%Y-%m-%d %H:%M:%S'), datetime.strftime(max_time, '%Y-%m-%d %H:%M:%S'))

    if os.path.exists(out_file_name):
        print "File with name %s already exists" % out_file_name
    else:
        with open(out_file_name, "w") as out_file:
            query_info_list_str = [str(qi) for qi in query_info_list]
            query_info_str = "\n".join(query_info_list_str)
            out_file.write(str(query_info_str))

    return out_file_name

def get_cached_queries(in_file_name=""):
    query_list = []
    with open(in_file_name, "r") as in_file:
        for line in in_file:
            qi = QueryInfo()
            error_check = ""
            try:
                query_type = re.search("query_type = .*?;", line).group(0)
                qi.query_type = query_type[13:-1]
                error_check += "query_type parsed"

                query_pid = re.search("query_pid = (-)?[0-9]*?;", line).group(0)
                qi.query_pid = int(re.search("(-)?[0-9]+", query_pid).group(0))
                error_check += "query_pid parsed"

                time_stamp_str = re.search("time_stamp = .*?;", line).group(0)
                qi.time_stamp = datetime.strptime(time_stamp_str[13:-1], '%Y-%m-%d %H:%M:%S')
                error_check += "time_stamp parsed"

                query_time = re.search("query_time = (-)?([0-9\.]+)([eE](-)?[0-9]+)?", line).group(0)
                qi.query_time = float(query_time[13:])
                error_check += "query_time parsed,"

                send_time = re.search("send_time = (-)?([0-9\.]+)([eE](-)?[0-9]+)?", line).group(0)
                qi.send_time = float(send_time[12:])
                error_check += "send_time parsed"

                query_info_type = re.search("type = .*?;", line).group(0)
                qi.query_info_type = query_info_type[7:-1]
                error_check += "query_info_type parsed"

                constraint = re.search("requirements = .*?;", line).group(0)
                qi.constraint = constraint[15:-1]
                error_check += "constraint parsed"

                projection = re.search("projections = {.*?};", line).group(0)
                qi.constraint = constraint[15:-2]
                error_check += "projection parsed"

            except AttributeError:
#                print error_check
                qi.error = "Error drawing from cache: " + line
                print qi.error

            query_list.append(qi)
    return query_list

query_info_list = []

time_stamp = None
requirements = None
projections = None
query_time = -1
send_time = -1

def parse_condor_logs(log_file_name):
    with open(log_file_name) as fd:
        for log in fd:
            qi = QueryInfo(log)
            try:
                time_str = re.search('^[0-9][0-9]/[0-9][0-9]/[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]', log).group(0)
                time_stamp = datetime.strptime(time_str, '%m/%d/%y %H:%M:%S')
                qi.time_stamp = time_stamp
            except AttributeError:
                print "Time stamp format mismatch: %s" % log

            query_info_match = re.search(r"Query info.+query_time=.+send_time=.+type=.+requirements={.*?}.+projection={.*?}", log)
            if query_info_match:
                query_info = query_info_match.group(0)
                try:
                    query_time_str = re.search("query_time=[0-9\.]*", query_info).group(0)
                    query_time = float(query_time_str[11:])
                    qi.query_time = query_time
                except AttributeError:
                    print "query_time format mismatch: %s" % log

                try:
                    send_time_str = re.search("send_time=[0-9\.]*", query_info).group(0)
                    send_time = float(send_time_str[10:])
                    qi.send_time = send_time
                except AttributeError:
                    print "send_time format mismatch: %s" % log

                try:
                    query_info_type = re.search("type=.+?;", query_info).group(0)
                    query_info_type = query_info_type[5:-1]
                    qi.query_info_type = query_info_type
                except AttributeError:
                    print "type format mismatch: %s" % log

                try:
                    requirements = re.search("requirements={.*?}", query_info).group(0)
                    requirements = requirements[14:-1]
                    qi.requirements = requirements

                    try:
                        query_type_pid_str = re.search("MyType[\s]*=!=[\s]*\"(condor_status_|exe_condor_status_|condor_q_|exe_condor_q_)[0-9]+\"", requirements).group(0)
                        qi.query_type = re.search("\"(condor_status|exe_condor_status|condor_q|exe_condor_q)", query_type_pid_str).group(0)
                        qi.pid = int(re.search("[0-9]+", query_type_pid_str).group(0))
                    except AttributeError:
                        qi.pid = -1

                except AttributeError:
                    print "requirements format mismatch: %s" % log

                try:
                    projections = re.search("projection={.*?}", query_info).group(0)
                    projections = projections[12:-1]
                    projections_list = projections.split(" ")
                    qi.projections = projections
                except AttributeError:
                    print "projections format mismatch"

                query_info_list.append(qi)
            elif log.find("Query info") != -1:
                print "Query info format mismatch: %s" % log

    return query_info_list

def build_query_info_dict(query_list):
    query_info_dict = {}
    for qi in query_list:
#        key = "%s {%s}" % (qi.query_info_type, qi.projections)
        key = "%s [%s] {%s}" % (qi.query_info_type, qi.requirements, qi.projections)
        if key not in query_info_dict:
            query_info_dict[key] = list()
        query_info_dict[key].append(qi)

    return query_info_dict

def get_query_stats(query_stats_list, list_title=""):
    if query_stats_list and len(query_stats_list) > 0:
        avg = np.average(query_stats_list)
        var = np.var(query_stats_list, ddof = 1) if len(query_stats_list) > 1 else 0
        stat_min = min(query_stats_list)
        stat_max = max(query_stats_list)
        if len(query_stats_list) % 2 == 0:
            median = query_stats_list[len(query_stats_list)/2]
        elif len(query_stats_list) > 1:
            indx = int(len(query_stats_list)/2)
            median = (query_stats_list[indx] + query_stats_list[indx + 1])/2
        else:
            median = query_stats_list[0]
        out_str = "---- %s Statistics ---\n" % list_title
        out_str += "N = %d\n" % len(query_stats_list)
        out_str += "Average = %f\n" % avg
        out_str += "Variance = %f\n" % var
        out_str += "Min = %f\n" % stat_min
        out_str += "Max = %f\n" % stat_max
        out_str += "Median = %f\n" % median
        print out_str
    else:
        print "Invalid query statistics passed"

query_info_list = parse_condor_logs("/Users/jlundell/Documents/collector_logs/CollectorLog.20180619T004611")
query_info_projection_dict = {"Empty" : [], "Nonempty" : []}
query_info_dict = build_query_info_dict(query_info_list)
for k in query_info_dict:
    query_time_list = [qi.query_time for qi in query_info_dict[k]]
    send_time_list = [qi.send_time for qi in query_info_dict[k]]
    get_query_stats(query_time_list, "Query.query_time: %s" % k)
    get_query_stats(send_time_list, "Query.send_time: %s" % k)
cache_queries(query_info_list)

"""
grouped_query_info = sorted(query_info_list, key=attrgetter("projections", "requirements", "query_type"))
time_types = {}
time_avg = {}
for qi in grouped_query_info:
    if qi.query_type in time_types:
        time_types[qi.query_type].append(qi)
    else:
        time_types[qi.query_type] = [qi]

    if (qi.projections == None or qi.projections == ""):
        print qi.log
#        print "%s\t%s\t%s\t%s\t%s" % (datetime.datetime.strftime(qi.time_stamp, "%m/%d/%y %H:%M:%S"), qi.query_time, qi.query_type, qi.requirements, qi.projections)

for query_type in time_types:
    time_avg[query_type] = sum(qi.query_time for qi in time_types[query_type]) / len(time_types[query_type])
print "query_time Averages by Type = %s\n" % time_avg

# Condense!!!
qtime_list = [qi.query_time for qi in grouped_query_info]
qtime_avg = np.average(qtime_list)
qtime_var = np.var(qtime_list, ddof = 1)

qtime_avg = sum(qtime_list) / len(qtime_list)
if len(qtime_list) > 1:
    qtime_var = sum((qi - qtime_avg) ** 2 for qi in qtime_list) / (len(qtime_list) - 1)
else:
    qtime_var = -1
qtime_max = max(qtime_list)

qtime_nonempty_list = [qi.query_time for qi in grouped_query_info if (qi.projections != None or qi.projections != "")]
qtime_nonempty_avg = sum(qtime_nonempty_list) / len(qtime_nonempty_list)
if len(qtime_nonempty_list) > 1:
    qtime_nonempty_var = sum((qi - qtime_nonempty_avg) ** 2 for qi in qtime_nonempty_list) / (len(qtime_nonempty_list) - 1)
else:
    qtime_nonempty_var = -1
qtime_nonempty_max = max(qtime_nonempty_list)

qtime_empty_projection_list = [qi.query_time for qi in grouped_query_info if (qi.projections == None or qi.projections == "")]
qtime_empty_projection_avg = sum(qtime_empty_projection_list) / len(qtime_empty_projection_list)
if len(qtime_empty_projection_list) > 1:
    qtime_empty_projection_var = sum((qi - qtime_empty_projection_avg) ** 2 for qi in qtime_empty_projection_list) / (len(qtime_empty_projection_list) - 1)
else:
    qtime_empty_projection_var = -1
qtime_empty_projection_max = max(qtime_empty_projection_list)

stime_list = [qi.send_time for qi in grouped_query_info]
stime_avg = sum(stime_list) / len(stime_list)
if len(stime_list) > 1:
    stime_var = sum((qi - stime_avg) ** 2 for qi in stime_list) / (len(stime_list) - 1)
else:
    stime_var = -1

stime_empty_projection_list = [qi.send_time for qi in grouped_query_info if (qi.projections == None or qi.projections == "")]
stime_empty_projection_avg = sum(stime_empty_projection_list) / len(stime_empty_projection_list)
if len(stime_empty_projection_list) > 1:
    stime_empty_projection_var = sum((qi - stime_empty_projection_avg) ** 2 for qi in stime_empty_projection_list) / (len(stime_empty_projection_list) - 1)
else:
    stime_empty_projection_var = -1
stime_empty_projection_max = max(stime_empty_projection_list)

# Group by (MyType, Projection, Constraint), and do same stats as below

query_dict = {}
for qi in query_info_list:
    key = (qi.query_type, qi.projections)
    if key in query_dict:
        query_dict[key].append(qi)
    else:
        query_dict[key] = [qi]

print "Number of unique combinations of (query_type, query_projections) = %s" % len(query_dict.keys())
for k in query_dict:
    print k
    print "\tNumber elements = %s" % len(query_dict[k])

    query_times = [qi.query_time for qi in query_dict[k]]
    qtime_avg = sum(query_times) / len(query_times)
    print "\tAverage query_time = %s" % qtime_avg
    if len(query_dict[k]) > 1:
        qtime_var = sum([(q_time - qtime_avg) ** 2 for q_time in query_times]) / (len(query_times) - 1)
    else:
        qtime_var = 0
    print"\tVariance query_time = %s" % qtime_var
    print "\tMin query_time = %s" % min(query_times)
    print "\tMax query_time = %s" % max(query_times)

print "Number of Query Info = %s\n" % len(query_info_list)

print "Max query_time = %s" % qtime_max
print "Average query_time = %s" % qtime_avg
print "N query_time = %s"
print "Variance query_time = %s" % qtime_var
print "Max query_time = %s" % max(qtime_list)
print "Min query_time = %s\n" % min(qtime_list)

print "Max Nonempty Projection query_time = %s" % qtime_nonempty_max
print "Average Nonempty Projection query_time = %s" % qtime_nonempty_avg
print "Variance Nonempty Projection query_time = %s" % qtime_nonempty_var
print "Max Nonempty Projection query_time = %s" % max(qtime_nonempty_list)
print "Min Nonempty Projection query_time = %s\n" % min(qtime_nonempty_list)

print "Max Empty Projection query_time = %s" % qtime_empty_projection_max
print "Average Empty Projection query_time = %s" %  qtime_empty_projection_avg
print "Variance Empty Projection query_time = %s" % qtime_empty_projection_var
print "Max Empty Projection query_time = %s" % max(qtime_empty_projection_list)
print "Min Empty Projection query_time = %s\n" % min(qtime_empty_projection_list)

print "Average sending_time = %s" % stime_avg
print "Variance sending_time = %s" % stime_var
print "Max sending_time = %s" % max(stime_list)
print "Min sending_time = %s\n" % min(stime_list)

print "Max Empty Projection sending_time = %s" % stime_empty_projection_max
print "Average Empty Projection sending_time = %s" % stime_empty_projection_avg
print "Variance Empty Projection sending_time = %s" % stime_empty_projection_var
print "Max Empty Projection sending_time = %s" % max(stime_list)
print "Min Empty Projection sending_time = %s" % min(stime_list)
"""