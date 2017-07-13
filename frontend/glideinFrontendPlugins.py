from __future__ import absolute_import
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#  This module implements plugins for the VO frontend
#
# Author:
#  Igor Sfiligoi  (since Mar 31st 2009)
#

import os
import copy
import time
import random
import math
import collections
from glideinwms.lib import logSupport
from glideinwms.lib import util
from . import glideinFrontendLib
from . import glideinFrontendInterface


################################################################################
#                                                                              #
####    Proxy plugins                                                       ####
#                                                                              #
# All plugins implement the following interface:                               #
#   __init_(config_dir,proxy_list)                                             #
#     Constructor, config_dir may be used for internal config/cache files      #
#   get_required_job_attributes()                                              #
#     Return the list of required condor_q attributes                          #
#   get_required_classad_attributes()                                          #
#     Return the list of required condor_status attributes                     #
#   update_usermap(condorq_dict,condorq_dict_types,                            #
#           status_dict,status_dict_types)                                     #
#     Update usermap.  This is called once per iteration                       #
#   get_credentials(params_obj=None,
#           credential_type=None, trust_domain=None)                           #
#     Return a list of credenital that match the input criteria                #
#     This is called in two places, once in globals to return all credentials  #
#     and once when advertizing actual requests.
#     If params_obj is NOT None, then this function is responsible for calling
#     add_usage_details() for each returned credential to determine idle and max run
#     If called multiple time, it is guaranteed that                           #
#        if the index is the same, the proxy is (logicaly) the same            #
#     credential_type will limit the returned credentials to a particular type #
#     trust_domain will limit the returned credentials to a particular domain  #
#                                                                              #
################################################################################

############################################
#
# This plugin always returns the first proxy
# Useful when there is only one proxy
# or for testing
#
class ProxyFirst:
    def __init__(self, config_dir, proxy_list):
        self.cred_list = proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return []

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []

    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        return

    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        for cred in self.cred_list:
            if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                continue
            if (params_obj is not None):
                cred.add_usage_details(params_obj.min_nr_glideins, params_obj.max_run_glideins)
            return [cred]
        return []

############################################
#
# This plugin returns all the proxies
# This is can be a very useful default policy
#
class ProxyAll:
    def __init__(self, config_dir, proxy_list):
        self.cred_list = proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return []

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []


    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        return


    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        rtnlist = []
        for cred in self.cred_list:
            if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                continue
            rtnlist.append(cred)
        if (params_obj is not None):
            rtnlist = fair_assign(rtnlist, params_obj)
        return rtnlist

##########################################################
#
# This plugin uses the first N proxies
# where N is the number of users currently in the system
#
# This is useful if the first proxies are higher priority
# then the later ones
# Also good for testing
#
class ProxyUserCardinality:
    def __init__(self, config_dir, proxy_list):
        self.cred_list = proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return (('User', 's'),)

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []
    
    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        self.users_set = glideinFrontendLib.getCondorQUsers(condorq_dict)
        return


    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        rtnlist=self.get_proxies_from_cardinality(len(self.users_set), credential_type, trust_domain)
        if (params_obj is not None):
            rtnlist=fair_assign(rtnlist, params_obj)

        #Uncomment to print out assigned proxy allocations
        #print_list(rtnlist)
        #logSupport.log.debug("Total: %d %d" % (params_obj.min_nr_glideins,params_obj.max_run_glideins))
        return rtnlist

    #############################
    # INTERNAL
    #############################

    # return the proxies based on data held by the class
    def get_proxies_from_cardinality(self, nr_requested_proxies,credential_type=None, trust_domain=None):
        rtnlist=[]
        for cred in self.cred_list:
            if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                continue
            if len(rtnlist)<nr_requested_proxies:
                rtnlist.append(cred)
        return rtnlist

