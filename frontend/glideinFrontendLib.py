#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements the functions needed to keep the
#   required number of idle glideins
#   plus other miscelaneous functions
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import os.path
import string,math
import condorMonitor,condorExe
import logSupport
# sets is deprecated in Python 2.6 as set is a new builtin class
try:
    set
except:
    from sets import Set as set

#############################################################################################

#
# Return a dictionary of schedds containing interesting jobs
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorQ(schedd_names, constraint=None, format_list=None):
    if format_list != None:
        format_list = condorMonitor.complete_format_list(format_list, [('JobStatus', 'i'), ('EnteredCurrentStatus', 'i'), ('ServerTime', 'i'), ('RemoteHost', 's')])
    return getCondorQConstrained(schedd_names, "(JobStatus=?=1)||(JobStatus=?=2)", constraint, format_list)

def getIdleVomsCondorQ(condorq_dict):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name],lambda el:(el.has_key('JobStatus') and (el['JobStatus']==1) and (el.has_key('x509UserProxyFirstFQAN'))))
        sq.load()
        out[schedd_name]=sq
    return out




#
# Return a dictionary of schedds containing idle jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getIdleCondorQ(condorq_dict):
    out = {}
    for schedd_name in condorq_dict.keys():
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:(el.has_key('JobStatus') and (el['JobStatus'] == 1)))
        sq.load()
        out[schedd_name] = sq
    return out

#
# Return a dictionary of schedds containing running jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getRunningCondorQ(condorq_dict):
    out = {}
    for schedd_name in condorq_dict.keys():
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:(el.has_key('JobStatus') and (el['JobStatus'] == 2)))
        sq.load()
        out[schedd_name] = sq
    return out

def appendRealRunning(condorq_dict, status_dict):
    for schedd_name in condorq_dict:
        condorq = condorq_dict[schedd_name].fetchStored()

        for jid in condorq:
            found = False

            if condorq[jid].has_key('RemoteHost'):
                remote_host = condorq[jid]['RemoteHost']

                for collector_name in status_dict:
                    condor_status = status_dict[collector_name].fetchStored()
                    if remote_host in condor_status:
                        # there is currently no way to get the factory collector from
                        #   condor status so this hack grabs the hostname of the schedd
                        schedd = condor_status[remote_host]['GLIDEIN_Schedd'].split('@')
                        if len(schedd) < 2:
                            break

                        # split by : to remove port number if there
                        fact_pool = schedd[1].split(':')[0]

                        condorq[jid]['RunningOn'] = "%s@%s@%s@%s" % (
                            condor_status[remote_host]['GLIDEIN_Entry_Name'],
                            condor_status[remote_host]['GLIDEIN_Name'],
                            condor_status[remote_host]['GLIDEIN_Factory'],
                            fact_pool)
                        found = True
                        break

            if not found:
                condorq[jid]['RunningOn'] = 'UNKNOWN'

#
# Return a dictionary of schedds containing old jobs
# Each element is a condorQ
#
# Use the output of getCondorQ
#
def getOldCondorQ(condorq_dict, min_age):
    out = {}
    for schedd_name in condorq_dict.keys():
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:(el.has_key('ServerTime') and el.has_key('EnteredCurrentStatus') and ((el['ServerTime'] - el['EnteredCurrentStatus']) >= min_age)))
        sq.load()
        out[schedd_name] = sq
    return out

#
# Return the number of jobs in the dictionary
# Use the output of getCondorQ
#
def countCondorQ(condorq_dict):
    count = 0
    for schedd_name in condorq_dict.keys():
        count += len(condorq_dict[schedd_name].fetchStored())
    return count

#
# Return a set of users present in the dictionary
# Needs "User" attribute
#

def getCondorQUsers(condorq_dict):
    users_set = set()
    for schedd_name in condorq_dict.keys():
        condorq_data = condorq_dict[schedd_name].fetchStored()
        for jid in condorq_data.keys():
            job = condorq_data[jid]
            users_set.add(job['User'])

    return users_set

