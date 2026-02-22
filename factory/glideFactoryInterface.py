# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Module for advertising and retrieving commands from the Collector.

This module implements the functions needed to advertise ClassAds and get commands
from the Collector.
"""

import fcntl
import os
import time

from glideinwms.lib import classadSupport, condorExe, condorManager, condorMonitor, logSupport

############################################################
#
# Global Variables
#
############################################################

# Define global variables that keep track of the Daemon lifetime
start_time = time.time()
# Advertise counter for glidefactory classad
advertiseGFCounter = {}
# Advertise counter for glidefactoryclient classad
advertiseGFCCounter = {}
# Advertise counter for glidefactoryglobal classad
advertiseGlobalCounter = 0


############################################################
#
# Configuration
#
############################################################

# class FakeLog:
#    def write(self,str):
#        pass


# TODO: Verify the difference form glideFactoryConfig.FactoryConfig and if these can be unified
class FactoryConfig:
    def __init__(self):
        """Initialize a FactoryConfig object with default values.

        Users should modify the attributes if needed.
        """
        # set default values
        # user should modify if needed

        # The name of the attribute that identifies the glidein
        self.factory_id = "glidefactory"
        self.client_id = "glideclient"
        self.factoryclient_id = "glidefactoryclient"
        self.factory_global = "glidefactoryglobal"

        # Default the glideinWMS version string
        self.glideinwms_version = "glideinWMS UNKNOWN"

        # String to prefix for the attributes
        self.glidein_attr_prefix = ""

        # String to prefix for the submit attributes
        self.glidein_submit_prefix = "GlideinSubmit"

        # String to prefix for the parameters
        self.glidein_param_prefix = "GlideinParam"
        self.encrypted_param_prefix = "GlideinEncParam"

        # String to prefix for the monitoring
        self.glidein_monitor_prefix = "GlideinMonitor"

        # String to prefix for the configured limits
        self.glidein_config_prefix = "GlideinConfig"

        # String to prefix for the requests
        self.client_req_prefix = "Req"

        # String to prefix for the web passing
        self.client_web_prefix = "Web"
        self.glidein_web_prefix = "Web"

        # The name of the signtype
        self.factory_signtype_id = "SupportedSignTypes"
        self.client_web_signtype_suffix = "SignType"

        # Should we use TCP for condor_advertise?
        self.advertise_use_tcp = False
        # Should we use the new -multiple for condor_advertise?
        self.advertise_use_multi = False

        # warning log files
        # default is FakeLog, any other value must implement the write(str) method
        # self.warning_log = FakeLog()

        # Location of lock directory
        self.lock_dir = "."

        # Location of the factory Collector
        # Please notice that None means "use the system collector"
        # while any string value will force the use of that specific collector
        # i.e. the -pool argument coption to HTCondor cmdline tools
        self.factory_collector = None


# global configuration of the module
factoryConfig = FactoryConfig()

#
# When something is set to this,
# use the value set in factoryConfig
# This is useful when None has a well defined semantics
#   end cannot be used to signal the use of the default
# e.g.
#   the functions getting the default factory_collector value
#   will use
#   factoryConfig.factory_collector
#   (None means "use system collector" in that context)
#
DEFAULT_VAL = "default"


#####################################################
# Exception thrown when multiple executions are used
# Helps handle partial failures
class MultiExeError(condorExe.ExeError):
    """Exception thrown when multiple executions are used.

    Helps to handle partial failures.
    """

    def __init__(self, arr):
        """Initialize MultiExeError object with a list of exceptions.

        Args:
            arr (list): List of ExeError exceptions.
        """
        self.arr = arr

        # First approximation of implementation, can be improved
        str_arr = []
        for e in arr:
            str_arr.append("%s" % e)

        error_str = "\\n".join(str_arr)

        condorExe.ExeError.__init__(self, error_str)


############################################################
#
# User functions
#
############################################################


def findGroupWork(
    factory_name,
    glidein_name,
    entry_names,
    supported_signtypes,
    pub_key_obj=None,
    additional_constraints=None,
    factory_collector=DEFAULT_VAL,
):
    """Find work requests for the specified group.

    This function queries the WMS Collector for request ClassAds that match the
    given factory, glidein, and entry names. The result is returned as a dictionary
    of work to perform, grouped by entry and client (Frontend). Each value is a dictionary
    with keys "requests" and "params" holding ClassAd information about the work request.
    Example: work[entry_name][frontend] = {'params':'value', 'requests':'value}

    Args:
        factory_name (str): Name of the Factory.
        glidein_name (str): Name of the glidein instance.
        entry_names (list): List of Factory entry names.
        supported_signtypes (list, optional): List of supported sign types (e.g. ['sha1']).
            Supports only one kind of signtype, 'sha1'. Default is None
        pub_key_obj (str, optional): Public key object (e.g. RSA key). Defaults to None.
            Supports only one kind of public key, 'RSA'.
        additional_constraints (str, optional): Additional constraints for querying the WMS Collector. Defaults to None.
        factory_collector (str, optional): The collector to query. Special value "default" uses the global config.

    Returns:
        dict: Dictionary of work to perform in the format:
            work[entry_name][frontend] = {'params': 'value', 'requests': 'value'}
    """
    global factoryConfig

    if factory_collector == DEFAULT_VAL:
        factory_collector = factoryConfig.factory_collector

    req_glideins = ""
    for entry in entry_names:
        req_glideins = f"{entry}@{glidein_name}@{factory_name},{req_glideins}"
    # Strip off leading & trailing comma
    req_glideins = req_glideins.strip(",")

    status_constraint = '(GlideinMyType=?="{}") && (stringListMember(ReqGlidein,"{}")=?=True)'.format(
        factoryConfig.client_id,
        req_glideins,
    )

    if supported_signtypes is not None:
        status_constraint += ' && stringListMember({}{},"{}")'.format(
            factoryConfig.client_web_prefix,
            factoryConfig.client_web_signtype_suffix,
            ",".join(supported_signtypes),
        )

    if pub_key_obj is not None:
        # Get only classads that have my key or no key at all
        # Any other key will not work
        status_constraint += (
            ' && (((ReqPubKeyID=?="%s") && (ReqEncKeyCode=!=Undefined) && (ReqEncIdentity=!=Undefined)) || (ReqPubKeyID=?=Undefined))'
            % pub_key_obj.pub_key_id
        )

    if additional_constraints is not None:
        status_constraint = f"({status_constraint})&&({additional_constraints})"

    status = condorMonitor.CondorStatus(subsystem_name="any", pool_name=factory_collector)
    # Important, this dictates what gets submitted
    status.require_integrity(True)
    status.glidein_name = glidein_name

    # Serialize access to the Collector across all the processes
    # there is a single Collector anyhow
    lock_fname = os.path.join(factoryConfig.lock_dir, "gfi_status.lock")
    if not os.path.exists(lock_fname):
        # Create a lock file if needed
        try:
            fd = open(lock_fname, "w")
            fd.close()
        except Exception:
            # could be a race condition
            pass

    with open(lock_fname, "r+") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            status.load(status_constraint)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)

    data = status.fetchStored()

    reserved_names = (
        "ReqName",
        "ReqGlidein",
        "ClientName",
        "FrontendName",
        "GroupName",
        "ReqPubKeyID",
        "ReqEncKeyCode",
        "ReqEncIdentity",
        "AuthenticatedIdentity",
    )

    # Output is now in the format of
    # out[entry_name][frontend]
    out = {}

    # Copy over requests and parameters
    for k in data:
        kel = data[k]
        el = {"requests": {}, "web": {}, "params": {}, "params_decrypted": {}, "monitor": {}, "internals": {}}
        for key, prefix in (
            ("requests", factoryConfig.client_req_prefix),
            ("web", factoryConfig.client_web_prefix),
            ("params", factoryConfig.glidein_param_prefix),
            ("monitor", factoryConfig.glidein_monitor_prefix),
        ):
            plen = len(prefix)
            for attr in kel:
                if attr in reserved_names:
                    # Skip reserved names
                    continue
                if attr[:plen] == prefix:
                    el[key][attr[plen:]] = kel[attr]

        # sym_key_obj will stay None if
        # 1) extract_sym_key throws exception
        # 2) kel does not contain 'ReqPubKeyID'
        # 3) pub_key_obj is None and there is no key to decrypt
        sym_key_obj = None
        if (pub_key_obj is not None) and ("ReqPubKeyID" in kel):
            try:
                sym_key_obj = pub_key_obj.extract_sym_key(kel["ReqEncKeyCode"])
            except Exception:
                continue

        if sym_key_obj is not None:
            # Verify that the identity the client claims to be is the
            # identity that Condor thinks it is
            try:
                enc_identity = sym_key_obj.decrypt_hex(kel["ReqEncIdentity"]).decode("utf-8")
            except Exception:
                logSupport.log.warning(
                    "Client %s provided invalid ReqEncIdentity, could not decode. Skipping for security reasons." % k
                )
                continue  # Corrupted classad
            if enc_identity != kel["AuthenticatedIdentity"]:
                logSupport.log.warning(
                    "Client %s provided invalid ReqEncIdentity(%s!=%s). Skipping for security reasons."
                    % (k, enc_identity, kel["AuthenticatedIdentity"])
                )
                # Either the client is misconfigured or someone is cheating
                continue

        invalid_classad = False
        for key, prefix in (("params_decrypted", factoryConfig.encrypted_param_prefix),):
            # TODO: useless for, only one element
            plen = len(prefix)
            for attr in kel:
                if attr in reserved_names:
                    # Skip reserved names
                    continue
                if attr[:plen] == prefix:
                    # Define it even if I don't understand the content
                    el[key][attr[plen:]] = None
                    if sym_key_obj is not None:
                        try:
                            el[key][attr[plen:]] = sym_key_obj.decrypt_hex(kel[attr])
                        except Exception:
                            # I don't understand it -> invalid
                            invalid_classad = True
                            break

        # Continue if I have problems in an inner loop
        if invalid_classad:
            logSupport.log.warning(
                "At least one of the encrypted parameters for client %s cannot be decoded. Skipping for security reasons."
                % k
            )
            continue

        for attr in kel:
            if attr in (
                "ClientName",
                "FrontendName",
                "GroupName",
                "ReqName",
                "LastHeardFrom",
                "ReqPubKeyID",
                "AuthenticatedIdentity",
            ):
                el["internals"][attr] = kel[attr]

        out[k] = el

    return workGroupByEntries(out)


def workGroupByEntries(work):
    """Group work items by entry.

    Args:
        work (dict): Dictionary of work items for each client.

    Returns:
        dict: Dictionary of work items grouped by entry.
              Example: ``grouped_work[entry][client]``
    """
    grouped_work = {}

    for w in work:
        req_name = work[w]["internals"]["ReqName"]
        try:
            entry = (req_name.split("@"))[0]
            if entry not in grouped_work:
                grouped_work[entry] = {}
            grouped_work[entry][w] = work[w]
        except Exception:
            logSupport.log.warning(
                "Unable to group work for '%s' based on ReqName '%s'. This work item will not be processed."
                % (w, req_name)
            )

    return grouped_work


###############################################################################
# Code to advertise glidefactory classads to the WMS Pool
###############################################################################


class EntryClassad(classadSupport.Classad):
    """Class representing a glidefactory classad for an entry.

    Factory advertises the glidefactory classad to the user pool as an UPDATE_AD_GENERIC type classad.
    """

    def __init__(
        self,
        factory_name,
        glidein_name,
        entry_name,
        trust_domain,
        auth_method,
        supported_signtypes,
        pub_key_obj=None,
        glidein_submit={},
        glidein_attrs={},
        glidein_params={},
        glidein_monitors={},
        glidein_stats={},
        glidein_web_attrs={},
        glidein_config_limits={},
    ):
        """Initialize an EntryClassad object.

        glidein_attrs is a dictionary of values to publish like {"Arch":"INTEL","MinDisk":200000}
        similar for glidein_submits, glidein_params, glidein_monitor_monitors and the other dictionaries.

        Args:
            factory_name (str): Name of the Factory (from the config file root. Defaults to hostname if not set).
            glidein_name (str): Name of the Factory/Glidein installation (from the config file root and glidefactoryglobal)
            entry_name (str): Name of the resource/entry in the configuration file and glidefactory classad.
            trust_domain (str): Trust domain for this entry.
            auth_method (str): Authentication methods supported in glidein submission (e.g. grid_proxy, scitoken).
            supported_signtypes (list): Supported sign types (e.g. ['sha1']).
            pub_key_obj (glideFactoryConfig.GlideinKey, optional): Public key object for encryption. Defaults to None.
            glidein_submit (dict, optional): Dictionary of submit attributes in the configuration. Defaults to {}.
            glidein_attrs (dict, optional): Dictionary of glidein attributes to publish. These are never overwritten
                by clients (Frontends). Defaults to {}.
            glidein_params (dict, optional): Dictionary of parameters to publish. Can be overwritten by clients
                (Frontends). Defaults to {}.
            glidein_monitors (dict, optional): Dictionary of monitor attributes to publish. Defaults to {}.
            glidein_stats (dict, optional): Aggregated Entry(entry) and Factory(total) statistics. Defaults to {}.
            glidein_web_attrs (dict, optional): Dictionary of web attributes. Defaults to {}.
            glidein_config_limits (dict, optional): Dictionary of configured limits. Defaults to {}.
        """
        # TODO: rename glidein_ to entry_ (entry_monitors)?

        global factoryConfig, advertiseGFCounter

        classadSupport.Classad.__init__(self, factoryConfig.factory_id, "UPDATE_AD_GENERIC", "INVALIDATE_ADS_GENERIC")

        # Shorthand for easy access
        classad_name = f"{entry_name}@{glidein_name}@{factory_name}"
        self.adParams["Name"] = classad_name
        self.adParams["FactoryName"] = "%s" % factory_name
        self.adParams["GlideinName"] = "%s" % glidein_name
        self.adParams["EntryName"] = "%s" % entry_name
        self.adParams[factoryConfig.factory_signtype_id] = "%s" % ",".join(supported_signtypes)
        self.adParams["DaemonStartTime"] = int(start_time)
        advertiseGFCounter[classad_name] = advertiseGFCounter.get(classad_name, -1) + 1
        self.adParams["UpdateSequenceNumber"] = advertiseGFCounter[classad_name]
        self.adParams["GlideinWMSVersion"] = factoryConfig.glideinwms_version

        if pub_key_obj is not None:
            self.adParams["PubKeyID"] = "%s" % pub_key_obj.pub_key_id
            self.adParams["PubKeyType"] = "%s" % pub_key_obj.key_type
            self.adParams["PubKeyValue"] = "%s" % pub_key_obj.pub_key.string.decode("ascii").replace("\n", "\\n")
        if "grid_proxy" in auth_method:  # TODO: Check for credentials refactoring impact
            self.adParams["GlideinAllowx509_Proxy"] = "%s" % True
            self.adParams["GlideinRequirex509_Proxy"] = "%s" % True
            self.adParams["GlideinRequireGlideinProxy"] = "%s" % False
        else:
            self.adParams["GlideinAllowx509_Proxy"] = "%s" % False
            self.adParams["GlideinRequirex509_Proxy"] = "%s" % False
            self.adParams["GlideinRequireGlideinProxy"] = "%s" % True

        # write out both the attributes, params and monitors
        for prefix, data in (
            (factoryConfig.glidein_submit_prefix, glidein_submit),
            (factoryConfig.glidein_attr_prefix, glidein_attrs),
            (factoryConfig.glidein_param_prefix, glidein_params),
            (factoryConfig.glidein_monitor_prefix, glidein_monitors),
            (factoryConfig.glidein_web_prefix, glidein_web_attrs),
            (factoryConfig.glidein_config_prefix, glidein_config_limits),
        ):
            for attr in list(data.keys()):
                el = data[attr]
                # TODO: ClassAd attribute names must be alphanumeric and _
                #  ad-hoc filter to be replaces with more exhaustive one
                #  not expecting more that initial +, so OK for now
                if attr[0] == "+":
                    attr = f"_PLUS_{attr[1:]}"
                if isinstance(el, int):
                    # don't quote ints
                    self.adParams[f"{prefix}{attr}"] = el
                else:
                    escaped_el = str(el).replace("\n", "\\n")
                    self.adParams[f"{prefix}{attr}"] = "%s" % escaped_el

        # write job completion statistics
        if glidein_stats:
            prefix = factoryConfig.glidein_monitor_prefix
            for k, v in list(glidein_stats["entry"].items()):
                self.adParams[f"{prefix}{k}"] = v
            for k, v in list(glidein_stats["total"].items()):
                self.adParams[f"{prefix}{k}"] = v


###############################################################################
# Code to advertise glidefactoryglobal classads to the WMS Pool
###############################################################################


class FactoryGlobalClassad(classadSupport.Classad):
    """Class representing the glidefactoryglobal ClassAd.

    Factory advertises this ClassAd to the user pool as an UPDATE_AD_GENERIC type ClassAd.
    The glidefactory and glidefactoryglobal ClassAds must be of the same type because they
    may be invalidated together (with a single command).
    """

    def __init__(self, factory_name, glidein_name, supported_signtypes, pub_key_obj):
        """Initialize a FactoryGlobalClassad object.

        Args:
            factory_name (str): Name of the Factory.
            glidein_name (str): Name of the resource in the classad.
            supported_signtypes (list): List of supported sign types (e.g. ['sha1']).
            pub_key_obj (glideFactoryConfig.GlideinKey): Public key object (GlideinKey) used for encryption by the client (Frontend).
        """
        global factoryConfig, advertiseGlobalCounter

        classadSupport.Classad.__init__(
            self, factoryConfig.factory_global, "UPDATE_AD_GENERIC", "INVALIDATE_ADS_GENERIC"
        )

        # Short hand for easy access
        classad_name = f"{glidein_name}@{factory_name}"
        self.adParams["Name"] = classad_name
        self.adParams["FactoryName"] = "%s" % factory_name
        self.adParams["GlideinName"] = "%s" % glidein_name
        self.adParams[factoryConfig.factory_signtype_id] = "%s" % ",".join(supported_signtypes)
        self.adParams["DaemonStartTime"] = int(start_time)
        self.adParams["UpdateSequenceNumber"] = advertiseGlobalCounter
        advertiseGlobalCounter += 1
        self.adParams["GlideinWMSVersion"] = factoryConfig.glideinwms_version
        self.adParams["PubKeyID"] = "%s" % pub_key_obj.pub_key_id
        self.adParams["PubKeyType"] = "%s" % pub_key_obj.key_type
        self.adParams["PubKeyValue"] = "%s" % pub_key_obj.pub_key.string.decode("ascii").replace("\n", "\\n")


def advertiseGlobal(
    factory_name, glidein_name, supported_signtypes, pub_key_obj, stats_dict={}, factory_collector=DEFAULT_VAL
):
    """Create and advertise the glidefactoryglobal ClassAd.

    Args:
        factory_name (str): The name of the Factory.
        glidein_name (str): The name of the glidein (entry).
        supported_signtypes (list): Supported sign types (e.g. ['sha1']).
        pub_key_obj (GlideinKey): Public key object for encryption in the client (Frontend).
        stats_dict (dict, optional): Completed jobs statistics. Defaults to {}.
        factory_collector (str or None): The collector to query. Special value 'default' retrieves it from the global configuration.
    """
    # TODO: Add support for Factory downtime.

    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_ad_gfg")

    gfg_classad = FactoryGlobalClassad(factory_name, glidein_name, supported_signtypes, pub_key_obj)

    try:
        gfg_classad.writeToFile(tmpnam, append=False)
        exe_condor_advertise(tmpnam, gfg_classad.adAdvertiseCmd, factory_collector=factory_collector)
    finally:
        # Unable to write classad
        _remove_if_there(tmpnam)


def deadvertiseGlidein(factory_name, glidein_name, entry_name, factory_collector=DEFAULT_VAL):
    """Remove from the WMS Collector the glidefactory classad advertising the entry.

    Args:
        factory_name (str): Name of the factory.
        glidein_name (str): Name of the glidein.
        entry_name (str): Name of the entry.
        factory_collector (str or None): The collector to query.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gf")
    # TODO: use tempfile
    try:
        with open(tmpnam, "w") as fd:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % factoryConfig.factory_id)
            fd.write(
                'Requirements = (Name == "%s@%s@%s")&&(GlideinMyType == "%s")\n'
                % (entry_name, glidein_name, factory_name, factoryConfig.factory_id)
            )
        exe_condor_advertise(tmpnam, "INVALIDATE_ADS_GENERIC", factory_collector=factory_collector)
    finally:
        _remove_if_there(tmpnam)


