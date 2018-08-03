import datetime
import re
import math
# import matplotlib.pyplot as plt
# import numpy as np

class Query:
    def __init__(self, query_type=None, query_time=None, constraint=None, query_pid=-1):
        self.query_type = query_type
        self.time = query_time
        self.constraint = constraint
        self.pid = query_pid

# Get time stamp for log line
def get_log_timestamp(log):
    time_sub_str = None
    time_str = None
    time_stamp = None

    try:
        time_str = re.search('\A\[.*\]\sDEBUG:', log).group(0)
        time_str = time_str[1:-8]
        # print log
        # print "%s\n" % (time_str)
        time_stamp = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S,%f')
    except AttributeError:
        print "No time stamp found : %s" % (log)

    return time_stamp

def get_log_type(log):
    if log.find("PROFILER :: CONDOR_Q :: ") != -1:
        return "condor_q"
    elif log.find("PROFILER :: EXE_CONDOR_Q :: ") != -1:
        return "exe_condor_q"
    elif log.find("PROFILER :: CONDOR_STATUS :: ") != -1:
        return "condor_status"
    elif log.find("PROFILER :: EXE_CONDOR_STATUS :: ") != -1:
        return "exe_condor_status"
    else:
        return "unknown"

def get_constraint(log):
    log.strip('\n')
    indx = log.find("CONSTRAINT = ")
    if indx != -1:
        return log[(indx + 13):]
    else:
        return None

query_frq = {}
query_frq["condor_q"] = 0
query_frq["condor_status"] = 0
query_frq["exe_condor_q"] = 0
query_frq["exe_condor_status"] = 0
query_frq["unknown"] = 0
query_id = 0

min_time = datetime.datetime.strptime("07/20/2018 14:38", "%m/%d/%Y %H:%M")
query_time = None
start_time = {}
start_time["condor_q"] = None
start_time["exe_condor_q"] = None
start_time["condor_status"] = None
start_time["exe_condor_status"] = None
start_time["unknown"] = None

query = Query(None, None)
queries = []

count = 0

constraint = {}
constraint["condor_q"] = None
constraint["condor_status"] = None
constraint["exe_condor_q"] = None
constraint["exe_condor_status"] = None
constraint["unknown"] = None

with open("profiler.log", "rb") as fd:
    for log in fd:
        pid = -1
        count += 1
        time_stamp = get_log_timestamp(log)
        log_type = get_log_type(log)
        if log_type in constraint and constraint[log_type] == None:
            constraint[log_type] = get_constraint(log)
        # TODO: identify non-constraint queries
        if time_stamp and query_time == None:
            pid_indx = log.find("PID = ")
            if pid_indx != -1:
                pid_tmp = log[(pid_indx + 6):]
                try:
                    pid = int(pid_tmp)
                except ValueError:
                    print "Not an Int: %s" % pid_tmp
            if log.find("BEGIN getCondorQConstrained()") != -1:
                print "BEGIN getCondorQConstrained() : PID = %s" % pid
                start_time["condor_q"] = time_stamp
            elif log.find("END getCondorQConstrained()") != -1 and start_time["condor_q"]:
                print "END getCondorQConstrained() : PID = %s" % pid
                query_time = time_stamp - start_time["condor_q"]
            elif log.find("BEGIN exe condor_q") != -1:
                print "BEGIN exe condor_q : PID = %s" % pid
                start_time["exe_condor_q"] = time_stamp
            elif log.find("END exe condor_q") != -1 and start_time["exe_condor_q"]:
                print "END exe condor_q : PID = %s" % pid
                query_time = time_stamp - start_time["exe_condor_q"]
            elif log.find("BEGIN getCondorStatusConstrained()") != -1:
                print "BEGIN getCondorStatusConstrained() : PID = %s" % pid
                start_time["condor_status"] = time_stamp
            elif log.find("END getCondorStatusConstrained()") != -1 and start_time["condor_status"]:
                print "END getCondorStatusConstrained() : PID = %s" % pid
                query_time = time_stamp - start_time["condor_status"]
            elif log.find("BEGIN exe condor_status") != -1:
                print"BEGIN exe condor_status : PID = %s" % pid
                start_time["exe_condor_status"] = time_stamp
            elif log.find("END exe condor_status") != -1 and start_time["exe_condor_status"]:
                print "END exe condor_status : PID = %s" % pid
                query_time = time_stamp - start_time["exe_condor_status"]
        if query_time and query_time.total_seconds() > 0.25:
            query.time = query_time
            query.query_type = log_type
            if log_type in constraint:
                query.constraint = constraint[log_type]
            else:
                query.constraint = None
            if log_type in start_time:
                query_start = start_time[log_type]
            else:
                print "No Start Time for %s" % log_type
            queries.append(query)
            print "[%s]\t%s :: %s :: %s" % (query_start, query.query_type, query_time, query.constraint)
            if query.constraint == "":
                print "UNCONSTRAINED"
            query = Query()
            query_frq[log_type] += 1
            constraint[log_type] = None
        query_time = None

#print count
print query_frq

time_stats = {}
time_stats["condor_q"] = 0
time_stats["condor_status"] = 0
time_stats["exe_condor_q"] = 0
time_stats["exe_condor_status"] = 0
time_stats["unknown"] = 0
for q in queries:
    if q.query_type in time_stats:
        time_stats[q.query_type] += q.time.total_seconds()
    else:
        print "Could not find query type: %s" % (q.query_type)

if query_frq["condor_q"] != 0:
    time_stats["condor_q"] /= query_frq["condor_q"]
else:
    time_stats["condor_q"] = None
if query_frq["condor_status"] != 0:
    time_stats["condor_status"] /= query_frq["condor_status"]
else:
    time_stats["condor_status"] = None
if query_frq["exe_condor_q"] != 0:
    time_stats["exe_condor_q"] /= query_frq["exe_condor_q"]
else:
    time_stats["exe_condor_q"] = None
if query_frq["exe_condor_status"] != 0:
    time_stats["exe_condor_status"] /= query_frq["exe_condor_status"]
else:
    time_stats["exe_condor_status"] = None

# could probably install a package like numpy and simply receive pre-rolled std dev tools
var_time_stats = {}
var_time_stats["condor_q"] = 0
var_time_stats["condor_status"] = 0
var_time_stats["exe_condor_q"] = 0
var_time_stats["exe_condor_status"] = 0
var_time_stats["unknown"] = 0
for q in queries:
    if q.query_type in var_time_stats:
        var_time_stats[q.query_type] += pow((q.time.total_seconds() - time_stats[q.query_type]), 2)
    else:
        print "Could not find query type: %s" % (q.query_type)

if query_frq["condor_q"] > 1:
    var_time_stats["condor_q"] = var_time_stats["condor_q"] / (query_frq["condor_q"] - 1)
else:
    var_time_stats["condor_q"] = None
if query_frq["condor_status"] > 1:
    var_time_stats["condor_status"] = var_time_stats["condor_status"] / (query_frq["condor_status"] - 1)
else:
    var_time_stats["condor_status"] = None
if query_frq["exe_condor_q"] > 1:
    var_time_stats["exe_condor_q"] = var_time_stats["exe_condor_q"] / (query_frq["exe_condor_q"] - 1)
else:
    var_time_stats["exe_condor_q"] = None
if query_frq["exe_condor_status"] > 1:
    var_time_stats["exe_condor_status"] = var_time_stats["exe_condor_status"] / (query_frq["exe_condor_status"] - 1)
else:
    var_time_stats["exe_condor_status"] = None

print "Averages\t%s" % (time_stats)
print "Variance\t%s" % (var_time_stats)
fd.close()
