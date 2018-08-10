#import profile_parser.Query
#import Collector_Log_Parser.QueryInfo
import datetime
import re
from operator import attrgetter

class Query:
    def __init__(self, query_type=None, start_time=datetime.date(1, 1, 1), query_time=None, constraint=None, query_pid=-1):
        self.query_type = query_type
        self.start_time = start_time
        self.query_time = query_time
        self.constraint = constraint
        self.query_pid = query_pid

class QueryInfo:
    def __init__(self, log, time_stamp=datetime.date(1, 1, 1), query_time=None, send_time=None, query_type=None, requirements=None, projections=None, query_pid = -1):
        self.log = log.strip()
        self.time_stamp = time_stamp
        self.query_time = query_time
        self.send_time = send_time
        self.query_type = query_type
        self.requirements = requirements
        self.projections = projections
        self.query_pid = query_pid

    def __str__(self):
        return "time_stamp:\t%squery_time:\t%f\nsend_time:\t%f\nquery_type:\t%s\nrequirements:\t%s\nprojections:\t%s\n" % (self.time_stamp, self.query_time, self.send_time, self.query_type, self.requirements, self.projections)

def frontend_get_log_type(log):
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

def frontend_get_constraint(log):
    log.strip('\n')
    indx = log.find("CONSTRAINT = ")
    if indx != -1:
        return log[(indx + 13):]
    else:
        return None

def frontend_parse_time(log):
    time_Stamp = None
    try:
        time_str = re.search('\A\[.*\]\sDEBUG:', log).group(0)
        time_str = time_str[1:-8]
        time_stamp = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S,%f')
    except AttributeError:
        print "No time stamp found : %s" % log

    return time_stamp

def parse_time_condor_logs(log):
    try:
        time_str = re.search('\A[0-9][0-9]/[0-9][0-9]/[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]', log).group(0)
        time_stamp = datetime.datetime.strptime(time_str, '%m/%d/%y %H:%M:%S')
        qi.time_stamp = time_stamp
    except AttributeError:
        print "No time stamp found : %s" % log

def build_frontend_queries(frontend_log_file_name="/var/log/gwms-frontend/group_main/main.all.log"):
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

    with open(frontend_log_file_name, "rb") as fd:
        for log in fd:
            if "PROFILER :: " in log:
                pid = -1
                time_stamp = frontend_parse_time(log)
                log_type = frontend_get_log_type(log)
                if log_type in constraint and constraint[log_type] == None:
                    constraint[log_type] = frontend_get_constraint(log)
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
                query.query_pid = pid
                queries.append(query)

                query = Query()
                query_frq[log_type] += 1
                constraint[log_type] = None
            query_time = None

    return queries


def build_condor_queries(condor_log_file_name="/var/log/condor/CollectorLog"):
    query_info_list = []

    with open(condor_log_file_name) as fd:
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

                try:
                    query_type_pid = re.search(r"(exe_)?condor_(status|q)_[0-9]+", requirements).group(0)
                    qi.query_pid = int(re.search("[0-9]+", query_type_pid).group(0))
                except AttributeError:
                    qi.query_pid = -1

                projections = re.search("projection={.*?}", query_info).group(0)
                projections = projections[12:-1]
                projections_list = projections.split(" ")
                qi.projections = projections

                query_info_list.append(qi)
            except AttributeError:
                if log.find("Query info") != -1:
                    print "Format Mismatch!\t%s" % log

    return query_info_list

"""
Function to order both query_info and query_list, and then to determine whether the orderings are in agreement
Need to make a judgement call... determine whether to 
"""
def order_queries(query_info_list, query_list):
    # Sort both lists by the Process ID, then by start_time
    grouped_query_info = sorted(query_info_list, key=attrgetter("query_pid", "time_stamp"))
    grouped_query_list = sorted(query_list, key=attrgetter("query_pid", "start_time"))

    in_sync = True
    iter_max = min(len(grouped_query_info), len(grouped_query_list))
    for i in range(iter_max):
        qi = grouped_query_info[i]
        q = grouped_query_list[i]
        if (qi.query_pid != q.query_pid or qi.query_type != q.query_type) and in_sync:
            in_sync = False
            iter_max = min(iter_max, i + 5)
            print "Frontend and Condor Logs Are Not in Agreement, printing next five list members"
        elif in_sync:
            print "query_info %d{3}:  pid = %s\t\tquery %d{3}:  pid = %s" % (i, grouped_query_info[i].query_pid, grouped_query_list[i].query_pid)
            print "query_info %d{3}: time = %s\t\tquery %d{3}: time = %s" % (i, qi.query_time, q.query_time)
            print "query_info %d{3}: type = %s\t\tquery %d{3}: type = %s" % (i, qi.query_type, q.query_type)
        else:
            print "query_info %d{3}: %s: %s %s; %s; %s" % (i, qi.query_pid, qi.time_stamp, qi.query_type, qi.requirements, qi.projections)
            print "query      %d{3}: %s: %s %s; %s" % (i, q.query_pid, q.start_time, q.query_type, q.constraint)

query_list = build_frontend_queries()
query_info_list = build_condor_queries()

order_queries(query_info_list, query_list)
