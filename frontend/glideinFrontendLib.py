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
import string
import math
import sys
import traceback
import os

from glideinwms.lib import condorMonitor, logSupport

#############################################################################################

#
# Return a dictionary of schedds containing interesting jobs
# Each element is a condorQ
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate constraint
#
def getCondorQ(schedd_names, constraint=None, format_list=None,
               want_format_completion=True, job_status_filter=(1, 2)):

    if format_list is not None:
        if want_format_completion:
            format_list = condorMonitor.complete_format_list(
                format_list,
                [('JobStatus', 'i'), ('EnteredCurrentStatus', 'i'),
                 ('ServerTime', 'i'), ('RemoteHost', 's')])

    if not job_status_filter:
        # if nothing specified, assume it wants all of them
        js_constraint="True"
    else:
        js_arr=[]
        for n in job_status_filter:
            js_arr.append('(JobStatus=?=%i)'%n)
        js_constraint=string.join(js_arr, '||')

    return getCondorQConstrained(schedd_names, js_constraint, constraint, format_list)

def getIdleVomsCondorQ(condorq_dict):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:((el.get('JobStatus')==1) and ('x509UserProxyFirstFQAN' in el)))
        sq.load()
        out[schedd_name]=sq
    return out

def getIdleProxyCondorQ(condorq_dict):
    out={}
    for schedd_name in condorq_dict.keys():
        sq=condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:((el.get('JobStatus')==1) and ('x509userproxy' in el)))
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
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:('JobStatus' in el and (el['JobStatus'] == 1)))
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
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:('JobStatus' in el and (el['JobStatus'] == 2)))
        sq.load()
        out[schedd_name] = sq
    return out

def appendRealRunning(condorq_dict, status_dict):
    """Adds provenance information from condor_status to the condor_q dictionary
    The name of static or pslots is the value of RemoteHost
    NOTE: HTC 8.5 may change RemoteHost to be the DynamicSlot name

    :param condorq_dict: adding 'RunningOn' to each job
    :param status_dict: running jobs from condor_status
    :return:
    """
    for schedd_name in condorq_dict:
        condorq = condorq_dict[schedd_name].fetchStored()

        for jid in condorq:
            found = False

            if 'RemoteHost' in condorq[jid]:
                remote_host = condorq[jid]['RemoteHost']

                for collector_name in status_dict:
                    condor_status = status_dict[collector_name].fetchStored()
                    if remote_host in condor_status:
                        # there is currently no way to get the factory
                        # collector from condor status so this hack grabs
                        # the hostname of the schedd
                        schedd = condor_status[remote_host]['GLIDEIN_Schedd'].split('@')

                        # split by : to remove port number if there
                        fact_pool = schedd[-1].split(':')[0]

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
        sq = condorMonitor.SubQuery(condorq_dict[schedd_name], lambda el:('ServerTime' in el and 'EnteredCurrentStatus' in el and ((el['ServerTime'] - el['EnteredCurrentStatus']) >= min_age)))
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


