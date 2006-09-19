#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import condorMonitor

#
# Return a dictionary of schedds containing idle jobs
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getIdleCondorQ(schedd_names,constraint=None):
    out_condorq_dict={}
    for schedd in schedd_names:
        condorq=condorMonitor.CondorQ(schedd)
        idle_constraint="JobStatus==1"
        if constraint!=None:
            idle_constraint="(%s) && (%s)"%(idle_constraint,constraint)

        condorq.load(idle_constraint)
        if len(condorq.fetchStored())>0:
            out_condorq_dict[schedd]=condorq
    return out_condorq_dict

#
# Get the number of jobs that match each glidein
#
# match_str = '(job["MIN_NAME"]<glidein["MIN_NAME"]) && (job["ARCH"]==glidein["ARCH"])'
# condorq_dict = output of getidlqCondorQ
# glidein_dict = output of interface.findGlideins
#
# Returns:
#  dictionary of glidein name
#   where elements are number of idle jobs matching
def countMatchIdle(match_str,condorq_dict,glidein_dict):
    out_glidein_counts={}
    for glidename in glidein_dict:
        glidein=glidein_dict[glidename]
        glidein_count=0
        for schedd in condorq_dict.keys():
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            schedd_count=0
            for jid in condorq_data.keys():
                job=condorq_data[jid]
                if eval(match_str):
                    schedd_count+=1
                pass
            glidein_count+=schedd_count
            pass
        out_glidein_counts[glidename]=glidein_count
        pass
    return out_glidein_counts


############################################################
#
# I N T E R N A L - Do not use
#
############################################################

