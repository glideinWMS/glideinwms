import datetime
import re
import math
# import matplotlib.pyplot as plt
# import numpy as np

class Query:
    def __init__(self, query_type=None, start_time=None, query_time=None, constraint=None, query_pid=-1, use_python_bindings=None):
        self.query_type = query_type
        self.start_time = start_time
        self.query_time = query_time
        self.constraint = constraint
        self.query_pid = query_pid
        self.use_python_bindings = use_python_bindings

    def __str__(self):
        return "[%s]; query_type = %s; query_time = %s; constraint = %s; query_pid = %s" % (self.start_time, self.query_type, self.query_time, self.constraint, self.query_pid)

# Get time stamp for log line
def get_log_timestamp(log):
    time_sub_str = None
    time_str = None
    time_stamp = None

    try:
        time_str = re.search('^\[.*\]\sDEBUG:', log).group(0)
        time_str = time_str[1:-8]
        time_stamp = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S,%f')
    except AttributeError:
        if log.find("DEBUG:") != -1:
            print "No time stamp found : %s" % (log)

    return time_stamp

def get_log_type(log):
    if log.find(" CONDOR_Q :: ") != -1:
        return "condor_q"
    elif log.find(" EXE_CONDOR_Q :: ") != -1:
        return "exe_condor_q"
    elif log.find(" CONDOR_STATUS :: ") != -1:
        return "condor_status"
    elif log.find(" EXE_CONDOR_STATUS :: ") != -1:
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

query_types = ["condor_q", "condor_status", "exe_condor_q", "exe_condor_status"]

query_frq = {}
query_frq["condor_q"] = 0
query_frq["condor_status"] = 0
query_frq["exe_condor_q"] = 0
query_frq["exe_condor_status"] = 0
query_frq["unknown"] = 0
query_id = 0

#min_time = datetime.datetime.strptime("07/20/2018 14:38", "%m/%d/%Y %H:%M")
query_time = None
start_time = {}
start_time["condor_q"] = None
start_time["exe_condor_q"] = None
start_time["condor_status"] = None
start_time["exe_condor_status"] = None
start_time["unknown"] = None

query = Query(None, None)
queries = []

constraint = {};
constraint["condor_q"] = None
constraint["condor_status"] = None
constraint["exe_condor_q"] = None
constraint["exe_condor_status"] = None
constraint["unknown"] = None

use_python_bindings_dict = {}

file_name = "/var/log/gwms-frontend/group_main/main.all.log"
with open(file_name, "rb") as fd:
    for log in fd:
        if "PROFILER :: " in log:
            pid = -1
            time_stamp = get_log_timestamp(log)
            log_type = get_log_type(log)
            if log_type in constraint and constraint[log_type] == None:
                constraint[log_type] = get_constraint(log)
            # TODO: identify non-constraint queries
            if time_stamp and query_time == None:
                try:
                    pid_str = re.search("PID = [0-9]+", log).group(0)
                    try:
                        pid = int(pid_str[7:])
                    except ValueError:
                        pid = -1
                        print "Not an Int: %s" % pid_str[7:]
                except AttributeError:
                    pid = -1

                if log.find("BEGIN getCondorQConstrained()") != -1:
                    start_time["condor_q"] = time_stamp

                elif log.find("END getCondorQConstrained()") != -1 and start_time["condor_q"]:
                    query_time = time_stamp - start_time["condor_q"]

                elif log.find("BEGIN exe_condor_q") != -1:
                    try:
                        py_bindings_str = re.search("USE_HTCON(D)?OR_PYTHON_BINDINGS = (True|False)", log).group(0)
                        py_bindings = ("True" in py_bindings_str)
                        print log
                    except AttributeError:
                        py_bindings = None
                    start_time["exe_condor_q"] = time_stamp
                    use_python_bindings_dict["exe_condor_q"] = py_bindings

                elif log.find("END exe_condor_q") != -1 and start_time["exe_condor_q"]:
                    query_time = time_stamp - start_time["exe_condor_q"]

                elif log.find("BEGIN getCondorStatusConstrained()") != -1:
                    start_time["condor_status"] = time_stamp

                elif log.find("END getCondorStatusConstrained()") != -1 and start_time["condor_status"]:
                    query_time = time_stamp - start_time["condor_status"]

                elif log.find("BEGIN exe_condor_status") != -1:
                    try:
                        py_bindings_str = re.search("USE_HTCON(D)?OR_PYTHON_BINDINGS = (True|False)", log).group(0)
                        py_bindings = ("True" in py_bindings_str)
                        print log
                    except AttributeError:
                        py_bindings = None
                    start_time["exe_condor_status"] = time_stamp
                    use_python_bindings_dict["exe_condor_status"] = py_bindings

                elif log.find("END exe_condor_status") != -1 and start_time["exe_condor_status"]:
                    query_time = time_stamp - start_time["exe_condor_status"]

        if query_time:
            query.query_time = query_time
            query.query_type = log_type
            query.start_time = start_time[log_type] if log_type in start_time else None
            query.use_python_bindings = use_python_bindings_dict[log_type] if log_type in use_python_bindings_dict else None
            query.constraint = constraint[log_type] if log_type in constraint else "UNCONSTRAINED"
            queries.append(query)

            #print "[%s]\t%s :: %s :: %s" % (query.start_time, query.query_type, query.query_time, query.constraint)
            query = Query()
            query_frq[log_type] += 1
            constraint[log_type] = None
            use_python_bindings_dict[log_type] = None
        query_time = None

