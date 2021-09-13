#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# Description:
#   profile the countMatch frontend function
#   Uncomment lines in glideinFrontendElement.subprocess_count_dt to get the data to execute this script
#
# Author:
#   Marco Mascheroni
#

from __future__ import print_function

import os
import sys
import glob
import pickle
import cProfile

from glideinwms.lib import logSupport
from glideinwms.frontend.glideinFrontendLib import countMatch

# Replicating the class since this should be executed standalone on a production frontend
class FakeLogger(object):
    """
    Super simple logger for the unittests
    """

    def __init__(self, afile=sys.stderr):
        self.file = afile
        pass

    def debug(self, msg, *args):
        """
        Pass a debug message to stderr.

        Prints out msg % args.

        @param msg: A message string.
        @param args: Arguments which should be evaluated into the message.
        """
        print(str(msg) % args, file=self.file)

    def info(self, msg, *args):
        """
        Pass an info-level message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=self.file)

    def warning(self, msg, *args):
        """
        Pass a warning-level message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=self.file)

    def error(self, msg, *args):
        """
        Pass an error message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=self.file)

    def exception(self, msg, *args):
        """
        Pass an exception message to stderr.

        @see: debug
        """
        print(str(msg) % args, file=self.file)


class mock_condorq_el:
    def __init__(self, obj):
        self.obj = obj
    def fetchStored(self):
        return self.obj


def main():
    # Need to be global for cProfile to work
    global cexpr, condorq_dict, glidein_dict, attr_dict, condorq_match_list
    dumpdir = "/tmp/frontend_dump/main/" # This will profile the main group. Change it to profile another one
    # The CMS matching expression as of April 17th 2019
    mexpr = """(((glidein["attrs"].get("GLIDEIN_MaxMemMBs", 0) == 0) or (job.get("RequestMemory", 0)<=glidein["attrs"]["GLIDEIN_MaxMemMBs"])) and ((job.get("REQUIRED_OS", "any")=="any") or (glidein["attrs"].get("GLIDEIN_REQUIRED_OS", "any")=="any") or (job.get("REQUIRED_OS")==glidein["attrs"]["GLIDEIN_REQUIRED_OS"])) and ((job.get("MaxWallTimeMins", 0)*60)>=glidein["attrs"].get("GLIDEIN_Job_Min_Time", 0)) and ((job.get("MaxWallTimeMins", 0)+10)<(glidein["attrs"]["GLIDEIN_Max_Walltime"]-glidein["attrs"]["GLIDEIN_Retire_Time_Spread"])/60))"""
    logSupport.log = FakeLogger()

    # Load the saved dictionaries
    with open(os.path.join(dumpdir, 'glidein_dict.pickle')) as fd:
        glidein_dict = pickle.load(fd)
    with open(os.path.join(dumpdir, 'attr_dict.pickle')) as fd:
        attr_dict= pickle.load(fd)
    with open(os.path.join(dumpdir, 'condorq_match_list.pickle')) as fd:
        condorq_match_list = pickle.load(fd)

    cexpr = compile(mexpr, "<string>", "eval")

    # The condor_q dictionary names depend on the schedd names, use glob to get them
    cwd = os.getcwd()
    os.chdir(dumpdir)
    qdicts = glob.glob("condorq_dict*.pickle")
    os.chdir(cwd)

    condorq_dict = {}
    for schedd_name in qdicts:
        with open(os.path.join(dumpdir, schedd_name)) as fd:
            condorq_dict[schedd_name] = mock_condorq_el(pickle.load(fd))

    print("Frontend dump loaded")

    cProfile.run('countMatch(cexpr, condorq_dict, glidein_dict, attr_dict, condorq_match_list)')


if __name__ == "__main__":
    main()
