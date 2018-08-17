import datetime
import re
import copy
import os
import argparse
import errno
import numpy as np

class Query:
    def __init__(self, query_type="unknown", start_time=datetime.date(1900, 1, 1), end_time=datetime.date(1900, 1, 1), query_time=-1, constraint=None, query_pid=-1, use_python_bindings=None):
        self.query_type = query_type
        self.start_time = start_time
        self.end_time = end_time
        self.query_time = query_time
        self.constraint = constraint
        self.query_pid = query_pid
        self.use_python_bindings = use_python_bindings
        self.error = ""

    def __repr__(self):
        out_str = "query_type = %s;" % self.query_type
        out_str += " query_pid = %s;" % self.query_pid
        out_str += " start_time = %s;" % datetime.datetime.strftime(self.start_time, '%Y-%m-%d %H:%M:%S,%f')
        out_str += " end_time = %s;" % datetime.datetime.strftime(self.end_time, '%Y-%m-%d %H:%M:%S,%f')
        out_str += " query_time = %s;" % self.query_time
        out_str += " constraint = %s;" % self.constraint
        out_str += " use_python_bindings = %s;" % self.use_python_bindings
        if self.error:
            out_str += str(self.error)

        return out_str

def get_time_stamp(log):
    timestamp = None
    try:
        time_stamp_str = re.search("^\[[0-9\-\s:,]*\]", log).group(0)
        time_stamp_str = time_stamp_str[1:-1]
        time_stamp = datetime.datetime.strptime(time_stamp_str, '%Y-%m-%d %H:%M:%S,%f')
    except AttributeError:
        print "Either no timestamp found or timestamp misformated: %s" % log

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

def get_query_type(log):
    try:
        query_type_str = re.search(" (CONDOR_Q|EXE_CONDOR_Q|CONDOR_STATUS|EXE_CONDOR_STATUS) :: ", log).group(0)
        return query_type_str[1:-4].lower()
    except AttributeError:
        return "unknown"

def parse_frontend_logs(log_file_name):
    query_list = []
    query_endpts_regex = "(getCondorQConstrained\(\)|getCondorStatusConstrained\(\)|exe_condor_q|exe_condor_status)"
#    query_types = {"getCondorQConstrained()" : "condor_q", "exe_condor_q" : "exe_condor_q",
#    "getCondorStatusConstrained()" : "condor_status", "exe_condor_status" : "exe_condor_status", "unknown" : "unknown"}
    type_dict = {}

    q = Query()
    with open(log_file_name, "r") as fd:
        for log in fd:
            pid = -1
            query_time = -1
            if log.find("PROFILER ::") != -1:
                query_type = get_query_type(log)
                timestamp = get_time_stamp(log)
                try:
                    pid_str = re.search("PID = (-)?[0-9]+", log).group(0)
                    pid = int(re.search("(-)?[0-9]+", pid_str).group(0))
                except AttributeError:
                    pid = -1

                try:
                    constraint_str = re.search("CONSTRAINT = .*( ::)?", log).group(0)
                    try:
                        # Remove bogus constraint, which was added for getting query_type and PID in condor logs, so that queries with common constraints can be compared
                        if pid == -1:
                            pid_str = re.search("\(MyType=!=\"(condor_q|exe_condor_q|condor_status|exe_condor_status)_(-)?[0-9]+\"\)", constraint_str).group(0)
                            pid = int(re.search("(-)?[0-9]+", pid_str).group(0))
                        constraint_str = re.sub("&& \(MyType=!=\"(condor_q|exe_condor_q|condor_status|exe_condor_status)_(-)?[0-9]+\"\)", "", constraint_str).strip()
                    except AttributeError:
                        if constraint_str.find("MyType=!=\"condor_") != -1 or constraint_str.find("Mytype=!=\"exe_condor_") != -1:
                            print "Constraint marker does not appear properly configured: %s" % constraint_str
                    constraint = constraint_str[13:]

                    if pid in type_dict[query_type]:
                        type_dict[query_type][pid].constraint = constraint
                except AttributeError:
                    constraint = ""

                try:
                    begin_str = re.search("BEGIN %s :: " % query_endpts_regex, log).group(0)
                    q.query_type = query_type
                    q.start_time = timestamp
                    q.query_pid = pid
                    if query_type not in type_dict:
                        type_dict[query_type] = {}

                    if pid != -1:
                        type_dict[query_type][pid] = copy.copy(q)
                    q = Query()
                except AttributeError:
                    if log.find("BEGIN") != -1 and log.find("condor_advertise") == -1:
                        print "Error in parsing profiler BEGIN"

                try:
                    end_str = re.search("END %s :: " % query_endpts_regex, log).group(0)
                    if pid in type_dict[query_type]:
                        q = copy.copy(type_dict[query_type][pid])
                        q.end_time = timestamp
                        q.query_time = (timestamp - type_dict[query_type][pid].start_time).total_seconds()
                        query_list.append(q)
                    elif pid != -1:
                        print "No associated start time for query_type = %s and query_pid = %s" % (query_type, pid)
                    q = Query()
                except AttributeError:
                    if log.find("END") != -1 and log.find("condor_advertise") == -1:
                        print "Error in parsing profiler END"

    return query_list