def deadvertiseGlobal(factory_name, glidein_name, factory_collector=DEFAULT_VAL):
    """Remove from the WMS Collector the glidefactoryglobal classad advertising the Factory globals.

    Args:
        factory_name (str): The name of the factory.
        glidein_name (str): The name of the glidein.
        factory_collector (str or None): The collector to query.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gfg")
    # TODO: use tempfile
    try:
        with open(tmpnam, "w") as fd:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % factoryConfig.factory_global)
            fd.write(
                'Requirements = (Name == "%s@%s")&&(GlideinMyType == "%s")\n'
                % (glidein_name, factory_name, factoryConfig.factory_id)
            )
        exe_condor_advertise(tmpnam, "INVALIDATE_ADS_GENERIC", factory_collector=factory_collector)
    finally:
        _remove_if_there(tmpnam)


def deadvertiseFactory(factory_name, glidein_name, factory_collector=DEFAULT_VAL):
    """De-advertise all entry and global classads for the specified Factory.

    Args:
        factory_name (str): The name of the factory.
        glidein_name (str): The name of the glidein.
        factory_collector (str or None): The collector to query.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_fact")
    # TODO: use tempfile
    try:
        with open(tmpnam, "w") as fd:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % factoryConfig.factory_id)
            fd.write(f'Requirements = (FactoryName =?= "{factory_name}")&&(GlideinName =?= "{glidein_name}")\n')
        exe_condor_advertise(tmpnam, "INVALIDATE_ADS_GENERIC", factory_collector=factory_collector)
    finally:
        _remove_if_there(tmpnam)


