import datetime
import re
import math
# import matplotlib.pyplot as plt
# import numpy as np

class Query:
    def __init__(self, query_type=None, start_time=None, query_time=None, constraint=None, query_pid=-1):
        self.query_type = query_type
        self.start_time = start_time
        self.query_time = query_time
        self.constraint = constraint
        self.query_pid = query_pid

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
    if log.find("CONDOR_Q :: ") != -1:
        return "condor_q"
    elif log.find("EXE_CONDOR_Q :: ") != -1:
        return "exe_condor_q"
    elif log.find("CONDOR_STATUS :: ") != -1:
        return "condor_status"
    elif log.find("EXE_CONDOR_STATUS :: ") != -1:
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


constraint = {};
constraint["condor_q"] = None
constraint["condor_status"] = None
constraint["exe_condor_q"] = None
constraint["exe_condor_status"] = None
constraint["unknown"] = None

schedds_count = 0

file_name = "/var/log/gwms-frontend/group_main/main.err.log"
with open(file_name, "rb") as fd:
    for log in fd:
        pid = -1
        count += 1
        time_stamp = get_log_timestamp(log)
        log_type = get_log_type(log)
        if log_type in constraint and constraint[log_type] == None:
            constraint[log_type] = get_constraint(log)
        # TODO: identify non-constraint queries        
        try:
            py_bindings = re.search("USE_PYTHON_BINDINGS = (True|False) ::", log).group(0)
            use_python_bindings = (py_bindings.find("True") != -1)
        except AttributeError:
            use_python_bindings = None
            pass

        if time_stamp and query_time == None:
            pid_indx = log.find("PID = ")
            if pid_indx != -1:
                pid_tmp = log[(pid_indx + 6):]
                try:
                    pid = int(pid_tmp)
                except ValueError:
                    print "Not an Int: %s" % pid_tmp
            if log.find("BEGIN getCondorQConstrained()") != -1:
                start_time["condor_q"] = time_stamp
                use_python_bindings["condor_q"] = use_python_bindings

            elif log.find("END getCondorQConstrained()") != -1 and start_time["condor_q"]:
                query_time = time_stamp - start_time["condor_q"]

            elif log.find("BEGIN exe_condor_q") != -1:
                start_time["exe_condor_q"] = time_stamp
                use_python_bindings["exe_condor_q"] = use_python_bindings

            elif log.find("END exe_condor_q") != -1 and start_time["exe_condor_q"]:
                query_time = time_stamp - start_time["exe_condor_q"]

            elif log.find("BEGIN getCondorStatusConstrained()") != -1:
                start_time["condor_status"] = time_stamp
                use_python_bindings["condor_status"] = use_python_bindings

            elif log.find("END getCondorStatusConstrained()") != -1 and start_time["condor_status"]:
#                print "END getCondorStatusConstrained() : PID = %s" % pid
                query_time = time_stamp - start_time["condor_status"]

            elif log.find("BEGIN exe_condor_status") != -1:
#                print"BEGIN exe condor_status : PID = %s" % pid
                start_time["exe_condor_status"] = time_stamp
                use_python_bindings["exe_condor_status"] = use_python_bindings

            elif log.find("END exe_condor_status") != -1 and start_time["exe_condor_status"]:
                print "END exe condor_status : PID = %s" % pid
                query_time = time_stamp - start_time["exe_condor_status"]

        if query_time and query_time.total_seconds() > 0.25:
            query.query_time = query_time
            query.query_type = log_type
            query.start_time = start_time[log_type] if log_type in start_time else None
            query.use_python_bindings = use_python_bindings[log_type] if log_type in use_pythong_bindings else None
            query.constraint = constraint[log_type] if log_type in constraint else "UNCONSTRAINED"
            queries.append(query)

            print "[%s]\t%s :: %s :: %s" % (query.start_time, query.query_type, query.query_time, query.constraint)
            query = Query()
            query_frq[log_type] += 1
            constraint[log_type] = None
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

python_bindings_stats = [q for q in queries if (q.use_python_binding != None)]
use_python_binding_stats = [q for q in python_binding_stats if (q.use_python_binding)]
no_python_binding_stats = [q for q in python_binding_stats if (not q.use_python_binding)]

for qt in query_types:
    use_python_binding[qt] = [q for q in use_python_binding_stats if (q.query_type == qt)]
    no_python_binding[qt] = [q for q in no_python_binding_stats if (q.query_type == qt)]

    if size(use_python_binding[qt]) > 0:
        use_python_binding_avg[qt] = sum(use_python_binding[qt])/size(use_python_binding[qt])
    else:
        print "No queries use Python Bindings with query_type = %s" % qt

    if size(no_python_binding[qt]) > 0:
        no_python_binding_avg[qt] = sum(no_python_binding[qt])/size(no_python_binding[qt])
    else:
        print "No queries use No Python Bindings with query_type = %s" % qt

print "Use Python Binding Averages\t%s" % use_python_binding_avg
print "No Python Binding Averages\t%s" % no_python_binding_avg
fd.close()