#####################################################################
#
# Given a 'normal' credential, create sub-credentials based on the ProjectName
# attribute of jobs
#
class ProxyProjectName:

    def __init__(self, config_dir, proxy_list):
        self.cred_list = proxy_list
        self.proxy_list = proxy_list
        self.total_jobs = 0
        self.project_count = {}

    # This plugin depends on the ProjectName and User attributes in the job
    def get_required_job_attributes(self):
        return (('ProjectName', 's'), )

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []

    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        self.project_count = {}
        self.total_jobs = 0
        # Get both set of users and number of jobs for each user
        for schedd_name in list(condorq_dict.keys()):
            condorq_data = condorq_dict[schedd_name].fetchStored()
            for job in list(condorq_data.values()):
                if job['JobStatus'] != 1:
                    continue
                self.total_jobs += 1
                if job.get('ProjectName', '') != '':
                    if job.get('ProjectName') in self.project_count:
                        self.project_count[job.get('ProjectName', '')] += 1
                    else:
                        self.project_count[job.get('ProjectName', '')] = 1
        return

    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        if not params_obj:
            logSupport.log.debug("params_obj is None returning the credentials without the project_id Information")
            return self.proxy_list
        # Determine a base credential to use; we'll copy this and alter the project ID.
        base_cred = None
        for cred in self.proxy_list:
            if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain != trust_domain):
                continue
            if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                continue
            base_cred = cred
            break
        if not base_cred:
            return []

        # Duplicate the base credential; one per project in use.
        # Assign load proportional to the number of jobs.
        creds = []
        for project, job_count in list(self.project_count.items()):
            if not project:
                creds.append(base_cred)
            else:
                cred_copy = copy.deepcopy(base_cred)
                cred_copy.project_id = project
                creds.append(cred_copy)

            cred_max = int(math.ceil(job_count * params_obj.max_run_glideins / float(self.total_jobs)))
            cred_idle = int(math.ceil(job_count * params_obj.min_nr_glideins / float(self.total_jobs)))
            creds[-1].add_usage_details(cred_max, cred_idle)
        return creds





######################################################################
#
# This plugin implements a user-based round-robin policy
# The same proxies are used as long as the users don't change
#  (we keep a disk-based memory for this purpose)
# Once any user leaves, the most used credential is rotated to the back of the list
# If more users enter, they will reach farther down the list to access
#   less used credentials
class ProxyUserRR:
    def __init__(self, config_dir, proxy_list):
        self.proxy_list = proxy_list
        self.config_dir = config_dir
        self.config_fname = "%s/proxy_user_rr.dat" % self.config_dir
        self.load()

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return (('User', 's'),)

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []
    
    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        self.users_set = glideinFrontendLib.getCondorQUsers(condorq_dict)
        return

    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        new_users_set = self.users_set
        old_users_set = self.config_data['users_set']

        # users changed
        removed_users = old_users_set - new_users_set
        added_users = new_users_set - old_users_set

        if len(removed_users) > 0:
            self.shuffle_proxies(len(removed_users))

        self.config_data['users_set'] = new_users_set
        self.save()

        rtnlist=[]
        num_cred=0
        for cred in self.config_data['proxy_list']:
            if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                continue
            rtnlist.append(cred)
            num_cred=num_cred+1
            if (num_cred >= len(new_users_set)):
                break
                
        if (params_obj is not None):
            rtnlist=fair_assign(rtnlist, params_obj)
        return rtnlist

    #############################
    # INTERNAL
    #############################

    def load(self):
        """load from self.config_fname into self.config_data
        if the file does not exist, create a new config_data
        """
        if not os.path.isfile(self.config_fname):
            nr_proxies = len(self.proxy_list)
            self.config_data = {'users_set': set(),
                                'proxy_list': self.proxy_list}
        else:
            self.config_data = util.file_pickle_load(self.config_fname)
            for p in self.proxy_list:
                found = False
                for c in self.config_data['proxy_list']:
                    if p.filename == c.filename:
                        found = True
                if not found:
                    self.config_data['proxy_list'].append(p)
        return

    def save(self):
        """save self.config_data into self.config_fname"""
        # tmp file name is now *.PID.tmp instead of *~
        util.file_pickle_dump(self.config_fname, self.config_data, protocol=0)  # use ASCII version of protocol
        return

    # shuffle a number of proxies from the internal data
    def shuffle_proxies(self, nr):
        list = self.config_data['proxy_list']
        for t in range(nr):
            list.append(list.pop(0))
        return