#
# Get the number of jobs that match each glidein
#
# match_obj = compile('(job["MIN_NAME"]<glidein["MIN_NAME"]) && (job["ARCH"]==glidein["ARCH"])',"<string>","eval")
# condorq_dict = output of getidlqCondorQ
# glidein_dict = output of interface.findGlideins
#
# Returns:
#  tuple of 3 elements, where each is a
#    dictionary of glidein name where elements are number of jobs matching
#  The first  one is a straight match
#  The second one is the entry proportion based on unique subsets
#  The third  one contains only elements that can only run on this site 
#
#  A special "glidein name" of (None, None, None) is used for jobs 
#   that don't match any "real glidein name"

def countMatch(match_obj, condorq_dict, glidein_dict, attr_dict, condorq_match_list=None):
    out_glidein_counts = {}
    #new_out_counts: keys are site indexes(numbers), 
    #elements will be the number of real
    #idle jobs associated with each site
    new_out_counts = {}
    glideindex = 0

    schedds=condorq_dict.keys()
    nr_schedds=len(schedds)

    # find max ProcId
    max_procid=0
    for scheddIdx in range(nr_schedds):
        schedd=schedds[scheddIdx]
        condorq=condorq_dict[schedd]
        condorq_data=condorq.fetchStored()
        for jid in condorq_data.keys():
          procid=jid[1]
          if procid>max_procid:
           max_procid=procid
    procid_mul=long(max_procid+1)

    # dict of job clusters
    # group together those that have the same attributes
    cq_dict_clusters={}
    # set of all jobs
    cq_jobs=set()
    for scheddIdx in range(nr_schedds):
        schedd=schedds[scheddIdx]
        cq_dict_clusters[scheddIdx]={}
        cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
        condorq=condorq_dict[schedd]
        condorq_data=condorq.fetchStored()
        for jid in condorq_data.keys():
            jh=hashJob(condorq_data[jid],condorq_match_list)
            if not cq_dict_clusters_el.has_key(jh):
                cq_dict_clusters_el[jh]=[]
            cq_dict_clusters_el[jh].append(jid)
            t=(jid[0]*procid_mul+jid[1])*nr_schedds+scheddIdx
            cq_jobs.add(t)

    list_of_all_jobs = []

    for glidename in glidein_dict:
        glidein=glidein_dict[glidename]
        glidein_count=0
        jobs_arr=[]
        for scheddIdx in range(nr_schedds):
            schedd=schedds[scheddIdx]
            cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            schedd_count=0
            sjobs_arr=[]
            for jh in cq_dict_clusters_el.keys():
                # get the first job... they are all the same
                first_jid=cq_dict_clusters_el[jh][0]
                job=condorq_data[first_jid]
                if eval(match_obj):
                    # the first matched... add all jobs in the cluster
                    cluster_arr=[]
                    for jid in cq_dict_clusters_el[jh]:
                        t=(jid[0]*procid_mul+jid[1])*nr_schedds+scheddIdx
                        cluster_arr.append(t)
                        schedd_count+=1
                    # adding a whole cluster much faster
                    sjobs_arr+=cluster_arr
                    del cluster_arr
                    pass
                pass
            jobs_arr+=sjobs_arr
            del sjobs_arr
            glidein_count+=schedd_count
            pass    
        jobs=set(jobs_arr)
        del jobs_arr
        list_of_all_jobs.append(jobs)
        out_glidein_counts[glidename]=glidein_count
        pass

    (outvals,jrange) = uniqueSets(list_of_all_jobs)
    del list_of_all_jobs
    count_unmatched=len(cq_jobs-jrange)

    #unique_to_site: keys are sites, elements are num of unique jobs
    unique_to_site = {}
    #each tuple contains ([list of site_indexes],jobs associated with those sites)
    #this loop necessary to avoid key error
    for tuple in outvals:
        for site_index in tuple[0]:
            new_out_counts[site_index]=0.0
            unique_to_site[site_index]=0
    #for every tuple of([site_index],jobs), cycle through each site index
    #new_out_counts[site_index] is the number of jobs over the number
    #of indexes, may not be an integer.
    for tuple in outvals:
        for site_index in tuple[0]:
            new_out_counts[site_index]=new_out_counts[site_index]+(1.0*len(tuple[1])/len(tuple[0]))
        #if the site has jobs unique to it
        if len(tuple[0])==1:
            temp_sites=tuple[0]
            unique_to_site[temp_sites.pop()]=len(tuple[1])
    #create a list of all sites, list_of_sites[site_index]=site
    list_of_sites=[]
    i=0
    for glidename in glidein_dict:
        list_of_sites.append(0)
        list_of_sites[i]=glidename
        i=i+1
    final_out_counts={}
    final_unique={}
    # new_out_counts to final_out_counts
    # unique_to_site to final_unique
    # keys go from site indexes to sites
    for glidename in glidein_dict:
        final_out_counts[glidename]=0
        final_unique[glidename]=0
    for site_index in new_out_counts:
        site=list_of_sites[site_index]
        final_out_counts[site]=math.ceil(new_out_counts[site_index])
        final_unique[site]=unique_to_site[site_index]

    out_glidein_counts[(None,None,None)]=count_unmatched
    final_out_counts[(None,None,None)]=count_unmatched
    final_unique[(None,None,None)]=count_unmatched
    return (out_glidein_counts,final_out_counts,final_unique)

