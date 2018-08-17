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
        out_str += " query_pid = %s;" % self.query_pid
        out_str += " time_stamp = %s;" % datetime.strftime(self.time_stamp, "%Y-%m-%d %H:%M:%S")
        out_str += " query_time = %s;" % self.query_time
        out_str += " send_time = %s;" % self.send_time
        out_str += " type = %s;" % self.query_info_type
        out_str += " requirements = %s;" % self.requirements
        out_str += " projections = {%s};" % self.projections

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

def get_cached_queries(in_file_name, query_types_list, query_info_types_list, requirements_list, projections_list):
    query_list = []
    with open(in_file_name, "r") as in_file:
        for line in in_file:
            qi = QueryInfo()
            error_check = ""
            try:
                query_type = re.search("query_type = .*?;", line).group(0)
                if query_types_list == None or query_type in query_types_list:
                    q.query_type = query_type[13:-1]
                else:
                    continue

                query_pid = re.search("query_pid = (-)?[0-9]*?;", line).group(0)
                qi.query_pid = int(re.search("(-)?[0-9]+", query_pid).group(0))

                time_stamp_str = re.search("time_stamp = .*?;", line).group(0)
                qi.time_stamp = datetime.strptime(time_stamp_str[13:-1], '%Y-%m-%d %H:%M:%S')

                query_time = re.search("query_time = (-)?([0-9\.]+)([eE](-)?[0-9]+)?", line).group(0)
                qi.query_time = float(query_time[13:])

                send_time = re.search("send_time = (-)?([0-9\.]+)([eE](-)?[0-9]+)?", line).group(0)
                qi.send_time = float(send_time[12:])

                query_info_type = re.search("type = .*?;", line).group(0)
                if query_info_types_list == None or query_info_type[7:-1] in query_info_types_list`
                    qi.query_info_type = query_info_type[7:-1]
                else:
                    continue

                constraint = re.search("requirements = .*?;", line).group(0)
                if requirements_list == None or constraint[15:-1] in requirements_list:
                    qi.constraint = constraint[15:-1]
                else:
                    continue

                projection = re.search("projections = {.*?};", line).group(0)
                if projections_list == None or projection[15:-2] in projections_list:
                    qi.constraint = projection[15:-2]
                else:
                    continue

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
                        query_type_pid_str = re.search("MyType[\s]*=!=[\s]*\"(exe_condor_status_|condor_status_|exe_condor_q_|condor_q_)(-)?[0-9]+\"", requirements).group(0)
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

def arg_parse():
    args_parser = argparse.ArgumentParser()
    subparsers = args_parser.add_subparsers(help='sub-command help', dest='command')

    parent_parser = argparse.ArgumentParser(add_help=False)

    log_parser = subparsers.add_parser('parse', parents=[parent_parser])
    log_parser.add_argument('parse', metavar='F', nargs='?', default='/var/log/condor/CollectorLog', help='specifies the file path of a condor log file to parse and write to; defaults to /var/log/CollectorLog')
    log_parser.add_argument('--out', dest='cache_file', default='', help='specifies the name of the cache file where the results of parsing a log file will be written inside the directory glideinwms/profiler_tools/condor_cache')

    stats_parser = subparsers.add_parser('stats', parents=[parent_parser])
    stats_parser.add_argument('stats', metavar='F', help='specifies a queries cache_file from which statistics will be generated')
    stats_parser.add_argument('--query_types', metavar='Q', dest='query_types', type=str, nargs='*', help='list of strings specifying that only queries with the given query_type(s) will be included in the results')
    stats_parser.add_argument('--query_info_types', metavar='QI', dest='query_info_types', type=str, nargs='*', help='list of strings specifying that only queries with the given query_info_type(s) will be included in the results')
    stats_parser.add_argument('--constraints', metavar='C', dest='constraints', type=str, nargs='*', help='list of strings specifying that only queries with the given constraint(s) will be included in the results')
    stats_parser.add_argument('--projections', metavar='P', dest='projections', type=str, nargs='*', help='list of strings specifying that only queries with the given projection(s) will be included in the results')

def main():
    args = arg_parse()
    if args.command == 'parse':
        print args.query_types
        print args.constraints
        query_list = parse_frontend_logs(args.parse)
        print "Completed parsing %s" % args.parse
        out_file_path = cache_queries(query_list, args.cache_file)
    elif args.command == 'stats':
        query_list = get_cached_queries(args.stats, args.query_types, args.query_info_types, args.constraints, args.projections)
        query_dict = build_query_info_dict(query_list)
        for k in query_dict:
            query_times_list = [q.query_time for q in query_dict[k]]
            send_times_list = [q.send_time for q in query_dict[k]]
            get_query_stats(query_times_list)

main()