print query_frq

# Calculate Averages
time_stats = {}
time_stats["condor_q"] = 0
time_stats["condor_status"] = 0
time_stats["exe_condor_q"] = 0
time_stats["exe_condor_status"] = 0
time_stats["unknown"] = 0

for q in queries:
    if q.query_type in time_stats:
        time_stats[q.query_type] += q.query_time.total_seconds()
    else:
        print "Could not find query type: %s" % (q.query_type)

if query_frq["condor_q"] != 0:
    time_stats["condor_q"] /= query_frq["condor_q"]
else:
    time_stats["condor_q"] = 0
if query_frq["condor_status"] != 0:
    time_stats["condor_status"] /= query_frq["condor_status"]
else:
    time_stats["condor_status"] = 0
if query_frq["exe_condor_q"] != 0:
    time_stats["exe_condor_q"] /= query_frq["exe_condor_q"]
else:
    time_stats["exe_condor_q"] = 0
if query_frq["exe_condor_status"] != 0:
    time_stats["exe_condor_status"] /= query_frq["exe_condor_status"]
else:
    time_stats["exe_condor_status"] = 0

# Calculate variances
var_time_stats = {}
var_time_stats["condor_q"] = 0
var_time_stats["condor_status"] = 0
var_time_stats["exe_condor_q"] = 0
var_time_stats["exe_condor_status"] = 0
var_time_stats["unknown"] = 0
for q in queries:
    if q.query_type in var_time_stats:
        var_time_stats[q.query_type] += pow((q.query_time.total_seconds() - time_stats[q.query_type]), 2)
    else:
        print "Could not find query type: %s" % (q.query_type)


for qt in query_types:
    if query_frq[qt] > 1:
        var_time_stats[qt] = var_time_stats[qt] / (query_frq[qt] - 1)
    else:
        var_time_stats[qt] = None

print "Averages\t%s" % (time_stats)
print "Variance\t%s" % (var_time_stats)

python_binding_stats = [q for q in queries if (q.use_python_bindings != None)]
use_python_binding_stats = [q for q in python_binding_stats if (q.use_python_bindings)]
no_python_binding_stats = [q for q in python_binding_stats if (not q.use_python_bindings)]
#print python_binding_stats
#print use_python_binding_stats
#print no_python_binding_stats

use_python_binding = {}; use_python_binding_avg = {}
no_python_binding = {}; no_python_binding_avg = {}

for qt in ["exe_condor_status", "exe_condor_q"]:
    use_python_binding[qt] = [q.query_time.total_seconds() for q in use_python_binding_stats if (q.query_type == qt)]
    no_python_binding[qt] = [q.query_time.total_seconds() for q in no_python_binding_stats if (q.query_type == qt)]

    if len(use_python_binding[qt]) > 0:
        use_python_binding_avg[qt] = sum(use_python_binding[qt])/len(use_python_binding[qt])
    else:
        print "No queries use Python Bindings with query_type = %s" % qt

    if len(no_python_binding[qt]) > 0:
        no_python_binding_avg[qt] = sum(no_python_binding[qt])/len(no_python_binding[qt])
    else:
        print "No queries use No Python Bindings with query_type = %s" % qt

print "Use Python Binding Averages\t%s" % use_python_binding_avg
print "No Python Binding Averages\t%s" % no_python_binding_avg
fd.close()
