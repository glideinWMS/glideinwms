# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements classes that will set up the Condor security as needed."""

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
    """This class manages the state of the Condor environment.

    Attributes:
        filter (list): List of Condor variables to save.
        state (dict): The saved state of the environment variables.
    """

    def __init__(self, filter_list):
        """Initializes the EnvState instance.

        Args:
            filter_list (list): List of Condor variables to save.
        """
        self.filter = filter_list
        self.load()

    def restore(self):
        """Restores the environment variables to their original state (the one found when creating this object)."""
        for condor_key in list(self.state.keys()):
            env_key = "_CONDOR_%s" % condor_key
            old_val = self.state[condor_key]
            if old_val is not None:
                os.environ[env_key] = old_val
            else:
                if os.environ.get(env_key):
                    del os.environ[env_key]

    def load(self):
        """Loads the current environment state into the instance.

        This method is automatically called by the __init__ method. It should not be called directly.
        """
        filter_list = self.filter
        saved_state = {}
        for condor_key in filter_list:
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
    """Converts a security filter dictionary to a list of Condor keys.

    Args:
        sec_filter (dict): Dictionary of security contexts and features.

    Returns:
        list: List of Condor keys.
    """
    filter_list = []
    for context in list(sec_filter.keys()):
        for feature in sec_filter[context]:
            condor_key = f"SEC_{context}_{feature}"
            filter_list.append(condor_key)
    return filter_list