############################################################


# glidein_attrs is a dictionary of values to publish
#  like {"Arch":"INTEL","MinDisk":200000}
# similar for glidein_params and glidein_monitor_monitors
def advertiseGlideinClientMonitoring(
    factory_name,
    glidein_name,
    entry_name,
    client_name,
    client_int_name,
    client_int_req,
    glidein_attrs={},
    client_params={},
    client_monitors={},
    factory_collector=DEFAULT_VAL,
):
    """Advertise glidefactoryclient classads.

    Creates the glidefactoryclient classad file and advertises it.

    Args:
        factory_name (str): The name of the factory.
        glidein_name (str): The name of the glidein.
        entry_name (str): The name of the entry.
        client_name (str): The client name.
        client_int_name (str): The internal client name.
        client_int_req (str): The request name.
        glidein_attrs (dict, optional): Glidein attributes. Defaults to {}.
        client_params (dict, optional): Client parameters. Defaults to {}.
        client_monitors (dict, optional): Client monitors. Defaults to {}.
        factory_collector (str or None): The collector to query. Defaults to DEFAULT_VAL.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_adm_gfc")

    createGlideinClientMonitoringFile(
        tmpnam,
        factory_name,
        glidein_name,
        entry_name,
        client_name,
        client_int_name,
        client_int_req,
        glidein_attrs,
        client_params,
        client_monitors,
    )
    advertiseGlideinClientMonitoringFromFile(tmpnam, remove_file=True, factory_collector=factory_collector)


class MultiAdvertiseGlideinClientMonitoring:
    """Class for multi-advertising of glidefactoryclient classads.

    This class aggregates multiple client monitoring data items and advertises them in a single multi-classad.
    """

    # glidein_attrs is a dictionary of values to publish
    #  like {"Arch":"INTEL","MinDisk":200000}
    def __init__(self, factory_name, glidein_name, entry_name, glidein_attrs, factory_collector=DEFAULT_VAL):
        """Initialize a MultiAdvertizeGlideinClientMonitoring instance.

        Args:
            factory_name (str): The name of the factory.
            glidein_name (str): The name of the glidein.
            entry_name (str): The name of the entry.
            glidein_attrs (dict): Glidein attributes, e.g. `{"Arch":"INTEL","MinDisk":200000}`.
            factory_collector (str or None): The collector to query. Defaults to DEFAULT_VAL.
        """
        self.factory_name = factory_name
        self.glidein_name = glidein_name
        self.entry_name = entry_name
        self.glidein_attrs = glidein_attrs
        self.client_data = []
        self.factory_collector = factory_collector

    def add(
        self, client_name, client_int_name, client_int_req, client_params={}, client_monitors={}, limits_triggered={}
    ):
        """Add a client monitoring record.

        Args:
            client_name (str): The client name.
            client_int_name (str): The internal client name.
            client_int_req (str): The request name.
            client_params (dict, optional): Client parameters. Defaults to {}.
            client_monitors (dict, optional): Client monitor data. Defaults to {}.
            limits_triggered (dict, optional): Limits triggered data. Defaults to {}.
        """
        el = {
            "client_name": client_name,
            "client_int_name": client_int_name,
            "client_int_req": client_int_req,
            "client_params": client_params,
            "client_monitors": client_monitors,
            "limits_triggered": limits_triggered,
        }
        self.client_data.append(el)

    # do the actual advertising
    # can throw MultiExeError
    def do_advertise(self):
        """Advertise the collected client monitoring classads.

        Chooses between multi-advertising or iterative advertising based on configuration.

        Raises:
            MultiExeError: If one or more advertisement executions fail.
        """
        if factoryConfig.advertise_use_multi:
            self.do_advertise_multi()
        else:
            self.do_advertise_iterate()
        self.client_data = []

    # INTERNAL
    def do_advertise_iterate(self):
        """Iteratively advertise each client monitoring record.

        Raises:
            MultiExeError: If one or more advertisement executions fail.
        """
        error_arr = []

        tmpnam = classadSupport.generate_classad_filename(prefix="gfi_ad_gfc")

        for el in self.client_data:
            createGlideinClientMonitoringFile(
                tmpnam,
                self.factory_name,
                self.glidein_name,
                self.entry_name,
                el["client_name"],
                el["client_int_name"],
                el["client_int_req"],
                self.glidein_attrs,
                el["client_params"],
                el["client_monitors"],
            )
            try:
                advertiseGlideinClientMonitoringFromFile(
                    tmpnam, remove_file=True, factory_collector=self.factory_collector
                )
            except condorExe.ExeError as e:
                error_arr.append(e)

        if len(error_arr) > 0:
            raise MultiExeError(error_arr)

    def do_advertise_multi(self):
        """Advertise client monitoring records as a multi-classad.

        Raises:
            MultiExeError: If advertisement fails.
        """
        tmpnam = classadSupport.generate_classad_filename(prefix="gfi_adm_gfc")

        ap = False
        for el in self.client_data:
            createGlideinClientMonitoringFile(
                tmpnam,
                self.factory_name,
                self.glidein_name,
                self.entry_name,
                el["client_name"],
                el["client_int_name"],
                el["client_int_req"],
                self.glidein_attrs,
                el["client_params"],
                el["client_monitors"],
                do_append=ap,
            )
            ap = True  # Append from here on

        if ap:
            error_arr = []
            try:
                advertiseGlideinClientMonitoringFromFile(
                    tmpnam, remove_file=True, is_multi=True, factory_collector=self.factory_collector
                )
            except condorExe.ExeError as e:
                error_arr.append(e)

            if len(error_arr) > 0:
                raise MultiExeError(error_arr)

    def writeToMultiClassadFile(self, filename=None, append=True):
        """Write all client monitoring records to a multi-classad file.

        Args:
            filename (str, optional): The file to write to. If None, a new filename is generated.
            append (bool, optional): Whether to append to the file. Defaults to True.

        Returns:
            str: The filename where classads were written.
        """
        # filename: Name of the file to write classads to
        # append: Whether the classads need to be appended to the file
        #         If we create file append is in a way ignored

        if filename is None:
            filename = classadSupport.generate_classad_filename(prefix="gfi_adm_gfc")
            append = False

        for el in self.client_data:
            createGlideinClientMonitoringFile(
                filename,
                self.factory_name,
                self.glidein_name,
                self.entry_name,
                el["client_name"],
                el["client_int_name"],
                el["client_int_req"],
                self.glidein_attrs,
                el["client_params"],
                el["client_monitors"],
                el["limits_triggered"],
                do_append=append,
            )
            # Append from here on anyway
            append = True

        return filename


##############################
# Start INTERNAL


# glidein_attrs is a dictionary of values to publish
#  like {"Arch":"INTEL","MinDisk":200000}
# similar for glidein_params and glidein_monitor_monitors
def createGlideinClientMonitoringFile(
    fname,
    factory_name,
    glidein_name,
    entry_name,
    client_name,
    client_int_name,
    client_int_req,
    glidein_attrs={},
    client_params={},
    client_monitors={},
    limits_triggered={},
    do_append=False,
):
    """Create a file for glidein client monitoring classad advertisement.

    Args:
        fname (str): Filename to write classad information.
        factory_name (str): Name of the factory.
        glidein_name (str): Name of the glidein.
        entry_name (str): Name of the entry.
        client_name (str): Client name.
        client_int_name (str): Internal client name.
        client_int_req (str): Request name.
        glidein_attrs (dict, optional): Glidein attributes to publish. Defaults to {}.
        client_params (dict, optional): Client parameters to publish. Defaults to {}.
        client_monitors (dict, optional): Monitoring data to publish. Defaults to {}.
        limits_triggered (dict, optional): Triggered limits data. Defaults to {}.
        do_append (bool, optional): If True, append to the file; otherwise, overwrite. Defaults to False.
    """
    global factoryConfig
    global advertiseGFCCounter

    if do_append:
        open_type = "a"
    else:
        open_type = "w"

    try:
        with open(fname, open_type) as fd:
            limits = ("IdleGlideinsPerEntry", "HeldGlideinsPerEntry", "TotalGlideinsPerEntry")
            for limit in limits:
                if limit in limits_triggered:
                    fd.write(
                        '%sStatus_GlideFactoryLimit%s = "%s"\n'
                        % (factoryConfig.glidein_monitor_prefix, limit, limits_triggered[limit])
                    )

            all_frontends = limits_triggered.get("all_frontends")
            for fe_sec_class in all_frontends:
                sec_class_limits = ("IdlePerClass_%s" % fe_sec_class, "TotalPerClass_%s" % fe_sec_class)
                for limit in sec_class_limits:
                    if limit in limits_triggered:
                        fd.write(
                            '%sStatus_GlideFactoryLimit%s = "%s"\n'
                            % (factoryConfig.glidein_monitor_prefix, limit, limits_triggered[limit])
                        )
            fd.write('MyType = "%s"\n' % factoryConfig.factoryclient_id)
            fd.write('GlideinMyType = "%s"\n' % factoryConfig.factoryclient_id)
            fd.write('GlideinWMSVersion = "%s"\n' % factoryConfig.glideinwms_version)
            fd.write('Name = "%s"\n' % client_name)
            fd.write(f'ReqGlidein = "{entry_name}@{glidein_name}@{factory_name}"\n')
            fd.write('ReqFactoryName = "%s"\n' % factory_name)
            fd.write('ReqGlideinName = "%s"\n' % glidein_name)
            fd.write('ReqEntryName = "%s"\n' % entry_name)
            fd.write('ReqClientName = "%s"\n' % client_int_name)
            fd.write('ReqClientReqName = "%s"\n' % client_int_req)
            # fd.write('DaemonStartTime = %li\n'%start_time)
            advertiseGFCCounter[client_name] = advertiseGFCCounter.get(client_name, -1) + 1
            fd.write("UpdateSequenceNumber = %i\n" % advertiseGFCCounter[client_name])

            # write out both the attributes, params and monitors
            for prefix, data in (
                (factoryConfig.glidein_attr_prefix, glidein_attrs),
                (factoryConfig.glidein_param_prefix, client_params),
                (factoryConfig.glidein_monitor_prefix, client_monitors),
            ):
                for attr in list(data.keys()):
                    el = data[attr]
                    if isinstance(el, int):
                        # don't quote ints
                        fd.write(f"{prefix}{attr} = {el}\n")
                    else:
                        escaped_el = str(el).replace('"', '\\"')
                        fd.write(f'{prefix}{attr} = "{escaped_el}"\n')
            # add a final empty line... useful when appending
            fd.write("\n")
    except Exception:
        # remove file in case of problems
        if os.path.exists(fname):
            os.remove(fname)
        raise


# Given a file, advertise
# Can throw a CondorExe/ExeError exception
def advertiseGlideinClientMonitoringFromFile(fname, remove_file=True, is_multi=False, factory_collector=DEFAULT_VAL):
    """Advertise glidefactoryclient classads from a file.

    Args:
        fname (str): Filename containing the classads.
        remove_file (bool, optional): If True, remove the file after advertisement. Defaults to True.
        is_multi (bool, optional): True if advertising a multi-classad; otherwise, False. Defaults to False.
        factory_collector (str or None): Collector to use; if DEFAULT_VAL, uses global config.

    Raises:
        CondorExe or ExeError: if advertising fails.
    """
    if os.path.exists(fname):
        try:
            logSupport.log.info("Advertising glidefactoryclient classads")
            exe_condor_advertise(fname, "UPDATE_LICENSE_AD", is_multi=is_multi, factory_collector=factory_collector)
        except Exception:
            logSupport.log.warning("Advertising glidefactoryclient classads failed")
            logSupport.log.exception("Advertising glidefactoryclient classads failed: ")
        if remove_file:
            os.remove(fname)
    else:
        logSupport.log.warning(
            "glidefactoryclient classad file %s does not exist. Check if frontends are allowed to submit to entry"
            % fname
        )


def advertiseGlideinFromFile(fname, remove_file=True, is_multi=False, factory_collector=DEFAULT_VAL):
    """Advertise glidefactory classads from a file.

    Args:
        fname (str): Filename containing the classads.
        remove_file (bool, optional): If True, remove the file after advertisement. Defaults to True.
        is_multi (bool, optional): True if advertising a multi-classad; otherwise, False. Defaults to False.
        factory_collector (str or None): Collector to use; if DEFAULT_VAL, uses global config.
    """
    if os.path.exists(fname):
        try:
            logSupport.log.info("Advertising glidefactory classads")
            exe_condor_advertise(fname, "UPDATE_AD_GENERIC", is_multi=is_multi, factory_collector=factory_collector)
        except Exception:
            logSupport.log.warning("Advertising glidefactory classads failed")
            logSupport.log.exception("Advertising glidefactory classads failed: ")
        if remove_file:
            os.remove(fname)
    else:
        logSupport.log.warning(
            "glidefactory classad file %s does not exist. Check if you have at least one entry enabled" % fname
        )


# End INTERNAL
###########################################


# remove classads from Collector
def deadvertiseAllGlideinClientMonitoring(factory_name, glidein_name, entry_name, factory_collector=DEFAULT_VAL):
    """De-advertise monitoring classads for the given entry.

    Args:
        factory_name (str): The name of the factory.
        glidein_name (str): The name of the glidein.
        entry_name (str): The name of the entry.
        factory_collector (str or None): Collector to use; if DEFAULT_VAL, uses global config.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gfc")
    # TODO: use tempfile
    try:
        with open(tmpnam, "w") as fd:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % factoryConfig.factoryclient_id)
            fd.write(
                'Requirements = (ReqGlidein == "%s@%s@%s")&&(GlideinMyType == "%s")\n'
                % (entry_name, glidein_name, factory_name, factoryConfig.factoryclient_id)
            )

        exe_condor_advertise(tmpnam, "INVALIDATE_LICENSE_ADS", factory_collector=factory_collector)
    finally:
        _remove_if_there(tmpnam)


