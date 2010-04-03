#
# Description:
#   This module implements classes that will setup
#   the Condor security as needed
#
# Author:
#   Igor Sfiligoi @ UCSD (Apr 2010)
#

import os

CONDOR_CONTEXT_LIST=('DEFAULT',
                     'ADMINISTRATOR','NEGOTIATOR','CLIENT','OWNER',
                     'READ','WRITE','DAEMON','CONFIG',
                     'ADVERTISE_MASTER','ADVERTISE_STARTD','ADVERTISE_SCHEDD')

CONDOR_AUTH_FEATURE_LIST=('AUTHENTICATION',
                          'INTEGRITY','ENCRYPTION',
                          'NEGOTIATION')

CONDOR_AUTH_VALUE_LIST=('NEVER','OPTIONAL','PREFERRED','REQUIRED')


class AuthCondorSecurity:
    def __init__(self,requests=None):
        # requests is a dictionary of requests
        # this base class defines integrity and encryption
        # children can expand that to other requests
        self.requests={}
        if requests!=None:
            for context in requests.keys():
                for feature in requests[context].keys():
                    self.set(context,feature,requests[context][feature])

        self.saved_state=None


    ##############################################
    # Methods for accessig the requests
    def set(self,context,feature,value): # if value is None, remove the request
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError, "Invalid security context '%s'."%context
        if not (feature in CONDOR_AUTH_FEATURE_LIST):
            raise ValueError, "Invalid authentication feature '%s'."%feature
        if not (value in CONDOR_AUTH_VALUE_LIST):
            raise ValueError, "Invalid value type '%s'."%value
        self.set_nocheck(context,feature,value)

    def get(self,context,feature):
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError, "Invalid security context '%s'."%context
        if not (feature in CONDOR_AUTH_FEATURE_LIST):
            raise ValueError, "Invalid authentication feature '%s'."%feature
        return self.get_nocheck(context,feature)

    ##############################################
    # Methods for preserving the old state

    def has_saved_state(self):
        return (self.saved_state!=None)

    def save_state(self):
        if self.has_saved_state():
            raise RuntimeError,"There is already a saved state! Restore that first."
        self.saved_state=self.auth_save_state()

    def restore_state(self):
        if self.saved_state==None:
            return # nothing to do

        self.auth_restore_state(self.saved_state)
        
        self.saved_state=None

    ##############################################
    # Methods for changing to the desired state

    # you should call save_state before this one,
    # if you want to ever get back
    def enforce_requests(self):
        self.auth_enforce_requests(self.requests)

    #################################
    # INTERNAL, to be used with care
    def set_nocheck(self,context,feature,value): # if value is None, remove the request
        if value!=None:
            if not self.requests.has_key(context):
                self.requests[context]={}
            self.requests[context][feature]=value
        elif self.requests.has_key(context):
            if self.requests[context].has_key(feature):
                del self.requests[context][feature]
                if len(self.requests[context].keys())==0:
                    del self.requests[context]
    

    #################################
    # INTERNAL, to be used with care
    def get_nocheck(self,context,feature):
        if self.requests.has_key(context):
            if self.requests[context].has_key(feature):
                return self.requests[context][feature]
            else:
                return None
        else:
            return None

    #################################
    # INTERNAL, do not redefine
    def auth_save_state(self):
        saved_state={}
        for context in self.requests.keys():
            if not saved_state.has_key(context):
                saved_state[context]={}
            for feature in self.requests[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                if os.environ.has_key(env_key):
                    saved_state[context][feature]=os.environ[env_key]
                else:
                    saved_state[context][feature]=None # unlike requests, we want to remember there was nothing
        return saved_state
    
    #################################
    # INTERNAL, do not redefine
    def auth_restore_state(self,saved_state):
        for context in saved_state.keys():
            for feature in saved_state[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                old_val=saved_state[context][feature]
                if old_val!=None:
                    os.environ[env_key]=old_val
                else:
                    del os.environ[env_key]

    #################################
    # INTERNAL, do not redefine
    def auth_enforce_requests(self,requests):
        for context in requests.keys():
            for feature in requests[context].keys():
                condor_key="SEC_%s_%s"%(context,feature)
                env_key="_CONDOR_%s"%condor_key
                val=requests[context][feature]
                os.environ[env_key]=val
        return