class SecEnvState(EnvState):
    """This class manages the state of the Condor security environment.

    Attributes:
        sec_filter (dict): Dictionary of security contexts and features.
    """

    def __init__(self, sec_filter):
        """Initializes the SecEnvState instance.

        Args:
            sec_filter (dict): Dictionary of security contexts and features.
                               Example: `[context]=[feature list]`
        """
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
    """This class handles requests for setting the Condor security environment state.

    Attributes:
        requests (dict): Dictionary of security requests.
        saved_state (SecEnvState): The saved state of the environment variables.
    """

    def __init__(self, requests=None):
        """Initializes the SecEnvRequest instance.

        Args:
            requests (dict, optional): Dictionary of security requests. Defaults to None.
                                       Example: `[context][feature]=VAL`
        """
        # TODO: requests can be a self initializing dictionary of dictionaries in PY3
        self.requests = {}
        if requests is not None:
            for context in list(requests.keys()):
                for feature in list(requests[context].keys()):
                    self.set(context, feature, requests[context][feature])

        self.saved_state = None

    ##############################################
    # Methods for accessing the requests
    def set(self, context, feature, value):
        """Sets a security request.

        Args:
            context (str): The security context.
            feature (str): The security feature.
            value (str): The value to set. If None, the request is removed.
        """
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
        """Gets a security request.

        Args:
            context (str): The security context.
            feature (str): The security feature.

        Returns:
            str: The value of the request, or None if not found.
        """
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
        """Checks if there is a saved state.

        Returns:
            bool: True if there is a saved state, False otherwise.
        """
        return self.saved_state is not None

    def save_state(self):
        """Saves the current state of the environment variables.

        Raises:
            RuntimeError: If there is already a saved state.
        """
        if self.has_saved_state():
            raise RuntimeError("There is already a saved state! Restore that first.")
        filter = {}
        for c in list(self.requests.keys()):
            filter[c] = list(self.requests[c].keys())

        self.saved_state = SecEnvState(filter)

    def restore_state(self):
        """Restores the environment variables to the saved state."""
        if self.saved_state is None:
            return  # nothing to do

        self.saved_state.restore()
        self.saved_state = None

    ##############################################
    # Methods for changing to the desired state

    # you should call save_state before this one,
    # if you want to ever get back
    def enforce_requests(self):
        """Enforces the security requests environment state by setting the environment variables."""
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
    """This class manages the state of the Condor protocol security environment.

    Attributes:
        filter (dict): Dictionary of contexts and features to filter.
    """

    def __init__(self, filter=None):
        """Initializes the EnvProtoState instance.

        Args:
            filter (dict, optional): Dictionary of contexts and features to filter. Defaults to None.
        """
        if filter is not None:
            # validate filter
            for c in list(filter.keys()):
                if c not in CONDOR_CONTEXT_LIST:
                    raise ValueError(f"Invalid context '{c}'. Must be one of {CONDOR_CONTEXT_LIST}")
                for f in filter[c]:
                    if f not in CONDOR_PROTO_FEATURE_LIST:
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
    """This class handles requests for setting the Condor protocol security environment state.

    Methods:
        set: Sets a security request.
        get: Gets a security request.
    """

    def set(self, context, feature, value):
        """Sets a security request.
        If one of the inputs is invalid or is None, remove the request.

        Args:
            context (str): The security context.
            feature (str): The security feature.
            value (str): The value to set. If None, the request is removed.

        Raises:
            ValueError: If the context, feature, or value are invalid.
        """
        if context not in CONDOR_CONTEXT_LIST:
            raise ValueError("Invalid security context '%s'." % context)
        if feature not in CONDOR_PROTO_FEATURE_LIST:
            raise ValueError("Invalid authentication feature '%s'." % feature)
        if value not in (CONDOR_PROTO_VALUE_LIST + (UNSET_VALUE,)):
            raise ValueError("Invalid value type '%s'." % value)
        SecEnvRequest.set(self, context, feature, value)

    def get(self, context, feature):
        """Gets a security request.

        Args:
            context (str): The security context.
            feature (str): The security feature.

        Returns:
            str: The value of the request, or None if not found.

        Raises:
            ValueError: If the context or feature is invalid.
        """
        if context not in CONDOR_CONTEXT_LIST:
            raise ValueError("Invalid security context '%s'." % context)
        if feature not in CONDOR_PROTO_FEATURE_LIST:
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
    """This class handles requests for setting the Condor GSI security environment state.

    Attributes:
        x509_proxy (str): The X.509 proxy.
        allow_fs (bool): If True, allows FS authentication. Defaults to True.
        allow_idtokens (bool): If True, allows IDTOKENS authentication. Defaults to True.
        x509_proxy_saved_state (str): The saved state of the X.509 proxy environment variable.
    """

    def __init__(self, x509_proxy=None, allow_fs=True, allow_idtokens=True, proto_requests=None):
        """Initializes the GSIRequest instance.

        Args:
            x509_proxy (str, optional): The X.509 proxy. Defaults to None.
            allow_fs (bool, optional): If True, allows FS authentication. Defaults to True.
            allow_idtokens (bool, optional): If True, allows IDTOKENS authentication. Defaults to True.
            proto_requests (dict, optional): Dictionary of protocol requests. Defaults to None.

        Raises:
            ValueError: If neither IDTOKENS nor GSI is specified in the authentication options.
        """
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
                if "GSI" not in auth_list:
                    if "IDTOKENS" not in auth_list:
                        raise ValueError("Must specify either IDTOKENS or GSI as one of the options")
            else:
                proto_requests[context]["AUTHENTICATION"] = auth_str

        ProtoRequest.__init__(self, proto_requests)
        self.allow_fs = allow_fs
        self.x509_proxy_saved_state = None

        if x509_proxy is None:
            # Removed X509_USER_PROXY requirement, could use tokens and X509_USER_PROXY be None
            x509_proxy = os.environ.get("X509_USER_PROXY")

        # Here I should probably check if the proxy is valid
        # To be implemented in a future release

        self.x509_proxy = x509_proxy

    def save_state(self):
        """Saves the current state of the environment variables.

        Raises:
            RuntimeError: If there is already a saved state.
        """
        if self.has_saved_state():
            raise RuntimeError("There is already a saved state! Restore that first.")

        if "X509_USER_PROXY" in os.environ:
            self.x509_proxy_saved_state = os.environ["X509_USER_PROXY"]
        else:
            self.x509_proxy_saved_state = None  # unlike requests, we want to remember there was nothing
        ProtoRequest.save_state(self)

    def restore_state(self):
        """Restores the environment variables to the saved state."""
        if self.saved_state is None:
            return  # nothing to do

        ProtoRequest.restore_state(self)

        if self.x509_proxy_saved_state is not None:
            os.environ["X509_USER_PROXY"] = self.x509_proxy_saved_state
        else:
            del os.environ["X509_USER_PROXY"]

        # unset, just to prevent bugs
        self.x509_proxy_saved_state = None

    def enforce_requests(self):
        """Enforces the security requests by setting the environment variables."""
        ProtoRequest.enforce_requests(self)
        if self.x509_proxy:
            os.environ["X509_USER_PROXY"] = self.x509_proxy