def countRealRunning(match_obj,condorq_dict,glidein_dict,attr_dict,condorq_match_list=None):
    out_glidein_counts={}

    if condorq_match_list!=None:
        condorq_match_list=condorq_match_list+['RunningOn']

    schedds=condorq_dict.keys()
    nr_schedds=len(schedds)

    # dict of job clusters
    # group together those that have the same attributes
    cq_dict_clusters={}
    for scheddIdx in range(nr_schedds):
        schedd=schedds[scheddIdx]
        cq_dict_clusters[scheddIdx]={}
        cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
        condorq=condorq_dict[schedd]
        condorq_data=condorq.fetchStored()
        for jid in condorq_data.keys():
            jh=hashJob(condorq_data[jid],condorq_match_list)
            if not cq_dict_clusters_el.has_key(jh):
                cq_dict_clusters_el[jh]=[]
            cq_dict_clusters_el[jh].append(jid)

    for glidename in glidein_dict:
        # split by : to remove port number if there
        glide_str = "%s@%s" % (glidename[1],glidename[0].split(':')[0])
        glidein=glidein_dict[glidename]
        glidein_count=0
        for scheddIdx in range(nr_schedds):
            schedd=schedds[scheddIdx]
            cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            schedd_count=0
            for jh in cq_dict_clusters_el.keys():
                # get the first job... they are all the same
                first_jid=cq_dict_clusters_el[jh][0]
                job=condorq_data[first_jid]
                if eval(match_obj) and job['RunningOn'] == glide_str:
                    schedd_count+=len(cq_dict_clusters_el[jh])
                pass
            glidein_count+=schedd_count
            pass
        out_glidein_counts[glidename] = glidein_count
        pass
    return out_glidein_counts

#
# Convert frontend param expression in a value
#
# expr_obj = compile('glidein["MaxTimeout"]+frontend["MaxTimeout"]+600',"<string>","eval")
# frontend = the frontend const parameters
# glidein  = glidein factory parameters
#
# Returns:
#  The evaluated value
def evalParamExpr(expr_obj, frontend, glidein):
    return eval(expr_obj)

