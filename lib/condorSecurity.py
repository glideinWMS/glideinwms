# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements classes that will setup
#   the Condor security as needed
#
# Author:
#   Igor Sfiligoi @ UCSD (Apr 2010)
#

import copy
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
class EnvState:
    def __init__(self, filter):
        # filter is a list of Condor variables to save
        self.filter = filter
        self.load()

    #################################
    # Restore back to what you found
    # when creating this object
    def restore(self):
        for condor_key in list(self.state.keys()):
            env_key = "_CONDOR_%s" % condor_key
            old_val = self.state[condor_key]
            if old_val is not None:
                os.environ[env_key] = old_val
            else:
                if os.environ.get(env_key):
                    del os.environ[env_key]

    ##########################################
    # Load the environment state into
    # Almost never called by the user
    # It gets called automatically by __init__
    def load(self):
        filter = self.filter
        saved_state = {}
        for condor_key in filter:
            env_key = "_CONDOR_%s" % condor_key
            if env_key in os.environ:
                saved_state[condor_key] = os.environ[env_key]
            else:
                saved_state[condor_key] = None  # unlike requests, we want to remember there was nothing
        self.state = saved_state


########################################
# This class contains the state of the
# security Condor environment


def convert_sec_filter(sec_filter):
    filter = []
    for context in list(sec_filter.keys()):
        for feature in sec_filter[context]:
            condor_key = f"SEC_{context}_{feature}"
            filter.append(condor_key)
    return filter


class SecEnvState(EnvState):
    def __init__(self, sec_filter):
        # sec_filter is a dictionary of [contex]=[feature list]
        EnvState.__init__(self, convert_sec_filter(sec_filter))
        self.sec_filter = sec_filter


###############################################################
# This special value will unset any value and leave the default
# This is different than None, that will not do anything
UNSET_VALUE = "UNSET"


#############################################
# This class handle requests for ensuring
# the security state is in a particular state
class SecEnvRequest:
    def __init__(self, requests=None):
        # requests is a dictionary of requests [context][feature]=VAL
        # TODO: requests can be a self initializinf dictionary of dictionaries in PY3
        self.requests = {}
        if requests is not None:
            for context in list(requests.keys()):
                for feature in list(requests[context].keys()):
                    self.set(context, feature, requests[context][feature])

        self.saved_state = None

    ##############################################
    # Methods for accessing the requests
    def set(self, context, feature, value):  # if value is None, remove the request
        if value is not None:
            if context not in self.requests:
                self.requests[context] = {}
            self.requests[context][feature] = value
        elif context in self.requests:
            if feature in self.requests[context]:
                del self.requests[context][feature]
                if len(list(self.requests[context].keys())) == 0:
                    del self.requests[context]

    def get(self, context, feature):
        if context in self.requests:
            if feature in self.requests[context]:
                return self.requests[context][feature]
            else:
                return None
        else:
            return None

    ##############################################
    # Methods for preserving the old state

    def has_saved_state(self):
        return self.saved_state is not None

    def save_state(self):
        if self.has_saved_state():
            raise RuntimeError("There is already a saved state! Restore that first.")
        filter = {}
        for c in list(self.requests.keys()):
            filter[c] = list(self.requests[c].keys())

        self.saved_state = SecEnvState(filter)

    def restore_state(self):
        if self.saved_state is None:
            return  # nothing to do

        self.saved_state.restore()
        self.saved_state = None

    ##############################################
    # Methods for changing to the desired state

    # you should call save_state before this one,
    # if you want to ever get back
    def enforce_requests(self):
        for context in list(self.requests.keys()):
            for feature in list(self.requests[context].keys()):
                condor_key = f"SEC_{context}_{feature}"
                env_key = "_CONDOR_%s" % condor_key
                val = self.requests[context][feature]
                if val != UNSET_VALUE:
                    os.environ[env_key] = val
                else:
                    # unset -> make sure it is not in the env after the call
                    if env_key in os.environ:
                        del os.environ[env_key]
        return


########################################################################
#
# Security protocol handshake classes
# This are the most basic features users may want to change
#
########################################################################

CONDOR_CONTEXT_LIST = (
    "DEFAULT",
    "ADMINISTRATOR",
    "NEGOTIATOR",
    "CLIENT",
    "OWNER",
    "READ",
    "WRITE",
    "DAEMON",
    "CONFIG",
    "ADVERTISE_MASTER",
    "ADVERTISE_STARTD",
    "ADVERTISE_SCHEDD",
)

CONDOR_PROTO_FEATURE_LIST = ("AUTHENTICATION", "INTEGRITY", "ENCRYPTION", "NEGOTIATION")