######################################################################
#
# This plugin implements a user-based mapping policy
#  with possibility of recycling of accounts:
#  * when a user first enters the system, it gets mapped to a
#    pilot proxy that was not used for the longest time
#  * for existing users, just use the existing mapping
#  * if an old user comes back, it may be mapped to the old account, if not
#    yet recycled, else it is treated as a new user
#
class ProxyUserMapWRecycling:
    def __init__(self, config_dir, proxy_list):
        self.proxy_list = proxy_list
        self.config_dir = config_dir
        self.config_fname = "%s/proxy_usermap_wr.dat" % self.config_dir
        self.load()

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return (('User', 's'),)

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []
    
    def update_usermap(self, condorq_dict, condorq_dict_types,
                    status_dict, status_dict_types):
        self.num_user_jobs={}
        self.total_jobs=0
        # Get both set of users and number of jobs for each user
        for schedd_name in list(condorq_dict.keys()):
            condorq_data = condorq_dict[schedd_name].fetchStored()
            for jid in list(condorq_data.keys()):
                job = condorq_data[jid]
                if job['JobStatus']==1:
                    if job['User'] in self.num_user_jobs:
                        self.num_user_jobs[job['User']]=self.num_user_jobs[job['User']]+1
                    else:
                        self.num_user_jobs[job['User']]=1
                    self.total_jobs=self.total_jobs+1
        self.users_list = list(self.num_user_jobs.keys())
        return

    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        users = self.users_list
        out_proxies = []

        total_user_map = self.config_data['user_map']

        # check if there are more users than proxies
        if (credential_type is None) or (trust_domain is None):
            # if no type or trust_domain is returned
            # then we return the full list for the 
            # global advertisement
            rtnlist=[]
            for type in list(total_user_map.keys()):
                for trust_domain in list(total_user_map[type].keys()):
                    for k in list(total_user_map[type][trust_domain].keys()):
                        rtnlist.append(total_user_map[type][trust_domain][k]['proxy'])
            return rtnlist
        else:
            if (credential_type not in total_user_map):
                return []
            if (trust_domain not in total_user_map[credential_type]):
                return []
            user_map=total_user_map[credential_type][trust_domain]

        for user in users:
            # If the user is not already mapped,
            # find an appropriate credential
            # skip all that do not match auth method or trust_domain
                
            if user not in user_map:
                keys = list(user_map.keys())
                found=False
                new_key=""
                for k in keys:
                    cred=user_map[k]['proxy']
                    if (trust_domain is not None) and (hasattr(cred, 'trust_domain')) and (cred.trust_domain!=trust_domain):
                        continue
                    if (credential_type is not None) and (hasattr(cred, 'type')) and (not cred.supports_auth_method(credential_type)):
                        continue
                    #Someone is already using this credential
                    if (k in users):
                        continue
                    if (not found):
                        #This is the first non-matching credential, use it
                        new_key=k;
                        found=True
                        continue
                    # At this point, we have already have a credential,
                    # so switch to a new one only if this one is less used.
                    if (user_map[k]['last_seen'] < user_map[new_key]['last_seen']):
                        new_key = k
                        found=True
                if found:
                    user_map[user] = user_map[new_key]
                    del user_map[new_key]
                else:
                    logSupport.log.error("Could not find a suitable credential for user %s!" % user)
                    #We could not find a suitable credential!
                    continue
            
            cel = user_map[user]

            # Out of the max_run glideins,
            # Allocate proportionally out of the total jobs
            if (params_obj is not None):
                this_max=self.num_user_jobs[user]*params_obj.max_run_glideins/self.total_jobs
                this_idle=self.num_user_jobs[user]*params_obj.min_nr_glideins/self.total_jobs
                if (this_max<=0):
                    this_max=1
                if (this_idle<=0):
                    this_idle=1
                cel['proxy'].add_usage_details(this_idle, this_max)
            out_proxies.append(cel['proxy'])
            # save that you have indeed seen the user 
            cel['last_seen'] = time.time()
                

        # save changes
        self.save()
        
        #Uncomment to print out proxy allocations 
        #print_list(out_proxies)
        #if params_obj is not None:
        #    logSupport.log.debug("Total: %d %d" % (params_obj.min_nr_glideins,params_obj.max_run_glideins))

        return out_proxies

    #############################
    # INTERNAL
    #############################
    def add_proxy(self, user_map, proxy):
        type=proxy.type
        trust=proxy.trust_domain
        if (type not in user_map):
            user_map[type]={}
        if (trust not in user_map[type]):
            user_map[type][trust]={}
        idx=self.config_data['first_free_index']
        user_map[type][trust][idx] = {'proxy':proxy,
                     'proxy_index':idx,
                     'last_seen':0} #0 is the oldest UNIX have ever seen ;)
        self.config_data['first_free_index'] = idx + 1   

    # load from self.config_fname into self.config_data
    # if the file does not exist, create a new config_data
    def load(self):
        if not os.path.exists(self.config_fname):
            # no cache, create new cache structure from scratch
            self.config_data = {}
            user_map = {}
            self.config_data['first_free_index'] = 0
            nr_proxies = len(self.proxy_list)
            for i in range(nr_proxies):
                # use numbers for keys, so we are sure will not match to any user string
                self.add_proxy(user_map, self.proxy_list[i]) 
            self.config_data['user_map'] = user_map
        else:
            # load cache
            self.config_data = util.file_pickle_load(self.config_fname)

            # if proxies changed, remove old ones and insert the new ones
            cached_proxies = set() # here we will store the list of proxies in the cache

            user_map = self.config_data['user_map']

            # need to iterate, since not indexed by proxy name
            keys = list(user_map.keys())
            for type in list(user_map.keys()):
                for trust_domain in list(user_map[type].keys()):
                    for k in list(user_map[type][trust_domain].keys()):
                        el = user_map[type][trust_domain][k]
                        el_proxy = el['proxy']
                        el_proxyname = el['proxy'].filename
                        found=False
                        for p in self.proxy_list:
                            if (p.filename == el_proxyname):
                                cached_proxies.add(el_proxyname)
                                found=True
                        if not found:
                            # cached proxy not used anymore... remove from cache
                            del user_map[type][trust_domain][k]
            for proxy in self.proxy_list:
                if proxy.filename not in cached_proxies:
                    self.add_proxy(user_map, proxy) 
        return

    def save(self):
        """save self.config_data into self.config_fname"""
        # tmp file name is now *.PID.tmp instead of *~
        util.file_pickle_dump(self.config_fname, self.config_data, protocol=0)  # use ASCII version of protocol
        return