#
# Return a dictionary of collectors containing interesting classads
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorStatus(collector_names, constraint=None, format_list=None):
    if format_list != None:
        format_list = condorMonitor.complete_format_list(format_list, [('State', 's'), ('Activity', 's'), ('EnteredCurrentState', 'i'), ('EnteredCurrentActivity', 'i'), ('LastHeardFrom', 'i'), ('GLIDEIN_Factory', 's'), ('GLIDEIN_Name', 's'), ('GLIDEIN_Entry_Name', 's'), ('GLIDECLIENT_Name', 's'), ('GLIDEIN_Schedd', 's')])
    return getCondorStatusConstrained(collector_names, '(IS_MONITOR_VM=!=True)&&(GLIDEIN_Factory=!=UNDEFINED)&&(GLIDEIN_Name=!=UNDEFINED)&&(GLIDEIN_Entry_Name=!=UNDEFINED)', constraint, format_list)

#
# Return a dictionary of collectors containing idle(unclaimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getIdleCondorStatus(status_dict):
    out = {}
    for collector_name in status_dict.keys():
        sq = condorMonitor.SubQuery(status_dict[collector_name], lambda el:(el.has_key('State') and el.has_key('Activity') and (el['State'] == "Unclaimed") and (el['Activity'] == "Idle")))
        sq.load()
        out[collector_name] = sq
    return out

#
# Return a dictionary of collectors containing running(claimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getRunningCondorStatus(status_dict):
    out = {}
    for collector_name in status_dict.keys():
        sq = condorMonitor.SubQuery(status_dict[collector_name], lambda el:(el.has_key('State') and el.has_key('Activity') and (el['State'] == "Claimed") and (el['Activity'] in ("Busy", "Retiring"))))
        sq.load()
        out[collector_name] = sq
    return out

#
# Return a dictionary of collectors containing idle(unclaimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getClientCondorStatus(status_dict, frontend_name, group_name, request_name):
    client_name_old = "%s@%s.%s" % (request_name, frontend_name, group_name)
    client_name_new = "%s.%s" % (frontend_name, group_name)
    out = {}
    for collector_name in status_dict.keys():
        sq = condorMonitor.SubQuery(status_dict[collector_name], lambda el:(el.has_key('GLIDECLIENT_Name') and ((el['GLIDECLIENT_Name'] == client_name_old) or ((el['GLIDECLIENT_Name'] == client_name_new) and (("%s@%s@%s" % (el['GLIDEIN_Entry_Name'], el['GLIDEIN_Name'], el['GLIDEIN_Factory'])) == request_name)))))
        sq.load()
        out[collector_name] = sq
    return out

#
# Return the number of vms in the dictionary
# Use the output of getCondorStatus
#
def countCondorStatus(status_dict):
    count = 0
    for collector_name in status_dict.keys():
        count += len(status_dict[collector_name].fetchStored())
    return count

############################################################
#
# I N T E R N A L - Do not use
#
############################################################

#
# Return a dictionary of schedds containing jobs of a certain type 
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate additional constraint
#
def getCondorQConstrained(schedd_names, type_constraint, constraint=None, format_list=None):
    out_condorq_dict = {}
    for schedd in schedd_names:
        if schedd == '':
            logSupport.log.warning("Skipping empty schedd name")
            continue
        full_constraint = type_constraint[0:] #make copy
        if constraint != None:
            full_constraint = "(%s) && (%s)" % (full_constraint, constraint)

        try:
            condorq = condorMonitor.CondorQ(schedd)
            condorq.load(full_constraint, format_list)
        except condorExe.ExeError:
            logSupport.log.exception("Condor Error.  Failed to talk to schedd: ")
            continue # if schedd not found it is equivalent to no jobs in the queue        
        except RuntimeError:
            logSupport.log.exception("Runtime Error.  Failed to talk to schedd: ")
            continue
        except Exception:
            logSupport.log.exception("Unknown Exception.  Failed to talk to schedd: ")

        if len(condorq.fetchStored()) > 0:
            out_condorq_dict[schedd] = condorq
            
    return out_condorq_dict

