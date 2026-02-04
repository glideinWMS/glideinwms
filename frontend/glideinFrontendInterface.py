# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module implements the functions needed to advertise and get resources from the Collector
"""

import calendar
import copy
import os
import pickle
import time

from glideinwms.lib import (
    classadSupport,
    condorExe,
    condorManager,
    condorMonitor,
    defaults,
    glideinWMSVersion,
    logSupport,
)
from glideinwms.lib.credentials import AuthenticationMethod, CredentialPurpose, SymmetricKey, x509
from glideinwms.lib.util import hash_nc

############################################################
#
# Configuration
#
############################################################


class FrontendConfig:
    """Configuration class for the Frontend component of GlideinWMS.

    This class holds the configuration attributes for the frontend, including identifiers,
    version details, prefixes for various GlideinWMS components, and settings for condor advertisement.

    Attributes:
        factory_id (str): The name of the attribute that identifies the glidein factory.
        factory_global (str): The global identifier for the glidein factory.
        client_id (str): The name of the client identifier.
        client_global (str): The global identifier for the client.
        factoryclient_id (str): The name of the factory client identifier.
        glideinwms_version (str): The version of GlideinWMS, default is "glideinWMS UNKNOWN".
        glidein_attr_prefix (str): Prefix for glidein attributes.
        glidein_param_prefix (str): Prefix for glidein parameters.
        encrypted_param_prefix (str): Prefix for encrypted glidein parameters.
        glidein_monitor_prefix (str): Prefix for glidein monitors.
        glidein_config_prefix (str): Prefix for glidein configuration.
        glidein_perfmetric_prefix (str): Prefix for glidein performance metrics.
        client_req_prefix (str): Prefix for client requests.
        factory_signtype_id (str): The name of the sign type identifier.
        advertise_use_tcp (bool): Flag indicating whether to use TCP for condor_advertise.
        advertise_use_multi (bool): Flag indicating whether to use the -multiple option for condor_advertise.
        condor_reserved_names (tuple): Reserved names for condor-related attributes.

    Methods:
        __init__(self):
            Initializes the configuration with default values, which can be modified if needed.
            Attempts to retrieve the GlideinWMS version. If unsuccessful, logs an exception.
    """

    def __init__(self):
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.factory_id = "glidefactory"
        self.factory_global = "glidefactoryglobal"
        self.client_id = "glideclient"
        self.client_global = "glideclientglobal"
        self.factoryclient_id = "glidefactoryclient"

        # Default the glideinWMS version string
        self.glideinwms_version = "glideinWMS UNKNOWN"
        try:
            self.glideinwms_version = glideinWMSVersion.GlideinWMSDistro("checksum.frontend").version()
        except Exception:
            logSupport.log.exception("Exception occurred while trying to retrieve the glideinwms version: ")

        # String to prefix for the attributes
        self.glidein_attr_prefix = ""

        # String to prefix for the parameters
        self.glidein_param_prefix = "GlideinParam"
        self.encrypted_param_prefix = "GlideinEncParam"

        # String to prefix for the monitors
        self.glidein_monitor_prefix = "GlideinMonitor"

        # String to prefix for the configured limits
        self.glidein_config_prefix = "GlideinConfig"

        # String to prefix for the performance metrics
        self.glidein_perfmetric_prefix = "GlideinPerfMetric"

        # String to prefix for the requests
        self.client_req_prefix = "Req"

        # The name of the signtype
        self.factory_signtype_id = "SupportedSignTypes"

        # Should we use TCP for condor_advertise?
        self.advertise_use_tcp = False
        # Should we use the new -multiple for condor_advertise?
        self.advertise_use_multi = False

        self.condor_reserved_names = (
            "MyType",
            "TargetType",
            "GlideinMyType",
            "MyAddress",
            "UpdatesHistory",
            "UpdatesTotal",
            "UpdatesLost",
            "UpdatesSequenced",
            "UpdateSequenceNumber",
            "DaemonStartTime",
        )


# global configuration of the module
frontendConfig = FrontendConfig()


#####################################################
# Exception thrown when multiple executions are used
# Helps handle partial failures


class MultiExeError(condorExe.ExeError):
    """Exception used to store multiple failures and raised when an error occurs when executing a command.

    This class is designed to handle multiple `ExeError` exceptions and aggregate their
    string representations into one combined error message. The list of `ExeError` exceptions
    is passed as an argument, and their string representations are joined together with newlines.
    It helps to handle partial failures

    Attributes:
        arr (list): The list of `ExeError` exceptions passed to the constructor.
        str (str): A combined string representation of all the `ExeError` exceptions.

    Inherits:
        ExeError: Inherits from the `ExeError` class to extend its functionality.

    Example:
         >>> err1 = ExeError("Error 1")
         >>> err2 = ExeError("Error 2")
         >>> multi_err = MultiExeError([err1, err2])
         >>> print(multi_err)
         "Error 1\nError 2"
    """

    def __init__(self, arr):
        """Constructs an exception raised for multiple ExeError exceptions.

        Args:
            arr (list): A list of `ExeError` exceptions to be aggregated.
        """
        self.arr = arr

        # First approximation of implementation, can be improved
        str_arr = []
        for e in arr:
            str_arr.append("%s" % e)

        out = "\\n".join(str_arr)

        condorExe.ExeError.__init__(self, out)


############################################################
#
# Global Variables
#
############################################################

# Advertise counter for glideclient
advertiseGCCounter = {}

# Advertise counter for glideclientglobal
advertiseGCGCounter = {}

# Advertise counter for glideresource
advertiseGRCounter = {}

# Advertise counter for glidefrontendmonitor
advertiseGFMCounter = {}


############################################################
#
# User functions
#
############################################################


def findGlobals(pool_name, auth_identity, classad_type, additional_constraint=None):
    """
    Query the given pool to find the globals classad.
    Can be used to query glidefactoryglobal and glidefrontendglobal classads.
    """

    status_constraint = '(GlideinMyType=?="%s")' % classad_type

    # identity checking can be disabled, if really wanted
    if not ((auth_identity is None) or (auth_identity == "*")):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % auth_identity

    if additional_constraint is not None:
        status_constraint = f"{status_constraint} && ({additional_constraint})"

    status = condorMonitor.CondorStatus("any", pool_name=pool_name)
    # important, especially for proxy passing
    status.require_integrity(True)
    status.load(status_constraint)
    data = status.fetchStored()

    return format_condor_dict(data)


def findMasterFrontendClassads(pool_name, frontend_name):
    """
    Query the given pool to find master frontend classads
    """

    status_constraint = '(GlideinMyType=?="{}")||(GlideinMyType=?="{}")'.format("glideclientglobal", "glideclient")
    frontend_constraint = '(FrontendName=?="%s")&&(FrontendHAMode=!="slave")' % frontend_name

    status = condorMonitor.CondorStatus("any", pool_name=pool_name)
    # important, especially for proxy passing
    status.require_integrity(True)
    status.load(f"({status_constraint})&&({frontend_constraint})")
    data = status.fetchStored()

    return format_condor_dict(data)


# can throw condorMonitor.QueryError
def findGlideins(factory_pool, factory_identity, signtype, additional_constraint=None):
    global frontendConfig

    status_constraint = '(GlideinMyType=?="%s")' % frontendConfig.factory_id

    # identity checking can be disabled, if really wanted
    if not ((factory_identity is None) or (factory_identity == "*")):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity

    if signtype is not None:
        status_constraint += f' && stringListMember("{signtype}",{frontendConfig.factory_signtype_id})'

    # Note that Require and Allow x509_Proxy has been replaced by credential type and trust domain

    if additional_constraint is not None:
        status_constraint += " && (%s)" % additional_constraint

    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    status.require_integrity(True)  # important, especially for proxy passing
    status.load(status_constraint)

    data = status.fetchStored()
    return format_condor_dict(data)


def findGlideinClientMonitoring(factory_pool, factory_identity, my_name, additional_constraint=None):
    """Finds and returns a list of Glideins based on factory pool, identity, signature type, and optional constraints.

    This function constructs a Condor status query to find Glideins in a specified factory pool with various
    constraints, such as the factory identity and signature type. The resulting data is then fetched and
    formatted as a dictionary.

    Args:
        factory_pool (str): The name of the factory pool where the Glideins are located.
        factory_identity (str, optional): The factory identity for filtering Glideins. If None or "*", no filtering is applied.
        my_name (str): The Frontend identity to filter Glideins by. If None, no filtering is applied.
        additional_constraint (str, optional): Any additional constraints to apply to the query. Defaults to None.

    Returns:
        dict: A formatted dictionary of the fetched Glidein data.

    Example:
        >>> result = findGlideinClientMonitoring("my_factory_pool", "factory_id_1", "frontend_id_1", "extra_constraint")
        >>> print(result)
        { "Glidein1": {...}, "Glidein2": {...}, ...}
    """
    global frontendConfig

    status_constraint = '(GlideinMyType=?="%s")' % frontendConfig.factoryclient_id

    # identity checking can be disabled, if really wanted
    if not ((factory_identity is None) or (factory_identity == "*")):
        # filter based on AuthenticatedIdentity
        status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity

    if my_name is not None:
        status_constraint += ' && (ReqClientName=?="%s")' % my_name

    if additional_constraint is not None:
        status_constraint += " && (%s)" % additional_constraint
    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    status.load(status_constraint)

    data = status.fetchStored()
    return format_condor_dict(data)


def format_condor_dict(data):
    """
    Formats the data from the condor call.
    """

    reserved_names = frontendConfig.condor_reserved_names
    for k in reserved_names:
        if k in data:
            del data[k]

    out = {}

    for k in list(data.keys()):
        kel = data[k].copy()

        el = {"params": {}, "monitor": {}}

        # first remove reserved names
        for attr in reserved_names:
            if attr in kel:
                del kel[attr]

        # then move the parameters and monitoring
        for prefix, eldata in (
            (frontendConfig.glidein_param_prefix, el["params"]),
            (frontendConfig.glidein_monitor_prefix, el["monitor"]),
        ):
            plen = len(prefix)
            for attr in list(kel.keys()):
                if attr[:plen] == prefix:
                    eldata[attr[plen:]] = kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"] = kel

        out[k] = el

    return out


#############################################

# TODO: PM
# At some point we should change this class to watch for credential file
# updates and cache the contents/info between updates. This should further
# reduce calls to openssl and maintain consistency of credential info
# between cycles. If the file does not change the info in it remains same.
# This also means that the credential objects should be created much before
# and not for every iteration.


# DEPRECATED: use glideinwms.lib.credentials.Credential
class LegacyCredential:
    """A class representing a credential used for GlideinWMS.

    This class holds information about a specific credential, including its ID, filename,
    security class, trust domain, update frequency, and other attributes related to proxy files,
    VM types, and key files. The class is initialized with the proxy ID, proxy filename,
    and an element description containing the merged data necessary for the credential's setup.

    Attributes:
        req_idle (int): The required idle time for the credential, initially set to 0.
        req_max_run (int): The required maximum runtime for the credential, initially set to 0.
        advertise (bool): Flag indicating whether to advertise the credential, initially set to False.
        proxy_id (str): The ID associated with the credential.
        filename (str): The filename associated with the credential, containing information about the credential type.
        type (str): The type of the credential (e.g., "grid_proxy", "key_pair", etc.).
        security_class (str): The security class of the credential.
        trust_domain (str): The trust domain associated with the credential.
        update_frequency (int): The frequency at which the credential is updated.
        generator (str or None): The generator used for the credential, or None if not available.
        vm_id_fname (str or None): The filename containing the VM ID, or None if not available.
        vm_type_fname (str or None): The filename containing the VM type, or None if not available.
        vm_id (str or None): The VM ID associated with the credential, or None if not available.
        vm_type (str or None): The VM type associated with the credential, or None if not available.
        creation_script (str or None): The script used to create the credential, or None if not available.
        key_fname (str or None): The filename containing the key for the credential, or None if not available.
        pilot_fname (str or None): The filename for the pilot file, or None if not available.
        remote_username (str or None): The remote username associated with the credential, or None if not available.
        project_id (str or None): The project ID associated with the credential, or None if not available.
        _id (str or None): The credential ID, which is initialized when `getId()` is called.

    Methods:
        __init__(self, proxy_id, proxy_fname, elementDescript):
            Initializes the credential with its attributes based on the provided data and element description.
    """

    def __init__(self, proxy_id, proxy_fname, elementDescript):
        """Initializes the credential with its attributes based on the provided data and element description.

        Args:
            proxy_id (str): The ID of the credential.
            proxy_fname (str): The filename of the credential.
            elementDescript (object): An object containing the merged data for various credential attributes.
        """
        self.req_idle = 0
        self.req_max_run = 0
        self.advertise = False

        # TODO: refcredential - all these attributes names should not start w/ proxy and the dict names should
        #       be CredentialSomething, not ProxySomething
        proxy_security_classes = elementDescript.merged_data["ProxySecurityClasses"]
        proxy_trust_domains = elementDescript.merged_data["ProxyTrustDomains"]
        credential_generators = elementDescript.merged_data["CredentialGenerators"]
        proxy_types = elementDescript.merged_data["ProxyTypes"]
        proxy_keyfiles = elementDescript.merged_data["ProxyKeyFiles"]
        proxy_pilotfiles = elementDescript.merged_data["ProxyPilotFiles"]
        proxy_vm_ids = elementDescript.merged_data["ProxyVMIds"]
        proxy_vm_types = elementDescript.merged_data["ProxyVMTypes"]
        proxy_creation_scripts = elementDescript.merged_data["CredentialCreationScripts"]
        proxy_update_frequency = elementDescript.merged_data["CredentialMinimumLifetime"]
        proxy_vmid_fname = elementDescript.merged_data["ProxyVMIdFname"]
        proxy_vmtype_fname = elementDescript.merged_data["ProxyVMTypeFname"]
        proxy_remote_username = elementDescript.merged_data["ProxyRemoteUsernames"]
        proxy_project_id = elementDescript.merged_data["ProxyProjectIds"]
        self.proxy_id = proxy_id
        # self.filename (absfname) always contains component of credential
        # used to submit glidein and based on the type contains following:
        # grid_proxy: x509 proxy (also used by pilot to talk to User collector
        # key_pair: public/access key
        # cert_pair: public cert
        # auth_file: auth file used
        self.filename = proxy_fname
        self.type = proxy_types.get(proxy_fname, "Unknown")
        self.security_class = proxy_security_classes.get(proxy_fname, proxy_id)
        self.trust_domain = proxy_trust_domains.get(proxy_fname, "None")
        self.update_frequency = int(proxy_update_frequency.get(proxy_fname, -1))

        # Following items can be None
        self.generator = credential_generators.get(proxy_fname)
        self.vm_id_fname = proxy_vmid_fname.get(proxy_fname)
        self.vm_type_fname = proxy_vmtype_fname.get(proxy_fname)
        self.vm_id = proxy_vm_ids.get(proxy_fname)
        self.vm_type = proxy_vm_types.get(proxy_fname)
        self.creation_script = proxy_creation_scripts.get(proxy_fname)
        self.key_fname = proxy_keyfiles.get(proxy_fname)
        self.pilot_fname = proxy_pilotfiles.get(proxy_fname)
        self.remote_username = proxy_remote_username.get(proxy_fname)
        self.project_id = proxy_project_id.get(proxy_fname)

        # Will be initialized when getId() is called
        self._id = None

    def getId(self, recreate=False):
        """
        Generate the Credential id if we do not have one already
        Since the Id is dependent on the credential content for proxies
        recreate them if asked to do so
        """

        if (not self._id) or recreate:
            # Create the credential id
            self.create()
            self._id = self.file_id(self.getIdFilename())
        return self._id

    def getIdFilename(self):
        """
        Get credential file (name, aka string) used to generate the credential id
        """

        # This checks seem hacky. Ideally checking against the credetnial type
        # to get the filename is right thing to do

        cred_file = None
        if self.filename:
            cred_file = self.filename
        elif self.key_fname:
            cred_file = self.key_fname
        elif self.pilot_fname:
            cred_file = self.pilot_fname
        elif self.generator:
            cred_file = self.generator
        return cred_file

    def create(self):
        """
        Generate the credential
        """

        if self.creation_script:
            logSupport.log.debug("Creating credential using %s" % (self.creation_script))
            try:
                condorExe.iexe_cmd(self.creation_script)
            except Exception:
                logSupport.log.exception("Creating credential using %s failed" % (self.creation_script))
                self.advertise = False

            # Recreating the credential can result in ID change
            self._id = self.file_id(self.getIdFilename())

    def createIfNotExist(self):
        """
        Generate the credential if it does not exists.
        """

        if self.filename and (not os.path.exists(self.filename)):
            logSupport.log.debug("Credential %s does not exist." % (self.filename))
            self.create()

    def getString(self, cred_file=None):
        """
        Based on the type of credentials read appropriate files and return
        the credentials to advertise as a string. The output should be
        encrypted by the caller as required.
        """

        cred_data = ""
        if not cred_file:
            # If not file specified, assume the file used to generate Id
            cred_file = self.getIdFilename()
        try:
            with open(cred_file) as data_fd:
                cred_data = data_fd.read()
        except Exception:
            # This credential should not be advertised
            self.advertise = False
            logSupport.log.exception("Failed to read credential %s: " % cred_file)
        return cred_data

    # PM: Why are the usage details part of Credential Class?
    #     This is overloading the purpose of Credential Class
    def add_usage_details(self, req_idle=0, req_max_run=0):
        self.req_idle = req_idle
        self.req_max_run = req_max_run

    def get_usage_details(self):
        return (self.req_idle, self.req_max_run)

    def file_id(self, filename, ignoredn=False):
        if ("grid_proxy" in self.type) and not ignoredn:
            dn = x509.X509Cert(path=filename).subject
            hash_str = filename + dn
        else:
            hash_str = filename
        logSupport.log.debug(f"Using hash_str={hash_str} ({hash_nc(hash_str, 8)})")
        return hash_nc(hash_str, 8)

    def time_left(self):
        """
        Returns the time left if a grid proxy
        If missing, returns 0
        If not a grid proxy or other unidentified error, return -1
        """
        if not os.path.exists(self.filename):
            return 0

        if ("grid_proxy" in self.type) or ("cert_pair" in self.type):
            time_list = condorExe.iexe_cmd("openssl x509 -in %s -noout -enddate" % self.filename)
            if "notAfter=" in time_list[0]:
                time_str = time_list[0].split("=")[1].strip()
                timeleft = calendar.timegm(time.strptime(time_str, "%b %d %H:%M:%S %Y %Z")) - int(time.time())
                return timeleft
        return -1

    def renew(self):
        """
        Renews credential if time_left()<update_frequency
        Only works if type is grid_proxy or creation_script is provided
        """
        remaining = self.time_left()
        if (remaining != -1) and (self.update_frequency != -1) and (remaining < self.update_frequency):
            self.create()

    def supports_auth_method(self, auth_method):  # TODO: Check for credentials refactoring impact
        """
        Check if this credential has all the necessary info to support
        auth_method for a given factory entry
        """
        type_set = set(self.type.split("+"))
        am_set = set(auth_method.split("+"))
        if "grid_proxy" in am_set and "scitoken" in type_set:
            return True
        return am_set.issubset(type_set)

    def __str__(self):
        output = ""
        output += "id = %s\n" % self.getId()
        output += "proxy_id = %s\n" % self.proxy_id
        output += "req_idle = %s\n" % self.req_idle
        output += "req_max_run = %s\n" % self.req_max_run
        output += "filename = %s\n" % self.filename
        output += "type = %s\n" % self.type
        output += "security_class = %s\n" % self.security_class
        output += "trust_domain = %s\n" % self.trust_domain
        # output += "proxy_data = %s\n" % self.getString(cred_file=self.filename)
        try:
            output += "key_fname = %s\n" % self.key_fname
            # output += "key_data = %s\n" % self.getString(cred_file=self.key_fname)
            # output += "key_data = %s\n" % self.key_data
            output += "pilot_fname = %s\n" % self.pilot_fname
            # output += "pilot_data = %s\n" % self.getString(cred_file=self.pilot_fname)
        except Exception:
            pass
        output += "vm_id = %s\n" % self.vm_id
        output += "vm_type = %s\n" % self.vm_type
        output += "remote_username = %s\n" % self.remote_username
        output += "project_id = %s\n" % self.project_id

        return output


# PM: Credential.getId() should be much faster way of getting the Id
#     Maybe CredentialCache is now obsolete? Can we get rid of it?


# TODO: Evaluate if this class is still needed
class CredentialCache:
    """A class that caches file IDs for credentials to improve performance.

    This class maintains a cache of file IDs for credentials. When a request is made for a file ID
    associated with a credential, it checks the cache first to avoid redundant calculations. If the
    requested file ID is not in the cache, it computes and stores the result.

    Attributes:
        file_id_cache (dict): A dictionary that stores cached file IDs, with keys being tuples of
                              credential type and filename, and values being the corresponding file ID.

    Methods:
        __init__(self):
            Initializes the cache with an empty dictionary.

        file_id(self, credential_el, filename):
            Retrieves the file ID for a given credential element and filename, either from the cache or
            by computing it if not present in the cache.
    """

    def __init__(self):
        """Initializes the `CredentialCache` object with an empty file ID cache."""
        self.file_id_cache = {}

    def file_id(self, credential_el, filename):
        """Retrieves the file ID for the given credential element and filename, using the cache if available.

        This method checks if the file ID for the specified credential element and filename exists
        in the cache. If it does, it returns the cached value. If not, it computes the file ID and
        stores it in the cache for future use.

        Args:
            credential_el (Credential): The credential element for which the file ID is being requested.
            filename (str): The filename for which the file ID is being requested.

        Returns:
            str: The file ID for the given credential element and filename.

        Example:
            >>> cache = CredentialCache()
            >>> credential_el = Credential("proxy_id", "proxy_fname", elementDescript)
            >>> file_id = cache.file_id(credential_el, "filename")
        """
        k = (credential_el.type, filename)
        if k not in self.file_id_cache:
            self.file_id_cache[k] = credential_el.file_id(filename)
        return self.file_id_cache[k]


class FrontendDescript:
    """A class representing the frontend descriptor configuration.

    This class holds information about a specific frontend, including its name, group, web URL,
    signature type, and various associated configuration files. It provides methods to manage
    the frontend's monitoring URL and encryption requirements, as well as to retrieve specific ID attributes.

    Attributes:
        my_name (str): The name of the frontend.
        frontend_name (str): The frontend's identifier name.
        web_url (str): The URL of the frontend's web interface.
        monitoring_web_url (str): The URL for the frontend's monitoring interface, derived from `web_url`.
        main_descript (str): The main description file for the frontend.
        signtype (str): The signature type used for the frontend.
        main_sign (str): The main signature associated with the frontend.
        x509_proxies_plugin (str or None): The x509 proxies plugin for the frontend, or None if not used.
        group_name (str): The name of the group associated with the frontend.
        group_descript (str): The group description file for the frontend.
        group_sign (str): The group signature associated with the frontend.
        ha_mode (str): The high-availability mode for the frontend (default is "master").

    Methods:
        __init__(self, my_name, frontend_name, group_name, web_url, main_descript, group_descript, signtype, main_sign, group_sign, x509_proxies_plugin=None, ha_mode="master"):
            Initializes the frontend descriptor with the provided values.

        add_monitoring_url(self, monitoring_web_url):
            Sets the monitoring web URL for the frontend.

        need_encryption(self):
            Checks if encryption is required by verifying the presence of an x509 proxies plugin.

        get_id_attrs(self):
            Returns a list of strings representing the frontend's key attributes, including `my_name`, `frontend_name`, `ha_mode`, and `group_name`.

        get_web_attrs(self):
            Returns a tuple of strings representing the web-related attributes of the frontend.
    """

    def __init__(
        self,
        my_name,
        frontend_name,
        group_name,
        web_url,
        main_descript,
        group_descript,
        signtype,
        main_sign,
        group_sign,
        credentials_plugin=None,
        ha_mode="master",
    ):
        self.my_name = my_name
        self.frontend_name = frontend_name
        self.web_url = web_url
        self.monitoring_web_url = web_url.replace("stage", "monitor")
        self.main_descript = main_descript
        self.signtype = signtype
        self.main_sign = main_sign
        self.credentials_plugin = credentials_plugin
        self.group_name = group_name
        self.group_descript = group_descript
        self.group_sign = group_sign
        self.ha_mode = ha_mode

    # Accessor method for monitoring web url
    def add_monitoring_url(self, monitoring_web_url):
        """Sets the monitoring web URL for the frontend.

        Args:
            monitoring_web_url (str): The new monitoring web URL for the frontend.
        """
        self.monitoring_web_url = monitoring_web_url

    def need_encryption(self):
        """Checks if encryption is required for the frontend.

        Returns:
            bool: True if encryption is required (i.e., if `x509_proxies_plugin` is not None), False otherwise.
        """
        return self.credentials_plugin is not None

    # return a list of strings
    def get_id_attrs(self):
        """Returns a list of strings representing key attributes of the frontend.

        Returns:
            tuple: A tuple of strings representing key frontend attributes, including `my_name`, `frontend_name`,
                   `ha_mode`, and `group_name`.
        """
        return (
            'ClientName = "%s"' % self.my_name,
            'FrontendName = "%s"' % self.frontend_name,
            'FrontendHAMode = "%s"' % self.ha_mode,
            'GroupName = "%s"' % self.group_name,
        )

    def get_web_attrs(self):
        """Returns a tuple of strings representing the web-related attributes of the frontend.

        This method constructs and returns key web-related attributes for the frontend, including the main
        web URL, signature type, description file, group URL, and associated group description files.

        Returns:
            tuple: A tuple of strings representing the web-related attributes, including:
                - WebURL: The URL for the frontend's web interface.
                - WebSignType: The signature type used for the web interface.
                - WebDescriptFile: The main description file for the frontend.
                - WebDescriptSign: The main signature associated with the frontend.
                - WebGroupURL: The URL for the group-specific web interface.
                - WebGroupDescriptFile: The group-specific description file.
                - WebGroupDescriptSign: The group-specific signature.

        Example:
            >>> frontend = FrontendDescript("my_name", "frontend_name", "group_name", "http://web.url", "main_descript", "group_descript", "signtype", "main_sign", "group_sign")
            >>> frontend.get_web_attrs()
            (
                'WebURL = "http://web.url"',
                'WebSignType = "signtype"',
                'WebDescriptFile = "main_descript"',
                'WebDescriptSign = "main_sign"',
                'WebGroupURL = "http://web.url/group_group_name"',
                'WebGroupDescriptFile = "group_descript"',
                'WebGroupDescriptSign = "group_sign"'
            )
        """
        return (
            'WebURL = "%s"' % self.web_url,
            'WebSignType = "%s"' % self.signtype,
            'WebDescriptFile = "%s"' % self.main_descript,
            'WebDescriptSign = "%s"' % self.main_sign,
            'WebGroupURL = "%s"' % os.path.join(self.web_url, "group_%s" % self.group_name),
            'WebGroupDescriptFile = "%s"' % self.group_descript,
            'WebGroupDescriptSign = "%s"' % self.group_sign,
        )


class FactoryKeys4Advertise:
    def __init__(self, classad_identity, factory_pub_key_id, factory_pub_key, glidein_symKey=None):
        """

        Args:
            classad_identity:
            factory_pub_key_id:
            factory_pub_key:
            glidein_symKey: if a symkey is not provided, or is not initialized, one will be generated
        """
        self.classad_identity = classad_identity
        self.factory_pub_key_id = factory_pub_key_id
        self.factory_pub_key = factory_pub_key

        if glidein_symKey is None:
            glidein_symKey = SymmetricKey()
        if not glidein_symKey.valid:
            glidein_symKey = copy.deepcopy(glidein_symKey)
            glidein_symKey.new()
        self.glidein_symKey = glidein_symKey

    # returns a list of strings
    def get_key_attrs(self):
        """Get the key attributes as classad lines

        Returns:
            list: list of str containing the classads about the key
        """
        glidein_symKey_str = self.glidein_symKey.get_code()
        return (
            'ReqPubKeyID = "%s"' % self.factory_pub_key_id,
            'ReqEncKeyCode = "%s"'
            % self.factory_pub_key.encrypt_hex(glidein_symKey_str).decode(defaults.BINARY_ENCODING_CRYPTO),
            # this attribute will be checked against the AuthenticatedIdentity
            # this will prevent replay attacks, as only who knows the symkey can change this field
            # no other changes needed, as HTCondor provides integrity of the whole classAd
            'ReqEncIdentity = "%s"' % self.encrypt_hex(self.classad_identity).decode(defaults.BINARY_ENCODING_CRYPTO),
        )

    def encrypt_hex(self, data):
        """Encrypt the input data

        Args:
            data (AnyStr): data to encrypt

        Returns:
            bytes: encrypted data
        """
        return self.glidein_symKey.encrypt_hex(data)


class Key4AdvertiseBuilder:
    """Class for creating FactoryKeys4Advertise objects
    will reuse the symkey as much as possible
    """

    def __init__(self):
        self.keys_cache = {}  # will contain a tuple of (key_obj, creation_time, last_access_time)

    def get_key_obj(self, classad_identity, factory_pub_key_id, factory_pub_key, glidein_symKey=None):
        """Get a key object

        Args:
            classad_identity:
            factory_pub_key_id:
            factory_pub_key:
            glidein_symKey: will use one, if provided, but better to leave it blank and let the Builder create one
                whoever can decrypt the pub key can anyhow get the symkey

        Returns:

        """
        cache_id = factory_pub_key.string

        if glidein_symKey is not None:
            # when a key is explicitly given, cannot reuse a cached one
            key_obj = FactoryKeys4Advertise(classad_identity, factory_pub_key_id, factory_pub_key, glidein_symKey)
            # but I can use it for others
            if cache_id not in self.keys_cache:
                now = time.time()
                self.keys_cache[cache_id] = [key_obj, now, now]
            return key_obj
        else:
            if cache_id in self.keys_cache:
                self.keys_cache[cache_id][2] = time.time()
                return self.keys_cache[cache_id][0]
            else:
                key_obj = FactoryKeys4Advertise(
                    classad_identity, factory_pub_key_id, factory_pub_key, glidein_symKey=None
                )
                now = time.time()
                self.keys_cache[cache_id] = [key_obj, now, now]
                return key_obj

    def clear(self, created_after=None, accessed_after=None):
        """Clear the cache

        Args:
            created_after: if not None, only clear entries older than this
            accessed_after: if not None, only clear entries not accessed recently
        """
        if (created_after is None) and (accessed_after is None):
            # just delete everything
            self.keys_cache = {}
            return

        for cache_id in list(self.keys_cache.keys()):
            # if at least one criteria is not satisfied, delete the entry
            delete_entry = False

            if created_after is not None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][1] < created_after)

            if accessed_after is not None:
                delete_entry = delete_entry or (self.keys_cache[cache_id][2] < accessed_after)

            if delete_entry:
                del self.keys_cache[cache_id]


#######################################
# INTERNAL, do not use directly


class AdvertiseParams:
    """A class representing the parameters for advertising Glideins.

    This class holds various configuration parameters related to the advertising of Glideins,
    including the request name, glidein name, minimum and maximum glideins, idle lifetime,
    and additional parameters for monitoring and security.

    Attributes:
        request_name (str): The name of the request associated with the Glideins.
        glidein_name (str): The name of the Glidein to be advertised.
        min_nr_glideins (int): The minimum number of Glideins to be requested.
        max_run_glideins (int): The maximum number of Glideins that can be run.
        idle_lifetime (int): The idle lifetime for the Glidein, default is 0.
        remove_excess_str (str): The strategy for handling excess Glideins. Valid values are "NO", "WAIT", "IDLE", "ALL", "UNREG".
        remove_excess_margin (int): The margin for removing excess Glideins, default is 0.
        glidein_params (dict): A dictionary of parameters associated with the Glidein.
        glidein_monitors (dict): A dictionary of monitoring parameters for the Glidein.
        glidein_monitors_per_cred (dict): A dictionary of monitoring parameters for each credential.
        glidein_params_to_encrypt (dict or None): Parameters that need encryption, needs key_obj.
        security_name (str or None): The security name associated with the Glidein, needs key_obj.

    Methods:
        __init__(self, request_name, glidein_name, min_nr_glideins, max_run_glideins, idle_lifetime=0, glidein_params={}, glidein_monitors={}, glidein_monitors_per_cred={}, glidein_params_to_encrypt=None, security_name=None, remove_excess_str=None, remove_excess_margin=0):
            Initializes the advertising parameters for the Glidein request.

        __str__(self):
            Returns a string representation of the `AdvertizeParams` object, displaying all the attribute values.
    """

    def __init__(
        self,
        request_name,
        glidein_name,
        min_nr_glideins,
        max_run_glideins,
        idle_lifetime=0,
        glidein_params={},
        glidein_monitors={},
        glidein_monitors_per_cred={},
        glidein_params_to_encrypt=None,  # params_to_encrypt needs key_obj
        security_name=None,  # needs key_obj
        remove_excess_str=None,
        remove_excess_margin=0,
    ):
        """Initializes the `AdvertizeParams` object with the given parameters.

        Args:
            request_name (str): The name of the request associated with the Glideins.
            glidein_name (str): The name of the Glidein to be advertised.
            min_nr_glideins (int): The minimum number of Glideins to be requested.
            max_run_glideins (int): The maximum number of Glideins that can be run.
            idle_lifetime (int, optional): The idle lifetime for the Glidein. Defaults to 0.
            glidein_params (dict, optional): Parameters associated with the Glidein. Defaults to an empty dictionary.
            glidein_monitors (dict, optional): Monitoring parameters for the Glidein. Defaults to an empty dictionary.
            glidein_monitors_per_cred (dict, optional): Monitoring parameters for each credential. Defaults to an empty dictionary.
            glidein_params_to_encrypt (dict or None, optional): Parameters that need encryption. Defaults to None.
            security_name (str or None, optional): The security name for the Glidein. Defaults to None.
            remove_excess_str (str, optional): Strategy for handling excess Glideins. Valid values are "NO", "WAIT", "IDLE", "ALL", "UNREG". Defaults to "NO".
            remove_excess_margin (int, optional): The margin for removing excess Glideins. Defaults to 0.

        Raises:
            RuntimeError: If the `remove_excess_str` parameter is provided with an invalid value.
        """
        self.request_name = request_name
        self.glidein_name = glidein_name
        self.min_nr_glideins = min_nr_glideins
        self.max_run_glideins = max_run_glideins
        self.idle_lifetime = idle_lifetime
        if remove_excess_str is None:
            remove_excess_str = "NO"
        elif remove_excess_str not in ("NO", "WAIT", "IDLE", "ALL", "UNREG"):
            raise RuntimeError(
                'Invalid remove_excess_str(%s), valid values are "NO","WAIT","IDLE","ALL","UNREG"' % remove_excess_str
            )
        self.remove_excess_str = remove_excess_str
        self.remove_excess_margin = remove_excess_margin
        self.glidein_params = glidein_params
        self.glidein_monitors = glidein_monitors
        self.glidein_monitors_per_cred = glidein_monitors_per_cred
        self.glidein_params_to_encrypt = glidein_params_to_encrypt
        self.security_name = security_name

    def __str__(self):
        """Returns a string representation of the `AdvertizeParams` object, displaying all the attribute values.

        Returns:
            str: A string representation of the `AdvertizeParams` object with its key attributes.

        Example:
            >>> params = AdvertizeParams("request1", "glidein1", 5, 10)
            >>> print(params)
            AdvertizeParams
            request_name = request1
            glidein_name = glidein1
            min_nr_glideins = 5
            max_run_glideins = 10
            idle_lifetime = 0
            remove_excess_str = NO
            remove_excess_margin = 0
            glidein_params = {}
            glidein_monitors = {}
            glidein_monitors_per_cred = {}
            glidein_params_to_encrypt = None
            security_name = None
        """
        output = "\nAdvertiseParams\n"
        output += "request_name = %s\n" % self.request_name
        output += "glidein_name = %s\n" % self.glidein_name
        output += "min_nr_glideins = %s\n" % self.min_nr_glideins
        output += "max_run_glideins = %s\n" % self.max_run_glideins
        output += "idle_lifetime = %s\n" % self.idle_lifetime
        output += "remove_excess_str = %s\n" % self.remove_excess_str
        output += "remove_excess_margin = %s\n" % self.remove_excess_margin
        output += "glidein_params = %s\n" % self.glidein_params
        output += "glidein_monitors = %s\n" % self.glidein_monitors
        output += "glidein_monitors_per_cred = %s\n" % self.glidein_monitors_per_cred
        output += "glidein_params_to_encrypt = %s\n" % self.glidein_params_to_encrypt
        output += "security_name = %s\n" % self.security_name

        return output


# Given a file, advertise
# Can throw a CondorExe/ExeError exception
def advertiseWorkFromFile(factory_pool, fname, remove_file=True, is_multi=False):
    try:
        exe_condor_advertise(fname, "UPDATE_MASTER_AD", factory_pool, is_multi=is_multi)
    finally:
        if remove_file:
            os.remove(fname)


# END INTERNAL
########################################


class MultiAdvertiseWork:
    """A class to manage and organize advertising requests for multiple Glidein factories.

    This class facilitates the addition of advertising requests for Glideins, including parameters,
    constraints, and associated keys. It organizes requests into a factory-specific queue and allows
    handling multiple Glidein advertisements simultaneously.

    Attributes:
        descript_obj (FrontendDescript): A frontend descriptor object containing configuration for the frontend.
        factory_queue (dict): A dictionary mapping each factory pool to a list of advertising parameters and keys.
        global_pool (list): A list for storing global pool-related data (currently not used).
        global_key (dict): A dictionary for storing global keys (currently not used).
        global_params (dict): A dictionary for storing global parameters (currently not used).
        factory_constraint (dict): A dictionary mapping each request's name to a tuple of trust domain and authentication method.
        unique_id (int): A unique identifier for the current instance, starting from 1.
        adname (str or None): The advertisement name, initialized to None.
        x509_proxies_data (list): A list for storing x509 proxies data (currently not used).
        ha_mode (str): The high-availability mode for the advertisement, default is "master".
        glidein_config_limits (dict): A dictionary for storing Glidein configuration limits (currently not used).

    Methods:
        __init__(self, descript_obj):
            Initializes the `MultiAdvertizeWork` object with the provided `descript_obj`.

        add(self, factory_pool, request_name, glidein_name, min_nr_glideins, max_run_glideins, idle_lifetime=0, glidein_params={}, glidein_monitors={}, glidein_monitors_per_cred={}, key_obj=None, glidein_params_to_encrypt=None, security_name=None, remove_excess_str=None, remove_excess_margin=0, trust_domain="Any", auth_method="Any", ha_mode="master"):
            Adds a new advertising request to the list, associated with the specified factory pool.
    """

    def __init__(self, descript_obj):  # must be of type FrontendDescript
        """Initializes the `MultiAdvertizeWork` object with the provided frontend descriptor.

        Args:
            descript_obj (FrontendDescript): The frontend descriptor object containing configuration for the frontend.
        """
        self.descript_obj = descript_obj
        self.factory_queue = {}  # will have a queue x factory, each element is list of tuples (params_obj, key_obj)
        self.global_pool = []
        self.global_key = {}
        self.global_params = {}
        self.factory_constraint = {}

        # set a few defaults
        self.unique_id = 1
        self.adname = None
        self.request_credentials = []
        self.ha_mode = "master"
        self.glidein_config_limits = {}

    # add a request to the list
    def add(
        self,
        factory_pool,
        request_name,
        glidein_name,
        min_nr_glideins,
        max_run_glideins,
        idle_lifetime=0,
        glidein_params={},
        glidein_monitors={},
        glidein_monitors_per_cred={},
        key_obj=None,  # must be of type FactoryKeys4Advertise
        glidein_params_to_encrypt=None,  # params_to_encrypt needs key_obj
        security_name=None,  # needs key_obj
        remove_excess_str=None,
        remove_excess_margin=0,
        trust_domain="Any",
        auth_method="Any",
        ha_mode="master",
    ):
        """Adds a new advertising request for a specific factory pool.

        This method creates an `AdvertizeParams` object for the given request and appends it to the queue
        of the specified factory pool. The method also stores the associated trust domain and authentication
        method in the `factory_constraint` dictionary.

        Args:
            factory_pool (str): The factory pool to which the advertising request belongs.
            request_name (str): The name of the request to be advertised.
            glidein_name (str): The name of the Glidein to be advertised.
            min_nr_glideins (int): The minimum number of Glideins to be requested.
            max_run_glideins (int): The maximum number of Glideins that can be run.
            idle_lifetime (int, optional): The idle lifetime for the Glidein. Defaults to 0.
            glidein_params (dict, optional): The parameters associated with the Glidein. Defaults to an empty dictionary.
            glidein_monitors (dict, optional): The monitoring parameters for the Glidein. Defaults to an empty dictionary.
            glidein_monitors_per_cred (dict, optional): Monitoring parameters for each credential. Defaults to an empty dictionary.
            key_obj (FactoryKeys4Advertise, optional): The key object used for advertising the Glidein. Defaults to None.
            glidein_params_to_encrypt (dict, optional): The parameters to encrypt. Defaults to None.
            security_name (str, optional): The security name associated with the request. Defaults to None.
            remove_excess_str (str, optional): The strategy for handling excess Glideins. Defaults to None.
            remove_excess_margin (int, optional): The margin for removing excess Glideins. Defaults to 0.
            trust_domain (str, optional): The trust domain for the request. Defaults to "Any".
            auth_method (str, optional): The authentication method. Defaults to "Any".
            ha_mode (str, optional): The high-availability mode. Defaults to "master".
        """
        params_obj = AdvertiseParams(
            request_name,
            glidein_name,
            min_nr_glideins,
            max_run_glideins,
            idle_lifetime,
            glidein_params,
            glidein_monitors,
            glidein_monitors_per_cred,
            glidein_params_to_encrypt,
            security_name,
            remove_excess_str,
            remove_excess_margin,
        )

        if factory_pool not in self.factory_queue:
            self.factory_queue[factory_pool] = []
        self.factory_queue[factory_pool].append((params_obj, key_obj))
        self.factory_constraint[params_obj.request_name] = (trust_domain, auth_method)
        self.ha_mode = ha_mode

    def add_global(self, factory_pool, request_name, security_name, key_obj):
        """Adds global configuration for a specific factory pool.

        This method appends the given factory pool to the global pool list and associates the factory pool
        with its corresponding key object and configuration parameters (request name and security name).

        Args:
            factory_pool (str): The name of the factory pool to be added to the global pool.
            request_name (str): The name of the request associated with the factory pool.
            security_name (str): The security name associated with the request.
            key_obj (object): The key object associated with the factory pool, used for secure operations.

        Example:
            >>> obj.add_global("factory_pool_1", "request_name_1", "security_name_1", key_obj)
            >>> print(obj.global_pool)
            ["factory_pool_1"]
            >>> print(obj.global_key["factory_pool_1"])
            key_obj
            >>> print(obj.global_params["factory_pool_1"])
            ("request_name_1", "security_name_1")
        """
        self.global_pool.append(factory_pool)
        self.global_key[factory_pool] = key_obj
        self.global_params[factory_pool] = (request_name, security_name)

    # return the queue depth
    def get_queue_len(self):
        count = 0
        # for factory_pool in self.factory_queue:
        for factory_pool in list(self.factory_queue.keys()):
            count += len(self.factory_queue[factory_pool])
        return count

    def renew_and_load_credentials(self):
        """Get the list of proxies, invoke the `renew()` scripts if any, and read the credentials in memory.

        Modifies the self.request_credentials variable.
        """
        self.request_credentials = []
        if self.descript_obj.credentials_plugin is not None:
            self.request_credentials = self.descript_obj.credentials_plugin.get_request_credentials()
            nr_credentials = len(self.request_credentials)
        else:
            nr_credentials = 0

        for cred_el in self.request_credentials:
            cred_el.advertise = True
            cred_el.credential.renew()
            cred_el.credential.save_to_file(overwrite=False, continue_if_no_path=True)

        return nr_credentials

    def initialize_advertise_batch(self, adname_prefix="gfi_ad_batch"):
        """Initialize the variables that are used for batch avertisement

        Args:
            adname_prefix (str, optional): The adname prefix to use. Defaults to "gfi_ad_batch".

        Returns:
            str: the adname to pass to do*advertise methods
                (will have to set reset_unique_id=False there, too)
        """
        self.unique_id = 1
        return classadSupport.generate_classad_filename(prefix=adname_prefix)

    def do_advertise_batch(self, filename_dict, remove_files=True):
        """
        Advertise the classad files in the dictionary provided
         The keys are the factory names, while the elements are lists of files
        Safe to run in parallel, guaranteed to not modify the self object state.
        """
        for factory_pool in filename_dict:
            self.do_advertise_batch_one(factory_pool, filename_dict[factory_pool], remove_files)

    def do_advertise_batch_one(self, factory_pool, filename_arr, remove_files=True):
        """
        Advertise to a Factory the ClassAd files provided
        Safe to run in parallel, guaranteed to not modify the self object state.
        """
        # Advertise all the files
        for filename in filename_arr:
            try:
                advertiseWorkFromFile(
                    factory_pool, filename, remove_file=remove_files, is_multi=frontendConfig.advertise_use_multi
                )
            except condorExe.ExeError:
                logSupport.log.exception("Advertising failed for factory pool %s: " % factory_pool)

    def get_advertise_factory_list(self):
        return tuple(set(self.global_pool).union(set(self.factory_queue.keys())))

    def do_global_advertise(self, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Advertise globals with credentials
        Returns a dictionary of files that still need to be advertised.
          The key is the factory pool, while the element is a list of file names
        Expects that the credentials have been already loaded.
        """
        unpublished_files = {}
        if reset_unique_id:
            self.unique_id = 1
        for factory_pool in self.global_pool:
            self.unique_id += 1  # make sure ads for different factories don't end in the same file
            unpublished_files[factory_pool] = self.do_global_advertise_one(
                factory_pool, adname, create_files_only, False
            )
        return unpublished_files

    def do_global_advertise_one(self, factory_pool, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Advertise globals with credentials to one factory
        Returns the list of files that still need to be advertised.
        Expects that the credentials have been already loaded.
        """
        if factory_pool not in self.global_pool:
            # nothing to be done, prevent failure
            return []

        if adname is None:
            tmpname = classadSupport.generate_classad_filename(prefix="gfi_ad_gcg")
        else:
            tmpname = adname

        if reset_unique_id:
            self.unique_id = 1
        self.adname = tmpname
        filename_arr = self.createGlobalAdvertiseWorkFile(factory_pool)
        if create_files_only:
            return filename_arr

        # Else, advertise all the files (if multi, should only be one)
        for filename in filename_arr:
            try:
                advertiseWorkFromFile(
                    factory_pool, filename, remove_file=True, is_multi=frontendConfig.advertise_use_multi
                )
            except condorExe.ExeError:
                logSupport.log.exception("Advertising globals failed for factory pool %s: " % factory_pool)
        return []  # no files left to be advertised

    def createGlobalAdvertiseWorkFile(self, factory_pool):
        """
        Create the advertise file for globals with credentials
        Expects the object variables
         adname and x509_proxies_data
        to be set.
        """
        global advertiseGCGCounter

        tmpname = self.adname
        glidein_params_to_encrypt = {}
        with open(tmpname, "a") as fd:
            nr_credentials = len(self.request_credentials)
            if nr_credentials > 0:
                glidein_params_to_encrypt["NumberOfCredentials"] = (
                    f"{nr_credentials}"  # TODO: Check if it needs refactoring
                )

            request_name = "Global"
            if factory_pool in self.global_params:
                request_name, security_name = self.global_params[factory_pool]
                glidein_params_to_encrypt["SecurityName"] = security_name
            classad_name = f"{request_name}@{self.descript_obj.my_name}"
            fd.write(f'MyType = "{frontendConfig.client_global}"\n')
            fd.write(f'GlideinMyType = "{frontendConfig.client_global}"\n')
            fd.write(f'GlideinWMSVersion = "{frontendConfig.glideinwms_version}"\n')
            fd.write(f'Name = "{classad_name}"\n')
            fd.write(f'FrontendName = "{self.descript_obj.frontend_name}"\n')
            fd.write(f'FrontendHAMode = "{self.ha_mode}"\n')
            fd.write(f'GroupName = "{self.descript_obj.group_name}"\n')
            fd.write(f'ClientName = "{self.descript_obj.my_name}"\n')
            for cred_el in self.request_credentials:
                if not cred_el.advertise:
                    continue  # we already determined it cannot be used
                glidein_params_to_encrypt[cred_el.credential.id] = cred_el.credential.string
                if hasattr(cred_el, "security_class"):
                    # Convert the sec class to a string so the Factory can interpret the value correctly
                    glidein_params_to_encrypt["SecurityClass" + cred_el.credential.id] = str(
                        cred_el.credential.security_class
                    )

            key_obj = None
            if factory_pool in self.global_key:
                key_obj = self.global_key[factory_pool]
            if key_obj is not None:
                fd.write("\n".join(key_obj.get_key_attrs()) + "\n")
                for attr in list(glidein_params_to_encrypt.keys()):
                    el = key_obj.encrypt_hex(glidein_params_to_encrypt[attr]).decode(defaults.BINARY_ENCODING_CRYPTO)
                    escaped_el = el.replace('"', '\\"').replace("\n", "\\n")
                    fd.write(f'{frontendConfig.encrypted_param_prefix}{attr} = "{escaped_el}"\n')

            # Update Sequence number information
            if classad_name in advertiseGCGCounter:
                advertiseGCGCounter[classad_name] += 1
            else:
                advertiseGCGCounter[classad_name] = 0
            fd.write(f"UpdateSequenceNumber = {advertiseGCGCounter[classad_name]}\n")

            # add a final empty line... useful when appending
            fd.write("\n")

        return [tmpname]

    def do_advertise(self, file_id_cache=None, adname=None, create_files_only=False, reset_unique_id=True):
        """
        Do the advertising of the requests
        Returns a dictionary of files that still need to be advertised.
          The key is the factory pool, while the element is a list of file names
        Expects that the credentials have already been loaded.
        """
        if file_id_cache is None:
            file_id_cache = CredentialCache()

        unpublished_files = {}
        if reset_unique_id:
            self.unique_id = 1
        for factory_pool in list(self.factory_queue.keys()):
            self.unique_id += 1  # make sure ads for different factories don't end in the same file
            unpublished_files[factory_pool] = self.do_advertise_one(
                factory_pool, file_id_cache, adname, create_files_only, False
            )
        return unpublished_files

    def do_advertise_one(
        self, factory_pool, file_id_cache=None, adname=None, create_files_only=False, reset_unique_id=True
    ):
        """
        Do the advertising of requests for one factory
        Returns the list of files that still need to be advertised.
        Expects that the credentials have already been loaded.
        """
        # the different indentation is due to code refactoring
        # this way the diff was minimized
        if factory_pool not in list(self.factory_queue.keys()):
            # nothing to be done, prevent failure
            return []

        if file_id_cache is None:
            file_id_cache = CredentialCache()

        if reset_unique_id:
            self.unique_id = 1
        if adname is None:
            self.adname = classadSupport.generate_classad_filename(prefix="gfi_ad_gc")
        else:
            self.adname = adname

        # this should be done in parallel, but keep it serial for now
        filename_arr = []
        if frontendConfig.advertise_use_multi:
            filename_arr.append(self.adname)
        for el in self.factory_queue[factory_pool]:
            params_obj, key_obj = el
            try:
                filename_arr_el = self.createAdvertiseWorkFile(
                    factory_pool, params_obj, key_obj, file_id_cache=file_id_cache
                )
                for f in filename_arr_el:
                    if f not in filename_arr:
                        filename_arr.append(f)
            except NoCredentialException:
                filename_arr = []  # don't try to advertise
                logSupport.log.warning(
                    "No security credentials match for factory pool %s, not advertising request;"
                    " if this is not intentional, check for typos frontend's credential "
                    "trust_domain and type, vs factory's pool trust_domain and auth_method" % factory_pool
                )
            except condorExe.ExeError:
                filename_arr = []  # don't try to advertise
                logSupport.log.exception(
                    "Error creating request files for factory pool %s, unable to advertise: " % factory_pool
                )
                logSupport.log.error(
                    "Error creating request files for factory pool %s, unable to advertise" % factory_pool
                )

        del self.factory_queue[factory_pool]  # clean queue for this factory

        if create_files_only:
            return filename_arr

        # Else, advertise all the files (if multi, should only be one)
        for filename in filename_arr:
            try:
                advertiseWorkFromFile(
                    factory_pool, filename, remove_file=True, is_multi=frontendConfig.advertise_use_multi
                )
            except condorExe.ExeError:
                logSupport.log.exception("Advertising request failed for factory pool %s: " % factory_pool)

        return []  # No files left to be advertised

    def vm_attribute_from_file(self, filename, prefix):
        """
        Expected syntax: VM_ID=<ami id> or VM_TYPE=<instance type>

        Note: This method does not check if the string that follows VM_ID
              is meaningful AMI or the string that follows VM_TYPE is one
              of AWS instance types.
        """

        values = []
        try:
            vmfile = open(filename)
            for line in vmfile.readlines():
                sep_idx = line.find("=")
                if sep_idx > 0:
                    key = (line[:sep_idx]).strip()
                    if key.upper() == prefix.upper():
                        value = (line[sep_idx + 1 :]).strip()
                        if value != "":
                            values.append(value)
        except Exception:
            logSupport.log.exception("Failed to read the file %s" % (filename))
            raise NoCredentialException

        if len(values) > 1:
            logSupport.log.error(f"Found multiple lines that contain {prefix} in {filename}")
            raise NoCredentialException
        elif len(values) == 0:
            logSupport.log.error(f"File {filename} does not contain {prefix}")
            raise NoCredentialException

        logSupport.log.debug(f"Found {prefix} = {values[0]} from file {filename}")
        return values[0]

    def createAdvertiseWorkFile(self, factory_pool, params_obj, key_obj=None, file_id_cache=None):
        """
        Create the advertise file
        Expects the object variables
          adname, unique_id and x509_proxies_data
        to be set.
        """

        cred_filename_arr = []

        logSupport.log.debug("In create Advertise work")

        # Make sure we have credentials to work with
        if len(self.request_credentials) == 0:
            logSupport.log.warning("No credentials found. Not advertising request.")
            raise NoCredentialException

        # Determine required credentials for the entry
        factory_trust, factory_auth = self.factory_constraint[params_obj.request_name]
        factory_auth = AuthenticationMethod(factory_auth)
        auth_set = factory_auth.match(self.descript_obj.credentials_plugin.security_bundle)
        if not auth_set:
            logSupport.log.debug(
                f'The available credentials do not match the requirements of factory pool {factory_pool} entry "{params_obj.request_name}". Not advertising request. '
                f"Available credentials: {str(self.descript_obj.credentials_plugin.security_bundle)} "
                f"Required credentials: {str(factory_auth)}"
            )
            raise NoCredentialException
        params_obj.glidein_params_to_encrypt["AuthSet"] = pickle.dumps(auth_set)

        entry_name = params_obj.glidein_name.split("@")[0]

        # Pack payload credentials to send with the request
        payload_creds = [
            cred
            for cred in self.descript_obj.credentials_plugin.get_credentials(
                trust_domain=factory_trust,
                credential_purpose=CredentialPurpose.PAYLOAD,
                snapshot=entry_name,
            )
        ]
        payload_creds.extend(
            [
                cred
                for cred in self.descript_obj.credentials_plugin.get_credentials(
                    trust_domain=factory_trust,
                    credential_purpose=CredentialPurpose.CALLBACK,
                    snapshot=entry_name,
                )
            ]
        )
        params_obj.glidein_params_to_encrypt["PayloadCredentials"] = pickle.dumps(payload_creds)

        # Pack parameters to send to the request
        security_params = [
            param for param in self.descript_obj.credentials_plugin.get_parameters(snapshot=entry_name).values()
        ]
        params_obj.glidein_params_to_encrypt["SecurityParameters"] = pickle.dumps(security_params)

        # Assign work to the credentials per the plugin policy
        self.descript_obj.credentials_plugin.assign_work(self.request_credentials, params_obj, auth_set)

        for request_cred in self.request_credentials:
            cred = self.descript_obj.credentials_plugin.get_credential(request_cred.credential.id, snapshot=entry_name)
            if not request_cred.advertise:
                logSupport.log.debug(f"Skipping credential with 'advertise' set to False. ({cred.id})")
                continue  # We already determined it cannot be used
            if (cred.trust_domain != factory_trust) and (factory_trust != "Any"):
                logSupport.log.warning(
                    f"Skipping credential with trust_domain {cred.trust_domain}. "
                    f"Factory requires {factory_trust}. ({cred.id})"
                )
                continue  # Skip credentials that don't match the trust domain
            # NOTE: Up to GWMS 3.10.x glideclient was always advertised. This is a new behavior.
            # If a credential has no work assigned to it or active Glideins using it, no glideclient Ad be advertised for it.
            if (
                request_cred.req_idle == 0
                and request_cred.req_max_run == 0
                and params_obj.glidein_monitors_per_cred[cred.id]["GlideinsTotal"] == 0
            ):
                logSupport.log.debug(f"Skipping credential with no work assigned or active glideins. ({cred.id})")
                continue  # Skip credentials with no work assigned or active glideins

            classad_name = f"{cred.id}_{params_obj.request_name}@{self.descript_obj.my_name}"

            glidein_params_to_encrypt = {}
            if params_obj.glidein_params_to_encrypt:
                glidein_params_to_encrypt = copy.deepcopy(params_obj.glidein_params_to_encrypt)

            # Add request specific parameters
            glidein_params_to_encrypt["RequestCredentials"] = pickle.dumps([cred])

            # Convert the security class to a string so the Factory can interpret the value correctly
            glidein_params_to_encrypt["SecurityClass"] = str(cred.security_class)
            if params_obj.security_name is not None:
                glidein_params_to_encrypt["SecurityName"] = params_obj.security_name

            # Encrypt parameters
            encrypted_params = {}
            if key_obj:
                for attr in glidein_params_to_encrypt:
                    encrypted_params[attr] = key_obj.encrypt_hex(glidein_params_to_encrypt[attr]).decode(
                        defaults.BINARY_ENCODING_CRYPTO
                    )

            # Generate classad info tuples
            classad_info_tuples = (
                (frontendConfig.glidein_param_prefix, params_obj.glidein_params),
                (frontendConfig.encrypted_param_prefix, encrypted_params),
                (frontendConfig.glidein_config_prefix, self.glidein_config_limits),
            )

            # Get the glidein monitors for this credential
            glidein_monitors_this_cred = params_obj.glidein_monitors_per_cred.get(
                cred.id, {}  # type: ignore[attr-defined]
            )

            # Update Sequence number information
            if classad_name in advertiseGCCounter:
                advertiseGCCounter[classad_name] += 1
            else:
                advertiseGCCounter[classad_name] = 0

            fname = f"{self.adname}"
            if not frontendConfig.advertise_use_multi:
                fname += f"_{self.unique_id}"
                self.unique_id += 1

            try:
                logSupport.log.debug(f"Writing {fname}")
                with open(fname, "a", encoding="utf-8") as fd:
                    fd.write(f'MyType = "{frontendConfig.client_id}"\n')
                    fd.write(f'GlideinMyType = "{frontendConfig.client_id}"\n')
                    fd.write(f'GlideinWMSVersion = "{frontendConfig.glideinwms_version}"\n')
                    fd.write(f'Name = "{classad_name}"\n')
                    fd.write("\n".join(self.descript_obj.get_id_attrs()) + "\n")
                    fd.write(f'ReqName = "{params_obj.request_name}"\n')
                    fd.write(f'ReqGlidein = "{params_obj.glidein_name}"\n')

                    fd.write("\n".join(self.descript_obj.get_web_attrs()) + "\n")

                    if key_obj:
                        fd.write("\n".join(key_obj.get_key_attrs()) + "\n")

                    fd.write(f"ReqIdleGlideins = {request_cred.req_idle}\n")
                    fd.write(f"ReqMaxGlideins = {request_cred.req_max_run}\n")
                    fd.write(f'ReqRemoveExcess = "{params_obj.remove_excess_str}"\n')
                    fd.write(f"ReqRemoveExcessMargin = {params_obj.remove_excess_margin}\n")
                    fd.write(f'ReqIdleLifetime = "{params_obj.idle_lifetime}"\n')
                    fd.write(f'WebMonitoringURL = "{self.descript_obj.monitoring_web_url}"\n')

                    for prefix, data in classad_info_tuples:
                        for attr in list(data.keys()):
                            writeTypedClassadAttrToFile(fd, f"{prefix}{attr}", data[attr])

                    for attr_name in params_obj.glidein_monitors:
                        prefix = frontendConfig.glidein_monitor_prefix
                        # attr_value = params_obj.glidein_monitors[attr_name]
                        if (attr_name == "RunningHere") and glidein_monitors_this_cred:
                            # This double check is for backward compatibility
                            attr_value = glidein_monitors_this_cred.get("GlideinsRunning", 0)
                        elif (attr_name == "Running") and glidein_monitors_this_cred:
                            # This double check is for backward compatibility
                            attr_value = glidein_monitors_this_cred.get("ScaledRunning", 0)
                        else:
                            attr_value = glidein_monitors_this_cred.get(
                                attr_name, params_obj.glidein_monitors[attr_name]
                            )
                        writeTypedClassadAttrToFile(fd, f"{prefix}{attr_name}", attr_value)

                    fd.write(f"UpdateSequenceNumber = {advertiseGCCounter[classad_name]}\n")

                    # add a final empty line... useful when appending
                    fd.write("\n")
            except Exception as e:
                logSupport.log.exception(f"Exception writing advertisement file: {e}")
                if os.path.exists(fname):
                    os.remove(fname)
                raise
                # TODO: Should we revert the changes done to advertiseGCCounter[classad_name]?

            cred_filename_arr.append(fname)

            logSupport.log.debug(
                f"Advertising credential {cred.path} "  # type: ignore[attr-defined]
                f"with ({request_cred.req_idle} idle, {request_cred.req_max_run} max run) for request {params_obj.request_name}"
            )

        return cred_filename_arr

    def set_glidein_config_limits(self, limits_data):
        """
        Set various limits and curbs configured in the frontend config
        into the glideresource classad
        """
        self.glidein_config_limits = limits_data


def writeTypedClassadAttrToFile(fd, attr_name, attr_value):
    """
    Given the FD, type check the value and write the info the classad file
    """
    if isinstance(attr_value, (int, float)):
        # don't quote numeric values
        fd.write(f"{attr_name} = {attr_value}\n")
    else:
        escaped_value = str(attr_value).replace('"', '\\"').replace("\n", "\\n")
        fd.write(f'{attr_name} = "{escaped_value}"\n')


# Remove ClassAd from Collector
def deadvertiseAllWork(factory_pool, my_name, ha_mode="master"):
    """
    Removes all work requests for the client in the factory.
    """
    global frontendConfig

    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gc")
    fd = open(tmpnam, "w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % frontendConfig.client_id)
            fd.write(
                'Requirements = (ClientName == "%s") && (GlideinMyType == "%s") && (FrontendHAMode == "%s")\n'
                % (my_name, frontendConfig.client_id, ha_mode)
            )
        finally:
            fd.close()

        exe_condor_advertise(tmpnam, "INVALIDATE_MASTER_ADS", factory_pool)
    finally:
        os.remove(tmpnam)


def deadvertiseAllGlobals(factory_pool, my_name, ha_mode="master"):
    """
    Removes all globals classads for the client in the factory.
    """
    global frontendConfig

    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gcg")
    fd = open(tmpnam, "w")
    try:
        try:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % frontendConfig.client_global)
            fd.write(
                'Requirements = (ClientName == "%s") && (GlideinMyType == "%s") && (FrontendHAMode == "%s")\n'
                % (my_name, frontendConfig.client_global, ha_mode)
            )
        finally:
            fd.close()

        exe_condor_advertise(tmpnam, "INVALIDATE_MASTER_ADS", factory_pool)
    finally:
        os.remove(tmpnam)


###############################################################################
# Code to advertise glideresource classads to the User Pool
###############################################################################


class ResourceClassad(classadSupport.Classad):
    """This class describes the resource classad. Frontend advertises the
    resource classad to the user pool as an UPDATE_AD_GENERIC type classad
    """

    def __init__(self, factory_ref, frontend_ref):
        """Initializes a new instance of the ResourceClassad class with the provided Factory and Frontend references.

        This constructor sets up the initial values for the resource classad, using the provided
        `factory_ref` (the name of the resource in the glidefactory classad) and `frontend_ref`
        (the name of the resource in the glideclient classad).
        This constructor initializes a resource classad with the following parameters:
        - GlideinWMS version
        - Factory name (`factory_ref`)
        - Frontend name (`frontend_ref`)
        - Name (constructed from `factory_ref` and `frontend_ref`)
        - Downtime status (set to "False")
        - Update sequence number (managed using a global counter)

        Args:
            factory_ref (str): The name of the resource in the glidefactory classad.
            frontend_ref (str): The name of the resource in the glideclient classad.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> print(resource_ad.adParams["GlideFactoryName"])
            glidefactory1
            >>> print(resource_ad.adParams["Name"])
            glidefactory1@glideclient1
        """
        global advertiseGRCounter

        classadSupport.Classad.__init__(self, "glideresource", "UPDATE_AD_GENERIC", "INVALIDATE_ADS_GENERIC")

        self.adParams["GlideinWMSVersion"] = frontendConfig.glideinwms_version
        self.adParams["GlideFactoryName"] = "%s" % factory_ref
        self.adParams["GlideClientName"] = "%s" % frontend_ref
        self.adParams["Name"] = f"{factory_ref}@{frontend_ref}"
        self.adParams["GLIDEIN_In_Downtime"] = "False"

        if self.adParams["Name"] in advertiseGRCounter:
            advertiseGRCounter[self.adParams["Name"]] += 1
        else:
            advertiseGRCounter[self.adParams["Name"]] = 0
        self.adParams["UpdateSequenceNumber"] = advertiseGRCounter[self.adParams["Name"]]

    def setFrontendDetails(self, frontend_name, group_name, ha_mode):
        """Sets the detailed description of the Frontend in the classad.

        This method updates the frontend details, including the frontend name, group name,
        and high-availability mode (HA mode). These details are essential for advertising
        the frontend to the GlideinWMS system.

        Args:
            frontend_name (str): The name of the frontend, representing the frontend MatchExpr.
            group_name (str): The name of the group associated with the frontend, representing the job query_expr.
            ha_mode (str): The high-availability mode of the frontend, typically "master" or "slave".

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> resource_ad.setFrontendDetails("frontend1", "groupA", "master")
            >>> print(resource_ad.adParams["FrontendName"])
            frontend1
            >>> print(resource_ad.adParams["GroupName"])
            groupA
            >>> print(resource_ad.adParams["FrontendHAMode"])
            master
        """
        self.adParams["GlideFrontendName"] = "%s" % frontend_name
        self.adParams["GlideGroupName"] = "%s" % group_name
        self.adParams["GlideFrontendHAMode"] = "%s" % ha_mode

    def setMatchExprs(self, match_expr, job_query_expr, factory_query_expr, start_expr):
        """Sets the Frontend Match and query Expressions in the classad.

        Args:
            match_expr (str): The match expression
            job_query_expr (str): The job query expression
            factory_query_expr (str): The factory query expression
            start_expr (str): The start expression
        """
        self.adParams["GlideClientMatchingGlideinCondorExpr"] = "%s" % match_expr
        self.adParams["GlideClientConstraintJobCondorExpr"] = "%s" % job_query_expr
        self.adParams["GlideClientMatchingInternalPythonExpr"] = "%s" % factory_query_expr
        self.adParams["GlideClientConstraintFactoryCondorExpr"] = "%s" % start_expr

    def setInDownTime(self, downtime):
        """Sets the downtime flag for the resource in the classad.

        This method updates the "GLIDEIN_In_Downtime" parameter in the classad to reflect
        whether the resource is in downtime. The downtime flag is represented as a string,
        where `True` is set to "True" and `False` is set to "False".

        Args:
            downtime (bool): A boolean indicating whether the resource is in downtime.
                              Pass `True` if the entry is in downtime, `False` otherwise.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> resource_ad.setInDownTime(True)
            >>> print(resource_ad.adParams["GLIDEIN_In_Downtime"])
            True
        """
        self.adParams["GLIDEIN_In_Downtime"] = str(downtime)

    def setGlideClientMonitorInfo(self, monitorInfo):
        """Sets the GlideClientMonitor information for the resource in the classad.

        This method updates the classad with the provided GlideClientMonitor information,
        typically used for monitoring the state of the GlideClient associated with the resource.

        Args:
            monitorInfo (list): A list containing the GlideClientMonitor information to be set in the classad.
                                The list should include relevant data for monitoring the GlideClient.

        Raises:
            RuntimeError: If the monitorInfo information does not have exactly the 17 expected elements.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> monitor_data = ["Monitor1", "Status: Active", "LastChecked: 2025-08-01"]
            >>> resource_ad.setGlideClientMonitorInfo(monitor_data)
            >>> print(resource_ad.adParams["GlideClientMonitor"])
            ["Monitor1", "Status: Active", "LastChecked: 2025-08-01"]
        """

        if len(monitorInfo) == 17:
            self.adParams["GlideClientMonitorJobsIdle"] = monitorInfo[0]
            self.adParams["GlideClientMonitorJobsIdleMatching"] = monitorInfo[1]
            self.adParams["GlideClientMonitorJobsIdleEffective"] = monitorInfo[2]
            self.adParams["GlideClientMonitorJobsIdleOld"] = monitorInfo[3]
            self.adParams["GlideClientMonitorJobsIdleUnique"] = monitorInfo[4]
            self.adParams["GlideClientMonitorJobsRunning"] = monitorInfo[5]
            self.adParams["GlideClientMonitorJobsRunningHere"] = monitorInfo[6]
            self.adParams["GlideClientMonitorJobsRunningMax"] = monitorInfo[7]
            self.adParams["GlideClientMonitorGlideinsTotal"] = monitorInfo[8]
            self.adParams["GlideClientMonitorGlideinsIdle"] = monitorInfo[9]
            self.adParams["GlideClientMonitorGlideinsRunning"] = monitorInfo[10]
            self.adParams["GlideClientMonitorGlideinsFailed"] = monitorInfo[11]
            self.adParams["GlideClientMonitorGlideinsTotalCores"] = monitorInfo[12]
            self.adParams["GlideClientMonitorGlideinsIdleCores"] = monitorInfo[13]
            self.adParams["GlideClientMonitorGlideinsRunningCores"] = monitorInfo[14]
            self.adParams["GlideClientMonitorGlideinsRequestIdle"] = monitorInfo[15]
            self.adParams["GlideClientMonitorGlideinsRequestMaxRun"] = monitorInfo[16]
        else:
            raise RuntimeError(
                "Glide client monitoring structure changed. Resource ad may have incorrect GlideClientMonitor values"
            )

    def setEntryInfo(self, info):
        """Sets the entry-specific information for the resource in the classad.

        This method processes the provided `info` dictionary, which contains useful data from the
        glidefactory classad, and updates the resource's classad with the relevant attributes.
        Certain attributes are excluded from being added to the classad, while others are added with potential prefix modifications.

        Args:
            info (dict): A dictionary containing useful information from the glidefactory classad.
                         The dictionary should include key-value pairs of attributes to be added to the classad.


        """

        eliminate_attrs = {
            "CurrentTime",
            "PubKeyValue",
            "PubKeyType",
            "AuthenticatedIdentity",
            "GlideinName",
            "FactoryName",
            "EntryName",
            "GlideinWMSVersion",
            "PubKeyObj",
            "LastHeardFrom",
            "PubKeyID",
            "SupportedSignTypes",
            "GLIDEIN_In_Downtime",
        }
        available_attrs = set(info.keys())
        publish_attrs = available_attrs - eliminate_attrs
        for attr in publish_attrs:
            ad_key = attr
            if attr.startswith(frontendConfig.glidein_config_prefix):
                # Condvert GlideinConfig -> GlideFactoryConfig
                ad_key = attr.replace(frontendConfig.glidein_config_prefix, "GlideFactoryConfig", 1)
            self.adParams[ad_key] = info[attr]

    def setEntryMonitorInfo(self, info):
        """Sets the entry-specific monitor information for the resource in the classad.

        This method processes the provided `info` dictionary, which contains data from the
        glidefactory classad, and updates the resource classad with the job completion information.

        Args:
            info (dict): A dictionary containing useful information from the glidefactory classad.
        """
        # Monitoring Prefixes are considering format_condor_dict that strips "GlideinMonitor"
        for k in info:
            if k.startswith("CompletedJobs"):
                self.adParams["GlideFactoryMonitor" + k] = info[k]

    def setGlideFactoryMonitorInfo(self, info):
        """Sets the GlideinFactoryMonitor information for the resource in the classad.

        This method updates the resource's classad with the relevant monitoring information (e.g., `GlideinFactoryMonitor`)
        from the glidefactoryclient classad. The provided `info` dictionary contains useful monitoring data
        that is added to the classad for tracking and monitoring purposes.

        Args:
            info (dict): A dictionary containing useful monitoring information from the glidefactoryclient classad.
                         The dictionary should include key-value pairs for attributes such as `GlideinFactoryMonitor`
                         and other related monitoring data.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> monitor_info = {
            >>>     "GlideinFactoryMonitorStatus": "Active",
            >>>     "GlideinFactoryMonitorJobs": 100
            >>> }
            >>> resource_ad.setGlideFactoryMonitorInfo(monitor_info)
            >>> print(resource_ad.adParams["GlideinFactoryMonitorStatus"])
            Active
            >>> print(resource_ad.adParams["GlideinFactoryMonitorJobs"])
            100
        """

        # Required keys do not start with TotalClientMonitor but only
        # start with Total or Status or Requested. Append GlideFactoryMonitor
        # to these keys and put them in the classad

        for key in info:
            ad_key = key
            if not key.startswith("TotalClientMonitor"):
                if key.startswith("Total") or key.startswith("Status") or key.startswith("Requested"):
                    ad_key = "GlideFactoryMonitor" + key
                    self.adParams[ad_key] = info[key]

    def setGlideClientConfigLimits(self, info):
        """Sets the GlideClientConfig configuration information for the resource in the classad.

        This method updates the resource's classad with the provided `GlideClientConfig` information.
        Each key in the `info` dictionary is used to create a corresponding `GlideClientConfig` attribute in the classad.

        Args:
            info (dict): A dictionary containing useful configuration information. Each key-value pair in the dictionary
                         is used to set a corresponding `GlideClientConfig*` attribute in the classad.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> config_info = {
            >>>     "MaxMemory": 2048,
            >>>     "MaxCPUs": 4
            >>> }
            >>> resource_ad.setGlideClientConfigLimits(config_info)
            >>> print(resource_ad.adParams["GlideClientConfigMaxMemory"])
            2048
            >>> print(resource_ad.adParams["GlideClientConfigMaxCPUs"])
            4
        """

        for key in info:
            self.adParams["GlideClientConfig%s" % key] = info[key]

    def setCurbsAndLimits(self, limits_triggered):
        """Sets descriptive messages about which limits and curbs have been triggered when deciding
        the number of Glideins to request.

        This method processes the provided `limits_triggered` dictionary, which contains limits
        and curbs that have been triggered, and updates the classad with the corresponding
        descriptive messages. It distinguishes between curbs and limits based on the key prefix
        ("Curb" or "Limit") and formats the corresponding classad message accordingly.

        Args:
            limits_triggered (dict): A dictionary containing the limits and curbs that have been triggered.
                                      The keys should represent the name of the limit or curb, and the values
                                      represent the associated messages or values.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> limits_info = {
            >>>     "CurbMaxMemory": "Max memory exceeded",
            >>>     "LimitMaxCPUs": "Max CPUs requested"
            >>> }
            >>> resource_ad.setCurbsAndLimits(limits_info)
            >>> print(resource_ad.adParams["GlideClientCurbMaxMemory"])
            Max memory exceeded
            >>> print(resource_ad.adParams["GlideClientLimitMaxCPUs"])
            Max CPUs requested
        """
        for k, v in limits_triggered.items():
            if k.startswith("Curb"):
                classadmessage = "GlideClientCurb" + k
            else:
                classadmessage = "GlideClientLimit" + k

            self.adParams[classadmessage] = v


class ResourceClassadAdvertiser(classadSupport.ClassadAdvertiser):
    """Class to handle the advertisement of resource classads to the user pool"""

    def __init__(self, pool=None, multi_support=False):
        """Initializes the object with the specified collector address and multi-support setting.

        This constructor initializes the instance with a `pool` (collector address) and a flag
        `multi_support` that determines whether the installation supports advertising multiple
        classads with a single `condor_advertise` command.

        Args:
            pool (str, optional): The address of the collector. Defaults to `None`, indicating no collector address is set.
            multi_support (bool, optional): A boolean flag indicating whether multiple classads can be advertised with one `condor_advertise` command. Defaults to `False`.

        Example:
            >>> obj = ResourceClassadAdvertiser(pool="collector_address", multi_support=True)
            >>> print(obj.pool)
            collector_address
            >>> print(obj.adType)
            glideresource
        """

        classadSupport.ClassadAdvertiser.__init__(
            self, pool=pool, multi_support=multi_support, tcp_support=frontendConfig.advertise_use_tcp
        )

        self.adType = "glideresource"
        self.adAdvertiseCmd = "UPDATE_AD_GENERIC"
        self.adInvalidateCmd = "INVALIDATE_ADS_GENERIC"
        self.advertiseFilePrefix = "gfi_ar"


class FrontendMonitorClassad(classadSupport.Classad):
    """This class describes the frontend monitor classad. Frontend advertises the
    monitor classad to the user pool as an UPDATE_AD_GENERIC type classad
    """

    def __init__(self, frontend_ref):
        """Class constructor for initializing the frontend monitor classad.

        This constructor initializes the classad parameters and sets the required attributes
        using the provided frontend reference (`frontend_ref`), which is the name of the resource
        in the glideclient classad.

        Args:
            frontend_ref (str): The name of the resource in the glideclient classad.

        Example:
            >>> frontend_monitor = FrontendMonitorClassad("frontend1")
            >>> print(frontend_monitor.adParams["FrontendName"])
            frontend1
        """

        global advertiseGFMCounter

        classadSupport.Classad.__init__(self, "glidefrontendmonitor", "UPDATE_AD_GENERIC", "INVALIDATE_ADS_GENERIC")

        self.adParams["GlideinWMSVersion"] = frontendConfig.glideinwms_version
        self.adParams["Name"] = "%s" % (frontend_ref)
        # self.adParams['GlideFrontend_In_Downtime'] = 'False'

        if self.adParams["Name"] in advertiseGFMCounter:
            advertiseGFMCounter[self.adParams["Name"]] += 1
        else:
            advertiseGFMCounter[self.adParams["Name"]] = 0
        self.adParams["UpdateSequenceNumber"] = advertiseGFMCounter[self.adParams["Name"]]

    def setFrontendDetails(self, frontend_name, groups, ha_mode):
        """Adds the detailed description of the frontend to the classad.

        This method sets the frontend name, associated groups, and high-availability (HA) mode in the classad
        for the frontend resource. The details are added as key-value pairs to the `adParams` dictionary.

        Args:
            frontend_name (str): A representation of the frontend, typically used as the MatchExpr in the classad.
            groups (str): A string representing the groups associated with the frontend, typically used in the job query expression.
            ha_mode (str): The high-availability mode of the frontend, such as "master" or "slave".

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> resource_ad.setFrontendDetails("frontend1", "groupA,groupB", "master")
            >>> print(resource_ad.adParams["GlideFrontendName"])
            frontend1
            >>> print(resource_ad.adParams["GlideFrontendGroups"])
            groupA,groupB
            >>> print(resource_ad.adParams["GlideFrontendHAMode"])
            master
        """
        self.adParams["GlideFrontendName"] = "%s" % frontend_name
        self.adParams["GlideFrontendGroups"] = "%s" % groups
        self.adParams["GlideFrontendHAMode"] = "%s" % ha_mode

    def setIdleJobCount(self, idle_jobs):
        """Sets the idle jobs information in the classad.

        This method updates the classad with the number of idle jobs, using the provided dictionary
        (`idle_jobs`). The dictionary is keyed by idle duration, where each key represents an idle
        duration (e.g., "Total", "3600" for jobs idle more than one hour) and the value is the number
        of jobs that are idle for that duration.

        Args:
            idle_jobs (dict): A dictionary containing idle job information. The keys are the idle durations
                               (e.g., "Total", "3600"), and the values are the counts of idle jobs for
                               those respective durations.

        Example:
            >>> resource_ad = ResourceClassad("glidefactory1", "glideclient1")
            >>> idle_jobs_info = {
            >>>     "Total": 50,
            >>>     "3600": 10
            >>> }
            >>> resource_ad.setIdleJobCount(idle_jobs_info)
            >>> print(resource_ad.adParams["GlideFrontend_IdleJobs_Total"])
            50
            >>> print(resource_ad.adParams["GlideFrontend_IdleJobs_3600"])
            10
        """

        for key in idle_jobs:
            k = "%s" % key
            self.adParams["GlideFrontend_IdleJobs_%s" % k.title()] = idle_jobs[key]

    def setPerfMetrics(self, perf_metrics):
        """Sets the performance metrics information for the Frontend or group in the classad.

        This method updates the classad with performance metrics data for the Frontend or group.
        The performance metrics are provided in a `PerfMetric` object, which includes various events.
        The method generates attribute names based on the metric name and event, then stores the corresponding
        lifetime for each event in the classad.

        Args:
            perf_metrics (servicePerformance.PerfMetric): A `PerfMetric` object containing the performance metrics
                                                          for the frontend or group. This object includes a list of
                                                          events and their associated lifetimes.
        """
        for event in perf_metrics.metric:
            attr_name = f"{frontendConfig.glidein_perfmetric_prefix}_{perf_metrics.name}_{event}"
            self.adParams[attr_name] = perf_metrics.event_lifetime(event)


class FrontendMonitorClassadAdvertiser(classadSupport.ClassadAdvertiser):
    """Class to handle the advertisement of frontend monitor classads to the user pool"""

    def __init__(self, pool=None, multi_support=False):
        """Initializes the object for advertising a frontend monitor classad.

        This constructor sets up the classad advertiser for the frontend monitor, initializing key parameters
        such as the collector address, multi-support capability, and TCP support based on the configuration.

        Args:
            pool (str, optional): The address of the collector. Defaults to `None`, meaning no collector address is set.
            multi_support (bool, optional): Indicates whether the installation supports advertising multiple classads
                                            with a single `condor_advertise` command. Defaults to `False`.

        Initializes the following class attributes:
            adType (str): The type of classad being advertised (set to "glidefrontendmonitor").
            adAdvertiseCmd (str): The command used for advertising the classad (set to "UPDATE_AD_GENERIC").
            adInvalidateCmd (str): The command used for invalidating the classad (set to "INVALIDATE_ADS_GENERIC").
            advertiseFilePrefix (str): The file prefix for the advertise file (set to "gfi_afm").

        Example:
            >>> frontend_monitor_adv = FrontendMonitorClassadAdvertiser("frontend1")
            >>> print(frontend_monitor_adv.adType)
            glidefrontendmonitor
            >>> print(frontend_monitor_adv.adAdvertiseCmd)
            UPDATE_AD_GENERIC
        """

        classadSupport.ClassadAdvertiser.__init__(
            self, pool=pool, multi_support=multi_support, tcp_support=frontendConfig.advertise_use_tcp
        )

        self.adType = "glidefrontendmonitor"
        self.adAdvertiseCmd = "UPDATE_AD_GENERIC"
        self.adInvalidateCmd = "INVALIDATE_ADS_GENERIC"
        self.advertiseFilePrefix = "gfi_afm"


############################################################
#
# I N T E R N A L - Do not use
#
############################################################


def exe_condor_advertise(fname, command, pool, is_multi=False):
    logSupport.log.debug(f"CONDOR ADVERTISE {fname} {command} {pool} {is_multi}")
    return condorManager.condorAdvertise(fname, command, frontendConfig.advertise_use_tcp, is_multi, pool)


class NoCredentialException(Exception):
    pass
