#
#
# Description:
#  This module implements plugins for the VO frontend
#
# Author:
#  Igor Sfiligoi  (since Mar 31st 2009)
#

import os,os.path
import sets
import pickle
import glideinFrontendLib


######################################################
#                                                    #
####    Proxy plugins                             ####
#                                                    #
######################################################

############################################
#
# This plugin always returns the first proxy
# Useful when there is only one proxy
# or for testing
#
class ProxyFirst:
    def __init__(self,config_dir,proxy_list):
        self.proxy_list=proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self,):
        return []

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self,):
        return []

    # get the proxies, given the condor_q and condor_status data
    def get_proxies(condorq_dict,condorq_dict_types,
                    status_dict,status_dict_types):
        return [self.proxy_list[0]]

############################################
#
# This plugin returns all the proxies
# This is can be a very useful default policy
#
class ProxyAll:
    def __init__(self,config_dir,proxy_list):
        self.proxy_list=proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return []

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []

    # get the proxies, given the condor_q and condor_status data
    def get_proxies(condorq_dict,condorq_dict_types,
                    status_dict,status_dict_types):
        return self.proxy_list

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
    def __init__(self,config_dir,proxy_list):
        self.proxy_list=proxy_list

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return ('User',)

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []

    # get the proxies, given the condor_q and condor_status data
    def get_proxies(condorq_dict,condorq_dict_types,
                    status_dict,status_dict_types):
        users_set=glideinFrontendLib.getCondorQUsers(condorq_dict)
        return self.get_proxies_from_cardinality(len(users_set))

    #############################
    # INTERNAL
    #############################

    # return the proxies based on data held by the class
    def get_proxies_from_cardinality(self,nr_requested_proxies):
        nr_proxies=len(self.proxy_list)

        if nr_requested_proxies>=nr_proxies:
            # wants all of them, no need to select
            return self.proxy_list
        
        out_proxies=[]
        for i in range(nr_requested_proxies):
            out_proxies.append(self.proxy_list[i])

        return out_proxies

######################################################################
#
# This plugin implements a user-based round-robin policy
# The same proxies are used as long as the users don't change
#  (we keep a disk-based memory for this purpose)
# Once any user leaves, the most used proxy is returned to the pool
# If a new user joins, the least used proxy is obtained from the pool
#
class ProxyUserRR:
    def __init__(self,config_dir,proxy_list):
        self.proxy_list=proxy_list
        self.config_dir=config_dir
        self.config_fname="%s/proxy_user_rr.dat"%self.config_dir
        self.load()

    # what job attributes are used by this plugin
    def get_required_job_attributes(self):
        return ('User',)

    # what glidein attributes are used by this plugin
    def get_required_classad_attributes(self):
        return []

    # get the proxies, given the condor_q and condor_status data
    def get_proxies(condorq_dict,condorq_dict_types,
                    status_dict,status_dict_types):
        new_users_set=glideinFrontendLib.getCondorQUsers(condorq_dict)
        old_users_set=self.config_data['users_set']
        if old_users_set==new_users_set:
            return self.get_proxies_from_data()

        # users changed
        removed_users=old_users_set-new_users_set
        added_users=new_users_set-old_users_set

        if len(removed_users)>0:
            self.shrink_proxies(len(removed_users))
        if len(added_users)>0:
            self.expand_proxies(len(added_users))

        self.config_data['users_set']=new_users_set
        self.save()

        return self.get_proxies_from_data()

    #############################
    # INTERNAL
    #############################

    # load from self.config_fname into self.config_data
    # if the file does not exist, create a new config_data
    def load(self):
        if os.path.isfile(self.config_fname):
            fd=open(self.config_fname,"r")
            try:
                self.config_data=pickle.load(fd)
            finally:
                fd.close()
        else:
            self.config_data={'users_set':sets.Set(),
                              'proxies_range':{'min':0,'max':0}}

        return

    # save self.config_data into self.config_fname
    def save(self):
        # fist save in a tmpfile
        tmpname="%s~"%self.config_fname
        try:
            os.unlink(tmpname)
        except:
            pass # just trying
        fd=open(tmpname,"w")
        try:
            pickle.dump(self.config_data,fd,0) # use ASCII version of protocol
        finally:
            fd.close()

        # then atomicly move it in place
        os.rename(tmpname,self.config_fname)

        return

    # remove a number of proxies from the internal data
    def shrink_proxies(self,nr):
        min_proxy_range=self.config_data['proxies_range']['min']
        max_proxy_range=self.config_data['proxies_range']['max']

        min_proxy_range+=nr
        if min_proxy_range>max_proxy_range:
            raise RuntimeError,"Cannot shrink so much: %i requested, %i available"%(nr, max_proxy_range-self.config_data['proxies_range']['min'])
        
        self.config_data['proxies_range']['min']=min_proxy_range

        return

    # add a number of proxies from the internal data
    def expand_proxies(self,nr):
        min_proxy_range=self.config_data['proxies_range']['min']
        max_proxy_range=self.config_data['proxies_range']['max']

        max_proxy_range+=nr
        if min_proxy_range>max_proxy_range:
            raise RuntimeError,"Did we hit wraparound after the requested exansion of %i? min %i> max %i"%(nr, min_proxy_range,max_proxy_range)

        self.config_data['proxies_range']['max']=max_proxy_range

        return

    # return the proxies based on data held by the class
    def get_proxies_from_data(self):
        nr_proxies=len(self.proxy_list)

        min_proxy_range=self.config_data['proxies_range']['min']
        max_proxy_range=self.config_data['proxies_range']['max']
        nr_requested_proxies=max_proxy_range-min_proxy_range;

        if nr_requested_proxies>=nr_proxies:
            # wants all of them, no need to select
            return self.proxy_list
        
        out_proxies=[]
        for i in range(min_proxy_range,max_proxy_range):
            real_i=i%nr_proxies
            out_proxies.append(self.proxy_list[i])

        return out_proxies
    
###################################################################

# Being plugins, users are not expected to directly reference the classes
# They should go throug the dictionaries below to find the appropriate plugin

proxy_plugins={'ProxyAll':ProxyAll,
               'ProxyUserRR':ProxyUserRR,
               'ProxyFirst':ProxyFirst,'ProxyUserCardinality':ProxyUserCardinality}