#
# Return a dictionary of collectors containing classads of a certain kind 
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate additional constraint
#
def getCondorStatusConstrained(collector_names, type_constraint, constraint=None, format_list=None):
    out_status_dict = {}
    for collector in collector_names:
        full_constraint = type_constraint[0:] #make copy
        if constraint != None:
            full_constraint = "(%s) && (%s)" % (full_constraint, constraint)

        try:
            status = condorMonitor.CondorStatus(pool_name=collector)
            status.load(full_constraint, format_list)
        except condorExe.ExeError:
            if collector != None:
                logSupport.log.exception("Condor Error. Failed to talk to collector %s: " % collector)
            else:
                logSupport.log.exception("Condor Error. Failed to talk to collector: ")
            continue # if collector not found it is equivalent to no classads      
        except RuntimeError:
            logSupport.log.exception("Runtime error. Failed to talk to collector: ")
            continue
        
        if len(status.fetchStored()) > 0:
            out_status_dict[collector] = status
            
    return out_status_dict

#############################################
#
# Extract unique subsets from a list of sets
# by Benjamin Hass @ UCSD (working under Igor Sfiligoi)
#
# Input: list of sets
# Output: list of (index set, value subset) pairs + a set that is the union of all input sets
#
# Example in:
#   [Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]), Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
#    Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
#         21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]),
#    Set([11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30])]
# Example out:
#   ([(Set([2]), Set([32, 33, 34, 35, 31])),
#     (Set([0, 1, 2]), Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])),
#     (Set([2, 3]), Set([11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
#                        21, 22, 23, 24, 25, 26, 27, 28, 29, 30]))],
#    Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
#         21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35]))
#
def uniqueSets(in_sets):
    #sets is a list of sets
    sorted_sets = []
    for i in in_sets:
        common_list = []
        common = set()
        new_unique = set()
        old_unique_list = []
        old_unique = sets()
        new = []
        #make a list of the elements common to i
        #(current iteration of sets) and the existing
        #sorted sets
        for k in sorted_sets:
            #for now, old unique is a set with all elements of
            #sorted_sets
            old_unique = old_unique | k
            common = k & i
            if common:
                common_list.append(common)
            else:
                pass
        #figure out which elements in i
        # and which elements in old_uniques are unique
        for j in common_list:
            i = i - j
            old_unique = old_unique - j
        #make a list of all the unique elements in sorted_sets
        for k in sorted_sets:
            old_unique_list.append(k & old_unique)
        new_unique = i
        if new_unique:
            new.append(new_unique)
        for o in old_unique_list:
            if o:
                new.append(o)
        for c in common_list:
            if c:
                new.append(c)
        sorted_sets = new

    # set with all unique elements
    sum_set = set()
    for s in sorted_sets:
        sum_set = sum_set | s


    sorted_sets.append(sum_set)

    # index_list is a list of lists. Each list corresponds to 
    # an element in sorted_sets, and contains the indexes of 
    # that elements shared elements in the initial list of sets
    index_list = []
    for s in sorted_sets:
        indexes = []
        temp_sets = in_sets[:]
        for t in temp_sets:
            if s & t:
                indexes.append(temp_sets.index(t))
                temp_sets[temp_sets.index(t)] = set()
        index_list.append(indexes)

    # create output
    outvals = []
    for i in range(len(index_list) - 1): # last one contains all the values
        outvals.append((set(index_list[i]), sorted_sets[i]))
    return (outvals, sorted_sets[-1])

def hashJob(condorq_el, condorq_match_list=None):
    out=[]
    keys=condorq_el.keys()
    keys.sort()
    if condorq_match_list!=None:
        # whitelist... keep only the ones listed
        allkeys=keys
        keys=[]
        for k in allkeys:
            if k in condorq_match_list:
                keys.append(k)
    for k in keys:
        out.append((k,condorq_el[k]))
    return tuple(out)
