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
import time
import sets
import pickle
import random
import logSupport
import glideinFrontendLib
import glideinFrontendInterface


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
            if (trust_domain != None) and (hasattr(cred,'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type != None) and (hasattr(cred,'type')) and (cred.type!=credential_type):
                continue
            if (params_obj!=None):
                cred.add_usage_details(params_obj.min_nr_glideins,params_obj.max_run_glideins)
            return [cred]

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
        rtnlist=[]
        for cred in self.cred_list:
            if (trust_domain != None) and (hasattr(cred,'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type != None) and (hasattr(cred,'type')) and (cred.type!=credential_type):
                continue
            rtnlist.append(cred)
        if (params_obj!=None):
            rtnlist=fair_assign(rtnlist,params_obj)
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
        rtnlist=self.get_proxies_from_cardinality(len(self.users_set),credential_type,trust_domain)
        if (params_obj!=None):
            rtnlist=fair_assign(rtnlist,params_obj)
        return rtnlist

    #############################
    # INTERNAL
    #############################

    # return the proxies based on data held by the class
    def get_proxies_from_cardinality(self, nr_requested_proxies,credential_type=None, trust_domain=None):
        rtnlist=[]
        for cred in self.cred_list:
            if (trust_domain != None) and (hasattr(cred,'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type != None) and (hasattr(cred,'type')) and (cred.type!=credential_type):
                continue
            if len(rtnlist)<nr_requested_proxies:
                rtnlist.append(cred)
        return rtnlist

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
        if old_users_set == new_users_set:
            return self.get_proxies_from_data()

        # users changed
        removed_users = old_users_set - new_users_set
        added_users = new_users_set - old_users_set

        if len(removed_users) > 0:
            self.shuffle_proxies(len(removed_users))

        self.config_data['users_set'] = new_users_set
        self.save()

        rtnlist=[]
        for cred in self.config_data['proxy_list']:
            if (trust_domain != None) and (hasattr(cred,'trust_domain')) and (cred.trust_domain!=trust_domain):
                continue
            if (credential_type != None) and (hasattr(cred,'type')) and (cred.type!=credential_type):
                continue
            if len(rtnlist)<nr_requested_proxies:
                rtnlist.append(cred)

        if (params_obj!=None):
            rtnlist=fair_assign(rtnlist,params_obj)
        return self.get_proxies_from_data()

    #############################
    # INTERNAL
    #############################

    # load from self.config_fname into self.config_data
    # if the file does not exist, create a new config_data
    def load(self):
        if not os.path.isfile(self.config_fname):
            nr_proxies = len(self.proxy_list)
            self.config_data = {'users_set':sets.Set(),
                              'proxy_list':proxy_list}
        else:
            fd = open(self.config_fname, "r")
            try:
                self.config_data = pickle.load(fd)
            finally:
                fd.close()

            # proxies may have changed... make sure you have them all indexed
            added_proxies = sets.Set(self.proxy_list) - sets.Set(self.config_data['proxy_list'])
            for proxy in added_proxies:
                self.config_data['proxy_list'].append(proxy)

        return

    # save self.config_data into self.config_fname
    def save(self):
        # fist save in a tmpfile
        tmpname = "%s~" % self.config_fname
        try:
            os.unlink(tmpname)
        except:
            pass # just trying
        fd = open(tmpname, "w")
        try:
            pickle.dump(self.config_data, fd, 0) # use ASCII version of protocol
        finally:
            fd.close()

        # then atomicly move it in place
        os.rename(tmpname, self.config_fname)

        return

    # shuffle a number of proxies from the internal data
    def shuffle_proxies(self, nr):
        list=self.config_data['proxy_list']
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
        self.users_list = list(glideinFrontendLib.getCondorQUsers(condorq_dict))
        return

    # get the proxies, given the condor_q and condor_status data
    def get_credentials(self, params_obj=None, credential_type=None, trust_domain=None):
        users = self.users_list
        out_proxies = []

        # check if there are more users than proxies

        user_map = self.config_data['user_map']



        for user in users:
            # If the user is not already mapped,
            # find an appropriate credential
            # skip all that do not match auth method or trust_domain
            if not user_map.has_key(user):
                keys = user_map.keys()
                found=False
                new_key=""
                for k in keys:
                    cred=user_map[k]['proxy']
                    if (trust_domain!=None) and (hasattr(cred,'trust_domain')) and (cred.trust_domain!=trust_domain):
                        continue
                    if (credential_type != None) and (hasattr(cred,'type')) and (cred.type!=credential_type):
                        continue
                    #Someone is already using this credential
                    if (k in users):
                        continue
                    if (not found):
                        #This is the first non-matching credential, use it
                        new_key=k;
                        continue
                    # At this point, we have already have a credential,
                    # so switch to a new one only if this one is less used.
                    if (user_map[k]['last_seen'] < user_map[new_key]['last_seen']):
                        new_key = k
                        found=True
                if found:
                    user_map[user] = user_map[min_key]
                    del user_map[min_key]
                else:
                    #We could not find a suitable credential!
                    pass
                cel = user_map[user]
                out_proxies.append(cel['proxy'])
                # save that you have indeed seen the user 
                cel['last_seen'] = time.time()

        # save changes
        self.save()
        
        if (params_obj!=None):
            out_proxies=fair_assign(out_proxies,params_obj)

        return out_proxies

    #############################
    # INTERNAL
    #############################

    # load from self.config_fname into self.config_data
    # if the file does not exist, create a new config_data
    def load(self):
        if not os.path.exists(self.config_fname):
            # no cache, create new cache structure from scratch
            self.config_data = {}
            user_map = {}
            nr_proxies = len(self.proxy_list)
            for i in range(nr_proxies):
                # use numbers for keys, so we are sure will not match to any user string
                user_map[i] = {'proxy':self.proxy_list[i],
                             'proxy_index':i,
                             'last_seen':0} #0 is the oldest UNIX have ever seen ;)
            self.config_data['user_map'] = user_map
            self.config_data['first_free_index'] = nr_proxies # this will be used for future updates
        else:
            # load cache
            fd = open(self.config_fname, "r")
            try:
                self.config_data = pickle.load(fd)
            finally:
                fd.close()

            # if proxies changed, remove old ones and insert the new ones
            new_proxies = sets.Set(self.proxy_list)
            cached_proxies = sets.Set() # here we will store the list of proxies in the cache

            user_map = self.config_data['user_map']

            # need to iterate, since not indexed by proxy name
            keys = user_map.keys()
            for k in keys:
                el = user_map[k]
                el_proxy = el['proxy']
                if not (el_proxy in new_proxies):
                    # cached proxy not used anymore... remove from cache
                    del user_map[k]
                else:
                    # add to the list, will process later
                    cached_proxies.add(el_proxy)

            added_proxies = new_proxies - cached_proxies
            # now that we know what proxies have been added, put them in cache
            for proxy in added_proxies:
                idx = self.config_data['first_free_index']
                # use numbers for keys, so we are user will not mutch to any user string
                user_map[idx] = {'proxy':proxy,
                               'proxy_index':idx,
                               'last_seen':0} #0 is the oldest UNIX have ever seen ;)
                self.config_data['first_free_index'] = idx + 1

        return

    # save self.config_data into self.config_fname
    def save(self):
        # fist save in a tmpfile
        tmpname = "%s~" % self.config_fname
        try:
            os.unlink(tmpname)
        except:
            pass # just trying
        fd = open(tmpname, "w")
        try:
            pickle.dump(self.config_data, fd, 0) # use ASCII version of protocol
        finally:
            fd.close()

        # then atomicly move it in place
        os.rename(tmpname, self.config_fname)

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
    credential_list=[]
    num=0
    for proxy in elementDescript.merged_data['Proxies']:
        credential_list.append(glideinFrontendInterface.Credential(num,proxy,elementDescript))
        num=num+1
    return credential_list

def fair_split(i,n,p):
    """
    Split n requests amongst p proxies 
    Returns how many requests go to the i-th proxy
    """
    n1=int(n)
    i1=int(i)
    p1=int(p)
    return int((n1*i1)/p1)-int((n1*(i1-1))/p1)

def random_split(n,p):
    random_arr=map(lambda i: fair_split(i,n,p) ,range(p))
    random.shuffle(random_arr)
    return random_arr


def fair_assign(cred_list,params_obj):
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
    random_arr=random_split(total_idle,num_cred)
    for cred in cred_list:
        this_idle=random_arr[i-1]
        this_max=fair_split(i,total_max,num_cred)
        # Never send more idle than max running
        if this_idle>this_max:
            this_idle=this_max
        cred.add_usage_details(this_idle,this_max)
        i=i+1
    return cred_list



###################################################################

# Being plugins, users are not expected to directly reference the classes
# They should go throug the dictionaries below to find the appropriate plugin

proxy_plugins = {'ProxyAll':ProxyAll,
               'ProxyUserRR':ProxyUserRR,
               'ProxyFirst':ProxyFirst,
               'ProxyUserCardinality':ProxyUserCardinality,
               'ProxyUserMapWRecycling':ProxyUserMapWRecycling}