###############################################
# INTERNAL to proxy_plugins, don't use directly

# convert a list into a list of (index, value)

#
# NOTE: This will not work if proxy order is changed between reconfigs :(
#

def list2ilist(lst):
    out = []
    for cred in lst:
        out.append((cred.proxy_id, cred.filename))
    return out


def createCredentialList(elementDescript):
    """ Creates a list of Credentials for a proxy plugin """
    credential_list = []
    num = 0
    for proxy in elementDescript.merged_data['Proxies']:
        credential_list.append(glideinFrontendInterface.Credential(num, proxy, elementDescript))
        num += 1
    return credential_list


def fair_split(i, n, p):
    """
    Split n requests amongst p proxies 
    Returns how many requests go to the i-th proxy
    """
    n1=int(n)
    i1=int(i)
    p1=int(p)
    return int((n1*i1)/p1)-int((n1*(i1-1))/p1)


def random_split(n, p):
    random_arr = [fair_split(i, n, p) for i in range(p)]
    random.shuffle(random_arr)
    return random_arr


def print_list(cred_list):
    for c in cred_list:
        logSupport.log.debug("Cred: %s %d %d" % (c.filename, c.req_idle, c.req_max_run))


def fair_assign(cred_list, params_obj):
    """
    Assigns requests to each credentials in cred_list
    max run will remain constant between iterations
    req idle will be shuffled each iteration.

    Note that shuffling will tend towards 
    rounding up ReqIdle over the long run,
    but that, since this is partially a throttling
    mechanism, it is okay to slow this down a little
    bit with shuffling.
    """
    i=1
    total_idle=params_obj.min_nr_glideins
    total_max=params_obj.max_run_glideins
    num_cred=len(cred_list)
    random_arr=random_split(total_idle, num_cred)
    for cred in cred_list:
        this_idle=random_arr[i-1]
        this_max=fair_split(i, total_max, num_cred)
        # Never send more idle than max running
        if this_idle>this_max:
            this_idle=this_max
        cred.add_usage_details(this_idle, this_max)
        i=i+1
    return cred_list


###################################################################

# Being plugins, users are not expected to directly reference the classes
# They should go throug the dictionaries below to find the appropriate plugin

proxy_plugins = {'ProxyAll':ProxyAll,
               'ProxyUserRR':ProxyUserRR,
               'ProxyFirst':ProxyFirst,
               'ProxyUserCardinality':ProxyUserCardinality,
               'ProxyUserMapWRecycling':ProxyUserMapWRecycling,
               'ProxyProjectName':ProxyProjectName}
