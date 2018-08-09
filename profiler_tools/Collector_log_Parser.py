from operator import attrgetter
import re
import datetime
import numpy as np

class QueryInfo:
    def __init__(self, log, time_stamp=None, query_time=None, send_time=None, query_type=None, requirements=None, projections=None):
        self.log = log.strip()
        self.time_stamp = time_stamp
        self.query_time = query_time
        self.send_time = send_time
        self.query_type = query_type
        self.requirements = requirements
        self.projections = projections

    def __str__(self):
        return "time_stamp:\t%squery_time:\t%f\nsend_time:\t%f\nquery_type:\t%s\nrequirements:\t%s\nprojections:\t%s\n" % (self.time_stamp, self.query_time, self.send_time, self.query_type, self.requirements, self.projections)

query_info_list = []

time_stamp = None
requirements = None
projections = None
query_time = -1
send_time = -1

# Parsing the logs to gather information
with open("/var/log/condor/CollectorLog") as fd:
    for log in fd:
        qi = QueryInfo(log)
        try:
            time_str = re.search('\A[0-9][0-9]/[0-9][0-9]/[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]', log).group(0)
            time_stamp = datetime.datetime.strptime(time_str, '%m/%d/%y %H:%M:%S')
            qi.time_stamp = time_stamp

            query_info = re.search(r"Query info.+query_time=.+send_time=.+type=.+requirements={.*?}.+projection={.*?}", log).group(0)

            query_time_str = re.search("query_time=[0-9\.]*", query_info).group(0)
            query_time = float(query_time_str[11:])
            qi.query_time = query_time

            send_time_str = re.search("send_time=[0-9\.]*", query_info).group(0)
            send_time = float(send_time_str[10:])
            qi.send_time = send_time

            query_type = re.search("type=.+?;", query_info).group(0)
            query_type = query_type[5:-1]
            qi.query_type = query_type

            requirements = re.search("requirements={.*?}", query_info).group(0)
            requirements = requirements[14:-1]
            qi.requirements = requirements

            projections = re.search("projection={.*?}", query_info).group(0)
            projections = projections[12:-1]
            projections_list = projections.split(" ")
            qi.projections = projections

            query_info_list.append(qi)
        except AttributeError:
            if log.find("Query info") != -1:
                print "Format Mismatch!\t%s" % log

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

print "Number of Query Info = %s\n" % len(query_info_list)

print "Max query_time = %s" % qtime_max
print "Average query_time = %s" % qtime_avg
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