CONDOR_PROTO_VALUE_LIST = ("NEVER", "OPTIONAL", "PREFERRED", "REQUIRED")


########################################
class EnvProtoState(SecEnvState):
    def __init__(self, filter=None):
        if filter is not None:
            # validate filter
            for c in list(filter.keys()):
                if not (c in CONDOR_CONTEXT_LIST):
                    raise ValueError(f"Invalid contex '{c}'. Must be one of {CONDOR_CONTEXT_LIST}")
                for f in filter[c]:
                    if not (f in CONDOR_PROTO_FEATURE_LIST):
                        raise ValueError(f"Invalid feature '{f}'. Must be one of {CONDOR_PROTO_FEATURE_LIST}")
        else:
            # do not filter anything out... add all
            filter = {}
            for c in CONDOR_CONTEXT_LIST:
                cfilter = []
                for f in CONDOR_PROTO_FEATURE_LIST:
                    cfilter.append(f)
                filter[c] = cfilter

        SecEnvState.__init__(self, filter)


#########################################
# Same as SecEnvRequest, but check that
# the context and feature are related
# to the Condor protocol handling
class ProtoRequest(SecEnvRequest):
    def set(self, context, feature, value):  # if value is None, remove the request
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError("Invalid security context '%s'." % context)
        if not (feature in CONDOR_PROTO_FEATURE_LIST):
            raise ValueError("Invalid authentication feature '%s'." % feature)
        if not (value in (CONDOR_PROTO_VALUE_LIST + (UNSET_VALUE,))):
            raise ValueError("Invalid value type '%s'." % value)
        SecEnvRequest.set(self, context, feature, value)

    def get(self, context, feature):
        if not (context in CONDOR_CONTEXT_LIST):
            raise ValueError("Invalid security context '%s'." % context)
        if not (feature in CONDOR_PROTO_FEATURE_LIST):
            raise ValueError("Invalid authentication feature '%s'." % feature)
        return SecEnvRequest.get(self, context, feature)


########################################################################
#
# GSI specific classes classes
# Extend ProtoRequest
# These assume all the communication will be GSI or IDTOKENS authenticated
#
########################################################################


class GSIRequest(ProtoRequest):
    def __init__(self, x509_proxy=None, allow_fs=True, allow_idtokens=True, proto_requests=None):
        if allow_idtokens:
            auth_str = "IDTOKENS,GSI"
        else:
            auth_str = "GSI"
        if allow_fs:
            auth_str += ",FS"

        # force either IDTOKENS or GSI authentication
        if proto_requests is not None:
            proto_requests = copy.deepcopy(proto_requests)
        else:
            proto_requests = {}
        for context in CONDOR_CONTEXT_LIST:
            if context not in proto_requests:
                proto_requests[context] = {}
            if "AUTHENTICATION" in proto_requests[context]:
                auth_list = proto_requests[context]["AUTHENTICATION"].split(",")
                if not ("GSI" in auth_list):
                    if not ("IDTOKENS" in auth_list):
                        raise ValueError("Must specify either IDTOKENS or GSI as one of the options")
            else:
                proto_requests[context]["AUTHENTICATION"] = auth_str

        ProtoRequest.__init__(self, proto_requests)
        self.allow_fs = allow_fs
        self.x509_proxy_saved_state = None

        if x509_proxy is None:
            # if 'X509_USER_PROXY' not in os.environ:
            #    raise RuntimeError("x509_proxy not provided and env(X509_USER_PROXY) undefined")
            x509_proxy = os.environ.get("X509_USER_PROXY")

        # Here I should probably check if the proxy is valid
        # To be implemented in a future release

        self.x509_proxy = x509_proxy

    ##############################################
    def save_state(self):
        if self.has_saved_state():
            raise RuntimeError("There is already a saved state! Restore that first.")

        if "X509_USER_PROXY" in os.environ:
            self.x509_proxy_saved_state = os.environ["X509_USER_PROXY"]
        else:
            self.x509_proxy_saved_state = None  # unlike requests, we want to remember there was nothing
        ProtoRequest.save_state(self)

    def restore_state(self):
        if self.saved_state is None:
            return  # nothing to do

        ProtoRequest.restore_state(self)

        if self.x509_proxy_saved_state is not None:
            os.environ["X509_USER_PROXY"] = self.x509_proxy_saved_state
        else:
            del os.environ["X509_USER_PROXY"]

        # unset, just to prevent bugs
        self.x509_proxy_saved_state = None

    ##############################################
    def enforce_requests(self):
        ProtoRequest.enforce_requests(self)
        if self.x509_proxy:
            os.environ["X509_USER_PROXY"] = self.x509_proxy