"""
Separate queries are line separated, and separate properties of a query are separated by semicolons
"""
def cache_queries(query_list, out_file_name=""):
    if not os.path.exists("%s/frontend_cache" % os.path.dirname(__file__)):
        try:
            os.makedirs("%s/frontend_cache" % os.path.dirname(__file__))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    if out_file_name == "" and len(query_list) > 0:
        min_time = min([q.start_time for q in query_list])
        max_time = max([q.end_time for q in query_list])
        out_file_name = "Frontend_Queries %s-%s" % (datetime.datetime.strftime(min_time, '%Y-%m-%d %H %M %S'), datetime.datetime.strftime(max_time, '%Y-%m-%d %H %M %S'))
        print os.path.dirname(os.path.realpath(__file__))
    elif len(query_list) == 0:
        print "No queries in list"
        return None

    out_file_path = "%s/frontend_cache/%s" % (os.path.dirname(__file__), out_file_name)
    if os.path.exists(out_file_path):
        print "File with name %s already exists" % out_file_name
    else:
        with open(out_file_path, "w+") as out_file:
            query_list_str = [str(qi) for qi in query_list]
            query_str = "\n".join(query_list_str)
            out_file.write(str(query_str))
        print "Queries cached in %s" % out_file_path

    return out_file_path

def get_cached_queries(in_file_name, query_types_list, constraints_list):
    query_list = []
    if os.path.exists(in_file_name):
        with open(in_file_name, "r") as in_file:
            for line in in_file:
                q = Query()
                try:
                    query_type = re.search("query_type = .*?;", line).group(0)
                    if query_types_list == None or query_type[13:-1] in query_types_list:
                        q.query_type = query_type[13:-1]
                    else:
                        continue

                    query_pid = re.search("query_pid = (-)?[0-9]+?;", line).group(0)
                    q.query_pid = int(re.search("(-)?[0-9]+", query_pid).group(0))

                    start_time_str = re.search("start_time = .*?;", line).group(0)
                    q.start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S,%f')

                    end_time_str = re.search("end_time = .*?;", line).group(0)
                    q.end_time = datetime.striptime(start_time_str, '%Y-%m-%d %H:%M:%S,%f')

                    query_time = re.search("query_time = (-)?([0-9\.]+)([eE](-)?[0-9]+)?;", line).group(0)
                    q.query_time = float(re.search("(-)?([0-9\.]+)([eE](-)?[0-9]+)?", query_time).group(0))

                    constraint = re.search("constraint = .*?;", line).group(0)
                    if constraints_list == None or constraint[13:-1] in constraints_list:
                        q.constraint = constraint[13:-1]
                    else:
                        continue

                    use_python_bindings = re.search("use_python_bindings = (True|False|None);", line).group(0)
                    q.use_python_bindings = re.search("(True|False|None)", use_python_bindings).group(0)
                except AttributeError:
                    q.error = "Error drawing from cache: " + line

                query_list.append(q)
    else:
        print "File %s not found" % in_file_name
    return query_list

def build_query_dict(query_list):
    query_dict = {}
    for q in query_list:
        key = "%s; %s" % (q.query_type, q.constraint)
        if key not in query_dict:
            query_dict[key] = list()
        query_dict[key].append(q)

    return query_dict

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

def arg_parse():
    args_parser = argparse.ArgumentParser()
    subparsers = args_parser.add_subparsers(help='sub-command help', dest='command')

    parent_parser = argparse.ArgumentParser(add_help=False)

    log_parser = subparsers.add_parser('parse', parents=[parent_parser])
    log_parser.add_argument('parse', metavar='F', nargs='?', default='/var/log/gwms-frontend/group_main/main.all.log', help='specifies the file path of a frontend log file to parse and write to; defaults to /var/log/gwms-frontend/group_main/main.all.log')
    log_parser.add_argument('--out', dest='cache_file', default='', help='specifies the name of the cache file where the results of parsing a log file will be written inside the directory glideinwms/profiler_tools/frontend_cache')

    stats_parser = subparsers.add_parser('stats', parents=[parent_parser])
    stats_parser.add_argument('stats', metavar='F', help='specifies a queries cache_file from which statistics will be generated')
    stats_parser.add_argument('--query_types', metavar='Q', dest='query_types', type=str, nargs='*', help='list of strings specifying that only queries with the given query_type(s) will be included in the results')
    stats_parser.add_argument('--constraints', metavar='C', dest='constraints', type=str, nargs='*', help='list of strings specifying that only queries with the given constraint(s) will be included in the results')

    args = args_parser.parse_args()
    return args

def main():
    args = arg_parse()
    if args.command == 'parse':
        query_list = parse_frontend_logs(args.parse)
        print "Completed parsing %s" % args.parse
        out_file_path = cache_queries(query_list, args.cache_file)
    elif args.command == 'stats':
        query_list = get_cached_queries(args.stats, args.query_types, args.constraints)
        print [q for q in query_list if (q.query_time == -1)]
        query_dict = build_query_dict(query_list)
        for k in query_dict:
            query_times_list = [q.query_time for q in query_dict[k]]
            get_query_stats(query_times_list, k)
main()

#query_list = parse_frontend_logs("/Users/jlundell/Documents/main.all.log")
#query_dict = build_query_dict(query_list)
#cached_queries_file = cache_queries(query_list)
#query_list_cached = get_cached_queries(cached_queries_file)