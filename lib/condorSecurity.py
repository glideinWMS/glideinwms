#
# Description:
#   This module implements classes that will setup
#   the Condor security as needed
#
# Author:
#   Igor Sfiligoi @ UCSD (Apr 2010)
#

import os

###############
#
# Base classes
#
###############

########################################
# This class contains the state of the
# Condor environment
#
# All info is in the state attribute
class SecEnvState:
    def __init__(self,filter):
        # filter is a dictionary of [contex]=[feature list]
        self.filter=filter
        self.load()
    
    #################################
    # Restore back to what you found
    # when creating this object
    def restore(self):
        for context in self.state.keys():
            for feature in self.state[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                old_val=self.state[context][feature]
                if old_val!=None:
                    os.environ[env_key]=old_val
                else:
                    del os.environ[env_key]

    ##########################################
    # Load the environment state into
    # Almost never called by the user
    # It gets called automatically by __init__
    def load(self):
        filter=self.filter
        saved_state={}
        for context in filter.keys():
            if not saved_state.has_key(context):
                saved_state[context]={}
            for feature in filter[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                if os.environ.has_key(env_key):
                    saved_state[context][feature]=os.environ[env_key]
                else:
                    saved_state[context][feature]=None # unlike requests, we want to remember there was nothing
        self.state=saved_state

###############################################################
# This special value will unset any value and leave the default
# This is different than None, that will not do anything
UNSET_VALUE='UNSET'

#############################################
# This class handle requests for ensuring
# the security state is in a particular state
class SecEnvRequest:
    def __init__(self,requests=None):
        # requests is a dictionary of requests [context][feature]=VAL
        self.requests={}
        if requests!=None:
            for context in requests.keys():
                for feature in requests[context].keys():
                    self.set(context,feature,requests[context][feature])

        self.saved_state=None


    ##############################################
    # Methods for accessig the requests
    def set(self,context,feature,value): # if value is None, remove the request
        if value!=None:
            if not self.requests.has_key(context):
                self.requests[context]={}
            self.requests[context][feature]=value
        elif self.requests.has_key(context):
            if self.requests[context].has_key(feature):
                del self.requests[context][feature]
                if len(self.requests[context].keys())==0:
                    del self.requests[context]
    
    def get(self,context,feature):
        if self.requests.has_key(context):
            if self.requests[context].has_key(feature):
                return self.requests[context][feature]
            else:
                return None
        else:
            return None

    ##############################################
    # Methods for preserving the old state

    def has_saved_state(self):
        return (self.saved_state!=None)

    def save_state(self):
        if self.has_saved_state():
            raise RuntimeError,"There is already a saved state! Restore that first."
        filter={}
        for c in self.requests.keys():
            filter[c]=self.requests[c].keys()
            
        self.saved_state=self.SecEnvState(filter)

    def restore_state(self):
        if self.saved_state==None:
            return # nothing to do

        self.saved_state.restore()
        self.saved_state=None

    ##############################################
    # Methods for changing to the desired state

    # you should call save_state before this one,
    # if you want to ever get back
    def enforce_requests(self):
        for context in self.requests.keys():
            for feature in self.requests[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                val=self.requests[context][feature]
                if val!=UNSET_VALUE:
                    os.environ[env_key]=val
                else:
                    # unset -> make sure it is not in the env after the call
                    if os.environ.has_key(env_key):
                        del os.environ[env_key]
        return

########################################################################
#
# Security protocol handhake classes
# This are the most basic features users may want to change
#
########################################################################

CONDOR_CONTEXT_LIST=('DEFAULT',
                     'ADMINISTRATOR','NEGOTIATOR','CLIENT','OWNER',
                     'READ','WRITE','DAEMON','CONFIG',
                     'ADVERTISE_MASTER','ADVERTISE_STARTD','ADVERTISE_SCHEDD')

CONDOR_PROTO_FEATURE_LIST=('AUTHENTICATION',
                           'INTEGRITY','ENCRYPTION',
                           'NEGOTIATION')

CONDOR_PROTO_VALUE_LIST=('NEVER','OPTIONAL','PREFERRED','REQUIRED')

########################################
class EnvProtoState(SecEnvState):
    def __init__(self,filter=None):
        if filter!=None:
            # validate filter
            for c in filter.keys():
                if not (c in CONDOR_CONTEXT_LIST):
                    raise ValueError, "Invalid contex '%s'. Must be one of %s"%(c,CONDOR_CONTEXT_LIST)
                for f in filter[c]:
                    if not (f in CONDOR_PROTO_FEATURE_LIST):
                        raise ValueError, "Invalid feature '%s'. Must be one of %s"%(f,CONDOR_PROTO_FEATURE_LIST)
        else:
            # do not filter anything out... add all
            filter={}
            for c in CONDOR_CONTEXT_LIST:
                cfilter=[]
                for f in CONDOR_PROTO_FEATURE_LIST:
                    cfilter.append(f)
                filter[c]=cfilter
        
        SecEnvState.__init__(self,filter)

#########################################
# Same as SecEnvRequest, but check that
# the context and feature are related
# to the Condor protocol handling
class ProtoRequest(SecEnvRequest):
    def set(self,context,feature,value): # if value is None, remove the request
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError, "Invalid security context '%s'."%context
        if not (feature in CONDOR_AUTH_FEATURE_LIST):
            raise ValueError, "Invalid authentication feature '%s'."%feature
        if not (value in (CONDOR_AUTH_VALUE_LIST+(UNSET_VALUE,))):
            raise ValueError, "Invalid value type '%s'."%value
        SecEnvRequest.set(self,context,feature,value)

    def get(self,context,feature):
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError, "Invalid security context '%s'."%context
        if not (feature in CONDOR_AUTH_FEATURE_LIST):
            raise ValueError, "Invalid authentication feature '%s'."%feature
        return SecEnvRequest.get(self,context,feature)