def countMatch(match_obj, condorq_dict, glidein_dict, attr_dict,
               condorq_match_list=None, match_policies=[]):
    """
    Get the number of jobs that match each glidein
    
    @param match_obj: output of re.compile(match string,'<string>','eval')
    @type condorq_dict: dictionary: sched_name->CondorQ object
    @param condorq_dict: output of getidleCondorQ
    @type glidein_dict: dictionary: glidein_name->dictionary of params and attrs
    @param glidein_dict: output of interface.findGlideins
    @param attr_dict:  dictionary of constant attributes
    @param condorq_match_list: list of job attributes from the XML file

    @return: tuple of 4 elements, where first 3 are a dictionary of
        glidein name where elements are number of jobs matching
        First tuple  : Straight match
        Second tuple : The entry proportion based on unique subsets
        Third tuple  : Elements that can only run on this site
        Forth tuple  : The entry proportion glideins to be requested based
                       on unique subsets after considering multicore
                       jobs and GLIDEIN_CPUS/GLIDEIN_ESTIMATED_CPUS
        A special 'glidein name' of (None, None, None) is used for jobs
        that don't match any 'real glidein name' in all 4 tuples above
    """

    out_glidein_counts={}
    out_cpu_counts={}

    # new_out_counts
    # keys: are site indexes(numbers)
    # elements: number of real idle jobs associated with each site
    new_out_counts = {}
    glideindex = 0

    #
    # To speed up dictionary lookup
    # we will convert Schedd_Name#ClusterId.ProcID into a number
    # Since we have to convert a 3 dimensional entity into a linear number
    # we have to pick two ranges to use as multipliers
    # len(schedds) is the first obvious one, since it is fixed
    # between ClusterId and ProcId, we select max(ProcId) 
    # since it is the smaller of the two the formula thus becomes
    #  (ClusterId*max_ProcId+ProcId)*len(schedds)+scheddIdx
    #

    schedds=condorq_dict.keys()
    nr_schedds=len(schedds)

    # Find max ProcId by searching through condorq output for all schedds
    #   This is needed to linearize the dictionary as per above
    #   The max ProcId will be stored in procid_mul
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

    # Group jobs into clusters of similar attributes

    # Results will be stored in the variables:
    #  cq_dict_clusters - dict of clusters (= list of job ids)
    #  cq_jobs - full set of job ids
    cq_dict_clusters={}
    cq_jobs=set()
    for scheddIdx in range(nr_schedds):
        # For each schedd, look through all its job from condorq results
        schedd=schedds[scheddIdx]
        cq_dict_clusters[scheddIdx]={}
        cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
        condorq=condorq_dict[schedd]
        condorq_data=condorq.fetchStored()
        for jid in condorq_data.keys():
            # For each job, hash the job using the attributes
            #  listed from xml under match_attrs
            # Jobs that hash to the same value should
            #  be considered equivalent and part of the same
            #  cluster for matching purposes
            jh=hashJob(condorq_data[jid], condorq_match_list)
            if jh not in cq_dict_clusters_el:
                cq_dict_clusters_el[jh]=[]
            # Add the job to the correct cluster according to the
            #   linearization scheme above
            cq_dict_clusters_el[jh].append(jid)
            t=(jid[0]*procid_mul+jid[1])*nr_schedds+scheddIdx
            # Add jobs
            cq_jobs.add(t)

    # Now, loop through all glideins (ie. entries)
    # match the clusters to these glideins
    # Results:
    # list_of_all_jobs: a list containing the set of jobs that match
    #                   a gliedin (i.e. entry) the position in the list
    #                   identifies the glidein and each element is a set of 
    #                   indexes representing a job cluster each
    #  all_jobs_clusters: dictionary of cluster index -> list of jobs in
    #                     the cluster (represented each by its own index)
    list_of_all_jobs=[]
    all_jobs_clusters={}
    
    for glidename in glidein_dict:
        glidein=glidein_dict[glidename]
        # Number of glideins to request
        glidein_count=0
        # Number of cpus required by the jobs on a glidein
        cpu_count=0
        jobs_arr=[]

        # Clusters are organized by schedd,
        #  so loop through each schedd
        for scheddIdx in range(nr_schedds):
            #logSupport.log.debug("****** Loop schedds ******")
            # Now, go through each unique hash in the cluster
            # and match clusters individually
            schedd=schedds[scheddIdx]
            cq_dict_clusters_el=cq_dict_clusters[scheddIdx]
            condorq=condorq_dict[schedd]
            condorq_data=condorq.fetchStored()
            # Number of jobs in this schedd to request glidein
            schedd_count=0
            # Number of cpus to request for jobs on this schedd
            cpu_schedd_count=0
            sjobs_arr=[]

            missing_keys = set()
            tb_count = 0
            recent_tb = None

            for jh in cq_dict_clusters_el.keys():
                # get the first job... they are all the same
                first_jid=cq_dict_clusters_el[jh][0]
                job=condorq_data[first_jid]

                try:
                    # Evaluate the Compiled object first.
                    # Evaluation order does not really matter.
                    match = eval(match_obj)
                    for policy in match_policies:
                        if match == True:
                            # Policies are supposed to be ANDed
                            match = (match and policy.pyObject.match(job, glidein))
                        else:
                            if match != False:
                                # Non boolean results should be discarded
                                # and logged
                                logSupport.log.warning("Match expression from policy file '%s' evaluated to non boolean result; assuming False" % policy.file)
                            break

                    if match == True:
                        # the first matched... add all jobs in the cluster
                        cluster_arr=[]
                        for jid in cq_dict_clusters_el[jh]:
                            t=(jid[0]*procid_mul+jid[1])*nr_schedds+scheddIdx
                            cluster_arr.append(t)
                            schedd_count+=1

                        # Since all jobs are same figure out how many cpus
                        # are required for this cluster based on one job
                        cpu_schedd_count += job.get('RequestCpus', 1) * len(cq_dict_clusters_el[jh])
                        first_t=(first_jid[0]*procid_mul+first_jid[1])*nr_schedds+scheddIdx
                        all_jobs_clusters[first_t]=cluster_arr
                        sjobs_arr+=[first_t]
                except KeyError as e:
                    tb = traceback.format_exception(sys.exc_info()[0],
                                                    sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    key = ((tb[-1].split(':'))[1]).strip()
                    missing_keys.add(key)

                except Exception as e:
                    tb_count = tb_count + 1
                    recent_tb = traceback.format_exception(sys.exc_info()[0],
                                                           sys.exc_info()[1],
                                                           sys.exc_info()[2])

            if missing_keys:
                logSupport.log.debug("Failed to evaluate resource match in countMatch. Possibly match_expr has errors and trying to reference job or site attribute(s) '%s' in an inappropriate way." % (','.join(missing_keys)))
            if tb_count > 0:
                logSupport.log.debug("There were %s exceptions in countMatch subprocess. Most recent traceback: %s " % (tb_count, recent_tb))

            # END LOOP: for jh in cq_dict_clusters_el.keys()

            jobs_arr+=sjobs_arr
            del sjobs_arr
            glidein_count+=schedd_count
            cpu_count+=cpu_schedd_count

        # END LOOP: for scheddIdx in range(nr_schedds)

        jobs=set(jobs_arr)
        del jobs_arr
        list_of_all_jobs.append(jobs)
        out_glidein_counts[glidename]=glidein_count
        out_cpu_counts[glidename]=cpu_count

    # END LOOP: for glidename in glidein_dict

    # Now split the list of sets into unique sets
    # We will use this to count how many glideins each job matches against
    # outvals_cl contains the new list of unique sets each element is a
    # tuple: (set of glideins with the same jobs, set of jobs)
    # jrange_cl contains the set of all the job clusters
    (outvals_cl, jrange_cl) = uniqueSets(list_of_all_jobs)
    del list_of_all_jobs

    # Convert from clusters back to jobs
    #   Now that we are done matching, we no longer
    #   need the clusters (needed for more efficient matching)
    #   convert all_jobs_clusters back to jobs_arr (list of jobs)
    outvals=[]
    for tuple in outvals_cl:
        jobs_arr=[]
        for ct in tuple[1]:
            cluster_arr=all_jobs_clusters[ct]
            jobs_arr+=cluster_arr
        outvals.append((tuple[0], set(jobs_arr)))
    jobs_arr=[]
    for ct in jrange_cl:
        cluster_arr=all_jobs_clusters[ct]
        jobs_arr+=cluster_arr
    jrange=set(jobs_arr)

    count_unmatched=len(cq_jobs-jrange)

    #unique_to_site: keys are sites, elements are num of unique jobs
    unique_to_site = {}
    #each tuple is ([list of site_indexes],jobs associated with those sites)
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
    final_out_cpu_counts={}
    final_unique={}
    # new_out_counts to final_out_counts
    # unique_to_site to final_unique
    # keys go from site indexes to sites
    for glidename in glidein_dict:
        final_out_counts[glidename]=0
        final_out_cpu_counts[glidename]=0
        final_unique[glidename]=0
    for site_index in new_out_counts:
        site=list_of_sites[site_index]
        final_out_counts[site]=math.ceil(new_out_counts[site_index])
        if out_glidein_counts[site] > 0:
            glidein_cpus = 1.0 * getGlideinCpusNum(glidein_dict[site])
            # new_out_counts is based on 1 cpu jobs
            # For a site, out_glidein_counts translates to out_cpu_counts
            # Figure out corresponding out_cpu_counts for new_out_counts
            # Scale the number based on the total cpus required &
            # that provided by the worker node on the site
            
            prop_cpus = (out_cpu_counts[site] * new_out_counts[site_index])/out_glidein_counts[site]
            prop_out_count = prop_cpus/glidein_cpus
            final_out_cpu_counts[site] = math.ceil(prop_out_count)

        final_unique[site]=unique_to_site[site_index]

    out_glidein_counts[(None, None, None)]=count_unmatched
    out_cpu_counts[(None, None, None)]=count_unmatched
    final_out_counts[(None, None, None)]=count_unmatched
    final_out_cpu_counts[(None, None, None)]=count_unmatched
    final_unique[(None, None, None)]=count_unmatched
    return (out_glidein_counts, final_out_counts,
            final_unique, final_out_cpu_counts)


def countRealRunning(match_obj, condorq_dict, glidein_dict,
                     attr_dict, condorq_match_list=None, match_policies=[]):
    """
    Counts all the running jobs on an entry
    :param match_obj: selection for the jobs
    :param condorq_dict: result of condor_q, keyed by schedd name
    :param glidein_dict: glideins, keyed by entry (glidename)
    :param attr_dict: entry attributes, NOT USED
    :param condorq_match_list: match attributes used for clustering
    :return: Tuple with the job counts (used for stats) and glidein counts (used for glidein_max_run)
      Both are dictionaries keyed by glidename (entry)
    """

    out_job_counts = {}
    out_glidein_counts = {}

    if condorq_match_list is not None:
        condorq_match_list = condorq_match_list + ['RunningOn']
    # add an else branch in case the initial list is None? Probably should never happen
    # else:
    #     condorq_match_list = ['RunningOn']

    schedds = condorq_dict.keys()
    nr_schedds = len(schedds)

    # dict of job clusters
    # group together those that have the same attributes
    cq_dict_clusters = {}
    for scheddIdx in range(nr_schedds):
        schedd = schedds[scheddIdx]
        cq_dict_clusters[scheddIdx] = {}
        cq_dict_clusters_el = cq_dict_clusters[scheddIdx]
        condorq = condorq_dict[schedd]
        condorq_data = condorq.fetchStored()
        for jid in condorq_data.keys():
            jh = hashJob(condorq_data[jid], condorq_match_list)
            if jh not in cq_dict_clusters_el:
                cq_dict_clusters_el[jh] = []
            cq_dict_clusters_el[jh].append(jid)

    for glidename in glidein_dict:
        # split by : to remove port number if there
        glide_str = "%s@%s" % (glidename[1], glidename[0].split(':')[0])
        glidein = glidein_dict[glidename]
        glidein_count = 0
        # Sets are necessary to remove duplicates
        # job_ids counts all the jobs running on the current entry (Running here stats)
        #   job_ID+schedd_ID identifies a job, set() is used to merge jobs matched by multiple auto-clusters
        # glidein_ids counts the glideins: multiple jobs could run on the same glidein, RemoteHost
        #   (without the initial slotN@ part) identifies the glidein
        #   i.e. multiple jobs with same RemoteHost run on the same slot, removing slotN@ gives all the slots
        #        running on the same glidein
        #   The slot part will change in HTCondor 8.5, where dynamic slots will have their name instead of the
        #   pslot name but removing slotN_N@ will still identify the glidein (so this code is robust to the change)
        job_ids = set()
        glidein_ids = set()
        for scheddIdx in range(nr_schedds):
            schedd = schedds[scheddIdx]
            cq_dict_clusters_el = cq_dict_clusters[scheddIdx]
            condorq = condorq_dict[schedd]
            condorq_data = condorq.fetchStored()
            schedd_count = 0

            missing_keys = set()
            tb_count = 0
            recent_tb = None

            for jh in cq_dict_clusters_el.keys():
                # get the first job... they are all the same
                first_jid = cq_dict_clusters_el[jh][0]
                job = condorq_data[first_jid]
                try:
                    # Evaluate the Compiled object first.
                    # Evaluation order does not really matter.
                    match = ((job['RunningOn']==glide_str) and eval(match_obj))
                    for policy in match_policies:
                        if match == True:
                            # Policies are supposed to be ANDed
                            match = (match and policy.pyObject.match(job, glidein))
                        else:
                            if match != False:
                                # Non boolean results should be discarded
                                # and logged
                                logSupport.log.warning("Match expression from policy file '%s' evaluated to non boolean result; assuming False" % policy.file)
                            break

                    if match == True:
                        schedd_count+=len(cq_dict_clusters_el[jh])
                        for jid in cq_dict_clusters_el[jh]:
                            job = condorq_data[jid]
                            job_ids.add("%d %s" % (scheddIdx, jid))
                            # glidein ID is just glidein_XXXXX_XXXXX@fqdn
                            # RemoteHost has following valid formats
                            #
                            # Static slots
                            # ------------
                            # 1 core: glidein_XXXXX_XXXXX@fqdn
                            # N core: slotN@glidein_XXXXX_XXXXX@fqdn
                            #
                            # Dynamic slots
                            # -------------
                            # N core: slotN_M@glidein_XXXXX_XXXXX@fqdn
                            try:
                                token = job['RemoteHost'].split('@')
                                glidein_id = '%s@%s' % (token[-2], token[-1])
                            except (KeyError, IndexError):
                                # If RemoteHost is missing or has a different
                                # format just identify it with the uniq jobid
                                # for accounting purposes. Here we assume that
                                # the job is running in a glidein with 1 slot
                                glidein_id = "%d %s" % (scheddIdx, jid)
                            glidein_ids.add(glidein_id)
                except KeyError as e:
                    tb = traceback.format_exception(sys.exc_info()[0],
                                                    sys.exc_info()[1],
                                                    sys.exc_info()[2])
                    key = ((tb[-1].split(':'))[1]).strip()
                    missing_keys.add(key)
                except Exception as e:
                    tb_count = tb_count + 1
                    recent_tb = traceback.format_exception(sys.exc_info()[0],
                                                           sys.exc_info()[1],
                                                           sys.exc_info()[2])
            if missing_keys:
                logSupport.log.debug("Failed to evaluate resource match in countRealRunning. Possibly match_expr has errors and trying to reference job or site attribute(s) '%s' in an inappropriate way." % (','.join(missing_keys)))
            if tb_count > 0:
                logSupport.log.debug("There were %s exceptions in countRealRunning subprocess. Most recent traceback: %s" % (tb_count, recent_tb))
            glidein_count += schedd_count
        logSupport.log.debug("Running glidein ids at %s (total glideins: %d, total jobs %d, cluster matches: %d): %s" %
                             (glidename, len(glidein_ids), len(job_ids), glidein_count, ", ".join(list(glidein_ids)[:5])))
        out_job_counts[glidename] = len(job_ids)
        out_glidein_counts[glidename] = len(glidein_ids)
    return out_job_counts, out_glidein_counts

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


def getCondorStatus(collector_names, constraint=None, format_list=None,
                    want_format_completion=True, want_glideins_only=True):
    """
    Return a dictionary of collectors containing interesting classads
    Each element is a condorStatus
    @param collector_names:
    @param constraint:
    @param format_list:
    @param want_format_completion:
    @param want_glideins_only:
    @return:
    """
    type_constraint = '(True)'
    if format_list is not None:
        if want_format_completion:
            format_list = condorMonitor.complete_format_list(
                format_list,
                [('State', 's'), ('Activity', 's'),
                 ('EnteredCurrentState', 'i'), ('EnteredCurrentActivity', 'i'),
                 ('LastHeardFrom', 'i'), ('GLIDEIN_Factory', 's'),
                 ('GLIDEIN_Name', 's'), ('GLIDEIN_Entry_Name', 's'),
                 ('GLIDECLIENT_Name', 's'), ('GLIDECLIENT_ReqNode', 's'),
                 ('GLIDEIN_Schedd', 's')])

    ###########################################################################
    # Parag: Nov 24, 2014
    # To get accounting info related to idle/running/total cores, you need to
    # get the partitionable slot (ie parent slot) classads as well.
    # Move the type_constraint below to individual getCondorStatus* filtering
    #
    # Partitionable slots are *always* idle 
    # The frontend only counts them when all the subslots have been
    # reclaimed (HTCondor sets TotalSlots == 1)
    # type_constraint = '(PartitionableSlot =!= True || TotalSlots =?= 1)'
    ###########################################################################

    if want_glideins_only:
        type_constraint += '&&(IS_MONITOR_VM=!=True)&&(GLIDEIN_Factory=!=UNDEFINED)&&(GLIDEIN_Name=!=UNDEFINED)&&(GLIDEIN_Entry_Name=!=UNDEFINED)'

    return getCondorStatusConstrained(collector_names, type_constraint, constraint, format_list)


def getCondorStatusNonDynamic(status_dict):
    """
    Return a dictionary of collectors containing static+partitionable slots
    and exclude any dynamic slots

    Each element is a condorStatus
    Use the output of getCondorStatus
    """
    out = {}
    for collector_name in status_dict.keys():
        # Exclude partitionable slots with no free memory/cpus
        sq = condorMonitor.SubQuery(
            status_dict[collector_name],
            lambda el: (
                (el.get('SlotType') != 'Dynamic')
            )
        )
        sq.load()
        out[collector_name] = sq
    return out


#
# Return a dictionary of collectors containing idle(unclaimed) vms
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getIdleCondorStatus(status_dict):
    out = {}
    for collector_name in status_dict.keys():

        # Exclude partitionable slots with no free memory/cpus
        # Minimum memory required by CMS is 2500 MB
        #
        # 1. (el.get('PartitionableSlot') != True)
        # Includes static slots irrespective of the free cpu/mem
        #
        # 2. (el.get('TotalSlots') == 1)
        # p-slots not yet partitioned
        #
        # 3. (el.get('Cpus', 0) > 0 and el.get('Memory', 2501) > 2500)
        # p-slots that have enough idle resources.

        sq = condorMonitor.SubQuery(
            status_dict[collector_name],
            lambda el: (
                (el.get('State') == 'Unclaimed') and
                (el.get('Activity') == 'Idle') and
                (
                    (el.get('PartitionableSlot') != True) or
                    (el.get('TotalSlots') == 1) or
                    (el.get('Cpus', 0) > 0 and el.get('Memory', 2501) > 2500)
                )
            )
        )
        sq.load()
        out[collector_name] = sq
    return out


def getRunningCondorStatus(status_dict):
    """Return a dictionary of collectors containing running(claimed) slots
    Each element is a condorStatus

    :param status_dict: output of getCondorStatus
    :return: dictionary of collectors containing running(claimed) slots
    """
    out = {}
    for collector_name in status_dict:
        # Consider following slots
        # 1. Static - running slots
        # 2. Dynamic slots (They are always running)
        # 3. p-slot with one or more dynamic slots
        #    We get them here so we can use them easily in appendRealRunning()

        sq = condorMonitor.SubQuery(
                status_dict[collector_name],
                lambda el: (
                    ((el.get('State') == 'Claimed') and
                     (el.get('Activity') in ('Busy', 'Retiring'))
                    ) or
                    ((el.get('PartitionableSlot') == True) and
                     (el.get('TotalSlots', 1) > 1)
                    )
                )
        )
        sq.load()
        out[collector_name] = sq
    return out


def getRunningPSlotCondorStatus(status_dict):
    """Return a dictionary of collectors containing running(claimed) partitionable slots
    Each element is a condorStatus

    :param status_dict: output of getCondorStatus
    :return: collectors containing running(claimed) partitionable slots
    """
    out = {}
    for collector_name in status_dict.keys():
        # Get p-slot where there is atleast one dynamic slot
        sq = condorMonitor.SubQuery(
                 status_dict[collector_name],
                 lambda el:(
                     (el.get('PartitionableSlot') == True) and
                     (el.get('TotalSlots', 1) > 1)
                 )
             )

        sq.load()
        out[collector_name] = sq
    return out


def getRunningJobsCondorStatus(status_dict):
    """Return a dictionary of collectors containing running(claimed) slots
    This includes Fixed slots and Dynamic slots (no partitionable slots)
    Each one is matched with a single job (gives number of running jobs)
    Each element is a condorStatus

    :param status_dict: output of getCondorStatus
    :return: dictionary of collectors containing running(claimed) slots
    """
    out = {}
    for collector_name in status_dict.keys():
        # This counts the running slots: fixed (static/not partitionable) or dynamic
        # It may give problems when matching with RemoteHost in the jobs
        # since dynamic slots report the parent partitionable slot in GLIDEIN_SiteWMS_Slot

        sq = condorMonitor.SubQuery(
            status_dict[collector_name],
            lambda el: (
                ((el.get('State') == 'Claimed') and
                 (el.get('Activity') in ('Busy', 'Retiring'))
                 )
            )
        )
        sq.load()
        out[collector_name] = sq
    return out


def getFailedCondorStatus(status_dict):
    out = {}
    for collector_name in status_dict.keys():
        sq = condorMonitor.SubQuery(
            status_dict[collector_name],
            lambda el: (
                (el.get('State') == "Drained") and
                (el.get('Activity') == "Retiring")
            )
        )
        sq.load()
        out[collector_name] = sq
    return out


#
# Return a dictionary of collectors containing idle(unclaimed) cores
# Each element is a condorStatus
#
# Same as getIdleCondorStatus - the dictionaries with the Machines/Glideins are the same
#
def getIdleCoresCondorStatus(status_dict):
    return getIdleCondorStatus(status_dict)


#
# Return a dictionary of collectors containing running(claimed) cores
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getRunningCoresCondorStatus(status_dict):
    return getRunningCondorStatus(status_dict)


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
        sq = condorMonitor.SubQuery(
                 status_dict[collector_name],
                 lambda el:('GLIDECLIENT_Name' in el and ((el['GLIDECLIENT_Name'] == client_name_old) or ((el['GLIDECLIENT_Name'] == client_name_new) and (("%s@%s@%s" % (el['GLIDEIN_Entry_Name'], el['GLIDEIN_Name'], el['GLIDEIN_Factory'])) == request_name)))))
        sq.load()
        out[collector_name] = sq
    return out


#
# Return a dictionary of collectors containing vms of a specific cred
#  Input should be the output of getClientCondorStatus or equivalent
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getClientCondorStatusCredIdOnly(status_dict, cred_id):
    out = {}
    for collector_name, collector_status in status_dict.iteritems():
        sq = condorMonitor.SubQuery(
            collector_status,
            lambda el: (
                'GLIDEIN_CredentialIdentifier' in el and
                (el['GLIDEIN_CredentialIdentifier'] == cred_id)
            )
        )
        sq.load()
        out[collector_name] = sq
    return out


#
# Return a dictionary of collectors containing vms at a client split by creds
# Each element is a condorStatus
#
# Use the output of getCondorStatus
#
def getClientCondorStatusPerCredId(status_dict, frontend_name, group_name,
                                   request_name, cred_id):
    step1 = getClientCondorStatus(status_dict, frontend_name, group_name,
                                  request_name)
    out = getClientCondorStatusCredIdOnly(step1, cred_id)
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


#
# Return the number of running slots in the dictionary
# Use the output of getCondorStatus
#
def countRunningCondorStatus(status_dict):
    count = 0
    # Running sstatus dict has p-slot corresponding to the dynamic slots
    # The loop will skip elements where slot is p-slot
    for collector_name in status_dict:
        for glidein_name, glidein_details in status_dict[collector_name].fetchStored().iteritems():
            if not glidein_details.get('PartitionableSlot', False):
                count += 1
    return count


#
# Return the number of glideins in the dictionary
#
def countGlideinsCondorStatus(status_dict):
    """Return the number of glideins in the dictionary

    :param status_dict: the output of getCondorStatus
    :return: number of glideins in the dictionary (integer)

    A Glidein is an execution of the glidein_startup.sh script
     - may be different from job submitted by the factory (for multinode jobs - future)
     - is different from a slot (or schedd or vm)
    It defines GLIDEIN_MASTER_NAME which is the part after '@' in the slot name
    Sets form different collectors are assumed disjunct
    """
    count = 0
    for collector_name in status_dict:
        slots_dict = status_dict[collector_name].fetchStored()
        count += len(set([i.split('@', 1)[1] for i in slots_dict.keys()]))
    return count


#
# Return the number of cores in the dictionary based on the status_type
# Use the output of getCondorStatus
#
def countCoresCondorStatus(status_dict, state='TotalCores'):
    count = 0
    if state == 'TotalCores':
        count = countTotalCoresCondorStatus(status_dict)
    elif state == 'IdleCores':
        count = countIdleCoresCondorStatus(status_dict)
    elif state == 'RunningCores':
        count = countRunningCoresCondorStatus(status_dict)
    return count


#
# Return the number of cores in the dictionary
# Use the output of getCondorStatus
#
def countTotalCoresCondorStatus(status_dict):
    """
    Counts the cores in the status dictionary
    The status is redundant in part but necessary to handle
    correctly partitionable slots which are
    1 glidein but may have some running cores and some idle cores
    @param status_dict: a dictionary with the Machines to count
    @type status_dict: str
    """
    count = 0
    # The loop will skip elements where Cpus or TotalSlotCpus are not defined
    for collector_name in status_dict:
        for glidein_name, glidein_details in status_dict[collector_name].fetchStored().iteritems():
            # TotalSlotCpus should always be the correct number but
            # is not defined pre partitionable slots
            if glidein_details.get('PartitionableSlot', False):
                count += glidein_details.get('TotalSlotCpus', 0)
            else:
                count += glidein_details.get('Cpus', 0)
    return count


def countIdleCoresCondorStatus(status_dict):
    """
    Counts the cores in the status dictionary
    The status is redundant in part but necessary to handle
    correctly partitionable slots which are
    1 glidein but may have some running cores and some idle cores
    @param status_dict: a dictionary with the Machines to count
    @type status_dict: str
    """
    count = 0
    # The loop will skip elements where Cpus or TotalSlotCpus are not defined
    for collector_name in status_dict:
        for glidein_name, glidein_details in status_dict[collector_name].fetchStored().iteritems():
            count += glidein_details.get('Cpus', 0)
    return count


def countRunningCoresCondorStatus(status_dict):
    """
    Counts the cores in the status dictionary
    The status is redundant in part but necessary to handle
    correctly partitionable slots which are
    1 glidein but may have some running cores and some idle cores
    @param status_dict: a dictionary with the Machines to count
    @type status_dict: str
    """
    count = 0
    # The loop will skip elements where Cpus or TotalSlotCpus are not defined
    for collector_name in status_dict:
        for glidein_name, glidein_details in status_dict[collector_name].fetchStored().iteritems():
            if not glidein_details.get('PartitionableSlot', False):
                count += glidein_details.get('Cpus', 0)
    return count


#
# Given startd classads, return the list of all the factory entries
# Each element in the list is (req_name, node_name)
#
def getFactoryEntryList(status_dict):
    out = set()
    for c in status_dict.keys():
        coll_status_dict = status_dict[c].fetchStored()
        for n in coll_status_dict.keys():
            el = coll_status_dict[n]
            if not ('GLIDEIN_Entry_Name' in el and 'GLIDEIN_Name' in el and
                        'GLIDEIN_Factory' in el and 'GLIDECLIENT_ReqNode' in el):
                continue  # ignore this glidein... no factory info
            entry_str = "%s@%s@%s" % (el['GLIDEIN_Entry_Name'], el['GLIDEIN_Name'], el['GLIDEIN_Factory'])
            factory_pool = str(el['GLIDECLIENT_ReqNode'])
            out.add((entry_str, factory_pool))

    return list(out)
        

#
# Return a dictionary of collectors containing interesting classads
# Each element is a condorStatus
#
# Return the schedd classads
#
def getCondorStatusSchedds(collector_names, constraint=None, format_list=None,
                           want_format_completion=True):
    if format_list is not None:
        if want_format_completion:
            format_list = condorMonitor.complete_format_list(
                              format_list,
                              [('TotalRunningJobs', 'i'),
                               ('TotalSchedulerJobsRunning', 'i'),
                               ('TransferQueueNumUploading', 'i'),
                               ('MaxJobsRunning', 'i'),
                               ('TransferQueueMaxUploading', 'i'),
                               ('CurbMatchmaking', 'i')])

    type_constraint = 'True'
    constraint += "&& (MyType =!= \"condor_status_schedds_%s\")" % os.getpid()
    return getCondorStatusConstrained(collector_names, type_constraint,
                                      constraint, format_list,
                                      subsystem_name="schedd")

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
    logSupport.profiler("BEGIN getCondorQConstrained() :: PID = %s" % os.getpid(), "condor_q")
    out_condorq_dict = {}
    for schedd in schedd_names:
        if schedd == '':
            logSupport.log.warning("Skipping empty schedd name")
            continue
        full_constraint = type_constraint[0:]  # make copy
        if constraint is not None:
#            full_constraint = "(%s) && (%s)" % (full_constraint, constraint)
            full_constraint = "(%s) && (%s) && (MyType=!=\"condor_q_%s\")" % (full_constraint, constraint, os.getpid())
        else:
            full_constraint = "(%s) && (MyType=!=\"condor_q_%s\")" % (full_constraint, os.getpid())
        logSupport.profiler("CONSTRAINT = %s" % full_constraint, "condor_q")
        logSupport.profiler("SCHEDD = %s" % schedd, "condor_q")

        try:
            condorq = condorMonitor.CondorQ(schedd)
            condorq.load(full_constraint, format_list)
            if len(condorq.fetchStored()) > 0:
                out_condorq_dict[schedd] = condorq
        except condorMonitor.QueryError:
            logSupport.log.exception("Condor Error. Failed to talk to schedd: ")
            # If schedd not found it is equivalent to no jobs in the queue
            continue
        except RuntimeError:
            logSupport.log.exception("Runtime Error. Failed to talk to schedd %s" % schedd)
            continue
        except Exception:
            logSupport.log.exception("Unknown Exception. Failed to talk to schedd %s" % schedd)
    
    logSupport.profiler("END getCondorQConstrained() :: PID = %s" % os.getpid(), "condor_q")
    return out_condorq_dict


#
# Return a dictionary of collectors containing classads of a certain kind 
# Each element is a condorStatus
#
# If not all the jobs of the schedd has to be considered,
# specify the appropriate additional constraint
#
def getCondorStatusConstrained(collector_names, type_constraint, constraint=None,
                               format_list=None, subsystem_name=None):
    # Jack Lundell
    logSupport.profiler("BEGIN getCondorStatusConstrained() :: PID = %s" % os.getpid(), "condor_status")
    out_status_dict = {}
    for collector in collector_names:
        full_constraint = type_constraint[0:]  # make copy
        if constraint is not None:
            # Jack Lundell
#            full_constraint = "(%s) && (%s)" % (full_constraint, constraint)
            full_constraint = "(%s) && (%s) && (MyType=!=\"condor_status_%s\")" % (full_constraint, constraint, os.getpid())
        else:
            full_constraint = "(%s) && (MyType =!=\"condor_status_%s\")" % (full_constraint, os.getpid())
        logSupport.profiler("COLLECTOR = %s" % collector, "condor_status")

        try:
            status = condorMonitor.CondorStatus(subsystem_name=subsystem_name,
                                                pool_name=collector)
            status.load(full_constraint, format_list)
        except condorMonitor.QueryError:
            if collector is not None:
                msg = "Condor Error. Failed to talk to collector %s: " % collector
            else:
                msg = "Condor Error. Failed to talk to collector: "
            logSupport.log.exception(msg)
            # If collector not found it is equivalent to no classads
            continue
        except RuntimeError:
            logSupport.log.exception("Runtime error. Failed to talk to collector: ")
            continue
        except Exception:
            logSupport.log.exception("Unknown error. Failed to talk to collector: ")
            continue

        if len(status.fetchStored()) > 0:
            out_status_dict[collector] = status

        logSupport.profiler("CONSTRAINT = %s" % full_constraint, "condor_status")
        logSupport.profiler("FORMAT_LIST = %s" % format_list, "condor_status")
    logSupport.profiler("END getCondorStatusConstrained() :: PID = %s" % os.getpid(), "condor_status")
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
        old_unique = set()
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
    keys=sorted(condorq_el.keys())
    if condorq_match_list is not None:
        # whitelist... keep only the ones listed
        allkeys=keys
        keys=[]
        for k in allkeys:
            if k in condorq_match_list:
                keys.append(k)
    for k in keys:
        out.append((k, condorq_el[k]))
    return tuple(out)


def getGlideinCpusNum(glidein, estimate_cpus=True):
    """
    Given the glidein data structure, get the GLIDEIN_CPUS and GLIDEIN_ESTIMATED_CPUS configured.
    If estimate_cpus is false translate keywords to numerical equivalent, otherwise estimate CPUs
    If GLIDEIN_CPUS is not configured ASSUME it to be 1, if it is set to auto/slot/-1 or node/0,
    use GLIDEIN_ESTIMATED_CPUS if provided, otherwise ASSUME it to be 1
    In the future there should be better guesses
    """
    # TODO: better estimation of cpus available on resources (e.g. average of obtained ones)
   
    cpus = str(glidein['attrs'].get('GLIDEIN_CPUS', 1))
    try:
        glidein_cpus = int(cpus)
        if estimate_cpus and glidein_cpus <= 0:
            cpus = str(glidein['attrs'].get('GLIDEIN_ESTIMATED_CPUS', 1))
            return int(cpus)
        else:
            return glidein_cpus
    except ValueError:
        if estimate_cpus:
            cpus = str(glidein['attrs'].get('GLIDEIN_ESTIMATED_CPUS', 1))
            return int(cpus)
        else:
            cpus_upper = cpus.upper()
            if cpus_upper == 'AUTO' or cpus_upper == 'SLOT':
                return -1
            if cpus_upper == 'NODE':
                return 0
            raise ValueError


def getHAMode(frontend_data):
    """
    Given the frontendDescript return if this frontend is to be run
    in 'master' or 'slave' mode
    """

    mode = 'master'
    ha = getHASettings(frontend_data)
    if ha and (ha.get('enabled').lower() == 'true'):
        mode = 'slave'
    return mode


def getHACheckInterval(frontend_data):
    """
    Given the frontendDescript return if this frontend is to be run
    in 'master' or 'slave' mode
    """
    interval = 0
    ha = getHASettings(frontend_data)
    if ha and ha.get('check_interval'):
        interval = int(ha.get('check_interval'))
    return interval


def getHASettings(frontend_data):
    ha = None
    if frontend_data.get('HighAvailability'):
        ha = eval(frontend_data.get('HighAvailability'))
    return ha