def deadvertiseFactoryClientMonitoring(factory_name, glidein_name, factory_collector=DEFAULT_VAL):
    """De-advertise all monitoring classads for this Factory.

    Args:
        factory_name (str): The name of the factory.
        glidein_name (str): The name of the glidein.
        factory_collector (str or None): Collector to use; if DEFAULT_VAL, uses global config.
    """
    tmpnam = classadSupport.generate_classad_filename(prefix="gfi_de_gfc")
    # TODO: use tempfile
    try:
        with open(tmpnam, "w") as fd:
            fd.write('MyType = "Query"\n')
            fd.write('TargetType = "%s"\n' % factoryConfig.factoryclient_id)
            fd.write(
                'Requirements = (ReqFactoryName=?="%s")&&(ReqGlideinName=?="%s")&&(GlideinMyType == "%s")'
                % (factory_name, glidein_name, factoryConfig.factoryclient_id)
            )

        exe_condor_advertise(tmpnam, "INVALIDATE_LICENSE_ADS", factory_collector=factory_collector)
    finally:
        _remove_if_there(tmpnam)


############################################################
#
# I N T E R N A L - Do not use
#
############################################################


def _remove_if_there(fname):
    """Remove the specified file, ignoring errors (e.g. file not there).

    Args:
        fname (str): The filename to remove.
    """
    try:
        os.remove(fname)
    except OSError:
        # Do the possible to remove the file if there
        pass


# serialize access to the Collector across all the processes
# these is a single Collector anyhow
def exe_condor_advertise(fname, command, is_multi=False, factory_collector=None):
    """Execute condorAdvertise on the given file.

    Args:
        fname (str): The filename containing the classad.
        command (str): The advertisement command.
        is_multi (bool, optional): True if advertising a multi-classad; otherwise, False. Defaults to False.
        factory_collector (str or None): The collector to use; if DEFAULT_VAL, uses global config.

    Returns:
        object: The result of the condorAdvertise command.
    """
    global factoryConfig

    if factory_collector == DEFAULT_VAL:
        factory_collector = factoryConfig.factory_collector

    lock_fname = os.path.join(factoryConfig.lock_dir, "gfi_advertise.lock")
    if not os.path.exists(lock_fname):  # create a lock file if needed
        try:
            fd = open(lock_fname, "w")
            fd.close()
        except Exception:
            # could be a race condition
            pass

    with open(lock_fname, "r+") as fd:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            ret = condorManager.condorAdvertise(
                fname, command, factoryConfig.advertise_use_tcp, is_multi, factory_collector
            )
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)

    return ret
