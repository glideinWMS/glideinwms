#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   This module implements classes to query the condor daemons
#   and manipulate the results
#   Please notice that it also converts \" into "
#
# Author:
#   Igor Sfiligoi (Aug 30th 2006)
#

import os
import sys
import string
import copy
import socket
import xml.parsers.expat
import condorExe
import condorSecurity

USE_HTCONDOR_PYTHON_BINDINGS = False
try:
    # NOTE:
    # import htcondor tries to look for CONDOR_CONFIG in the usual search path
    # If it cannot be found, it will print annoying error message which
    # neither goes to stdout nor stderr. It was not clear how to mask this
    # message so we may have to live with it till then
    # In case of non default locations of CONDOR_CONFIG, frontend will always
    # set the CONDOR_CONFIG appropriately before every command. Since import
    # happens before frontend can do anything, htcondor module is initialized
    # without the knowledge of CONDOR_CONFIG. This mandates that we do a
    # htcondor.reload_config() everytime to use the bindings.
    import htcondor
    import classad
    USE_HTCONDOR_PYTHON_BINDINGS = True
except:
    #TODO Maybe we should print a message here? Even though I don't know if
    #logSupport has been initialized. But I'd try to put it log.debug
    pass


#
# Configuration
#

# Set path to condor binaries
def set_path(new_condor_bin_path):
    global condor_bin_path
    condor_bin_path = new_condor_bin_path


#
# Exceptions
#

class QueryError(RuntimeError):
    """
    Thrown when there are exceptions using htcondor python bindings or commands
    """
    def __init__(self, err_str):
        RuntimeError.__init__(self, err_str)


class PBError(RuntimeError):
    """
    Thrown when there are exceptions using htcondor python bindings
    """
    def __init__(self, err_str):
        RuntimeError.__init__(self, err_str)


#
# Caching classes
#

class NoneScheddCache:
    """
    Dummy caching class, when you don't want caching.
    Used as base class below, too
    """

    def getScheddId(self, schedd_name, pool_name):
        """
        Given the schedd name and pool name, return a tuple (ScheddId, dict)

        @param schedd_name: Name of the schedd
        @type schedd_name: string

        @param pool_name: Name of the pool
        @type pool_name: string

        @return: tuple (schedd string, LOCAL_DIR)
        """
        return (self.iGetCmdScheddStr(schedd_name), {})

    def iGetCmdScheddStr(self, schedd_name):
        if schedd_name is None:
            schedd_str = ""
        else:
            schedd_str = "-name %s " % schedd_name

        return schedd_str


class LocalScheddCache(NoneScheddCache):
    """
    Schedd caching class
    The schedd can be found either through -name attr or through the
    local disk lookup. Remember which one to use.
    """

    def __init__(self):
        self.enabled = True
        # dict of (schedd_name,pool_name)=>(cms arg schedd string,env)
        self.cache = {}

        self.my_ips = socket.gethostbyname_ex(socket.gethostname())[2]
        try:
            self.my_ips += socket.gethostbyname_ex('localhost')[2]
        except socket.gaierror as e:
            pass  # localhost not defined, ignore

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

    def getScheddId(self, schedd_name, pool_name):
        """
        Given the schedd name and pool name, get a tuple containing
        (ScheddId, dict)

        @param schedd_name: Name of the schedd
        @type schedd_name: string

        @param pool_name: Name of the pool
        @type pool_name: string

        @return: tuple (schedd string, env)
        """
        if schedd_name is None:  # special case, do not cache
            return ("", {})

        if self.enabled:
            k = (schedd_name, pool_name)
            if k not in self.cache:  # not in cache, discover it
                env = self.iGetEnv(schedd_name, pool_name)
                if env is None:
                    self.cache[k] = (self.iGetCmdScheddStr(schedd_name), {})
                else:
                    self.cache[k] = ("", env)
            return self.cache[k]
        else:
            # Not enabled, just return the str
            return (self.iGetCmdScheddStr(schedd_name), {})

    #
    # PRIVATE
    #

    # return None if not found
    # Can raise exceptions
    def iGetEnv(self, schedd_name, pool_name):
        cs = CondorStatus('schedd', pool_name)
        data = cs.fetch(constraint='Name=?="%s"'%schedd_name,
                        format_list=[('ScheddIpAddr', 's'),
                                     ('SPOOL_DIR_STRING', 's'),
                                     ('LOCAL_DIR_STRING', 's')])
        if schedd_name not in data:
            raise RuntimeError, "Schedd '%s' not found"%schedd_name

        el = data[schedd_name]
        if 'SPOOL_DIR_STRING' not in el and 'LOCAL_DIR_STRING' not in el:
            # not advertising, cannot use disk optimization
            return None
        if 'ScheddIpAddr' not in el:
            # This should never happen
            raise RuntimeError, "Schedd '%s' is not advertising ScheddIpAddr"%schedd_name

        schedd_ip = el['ScheddIpAddr'][1:].split(':')[0]
        if schedd_ip in self.my_ips:  # seems local, go for the dir
            l=el.get('SPOOL_DIR_STRING', el.get('LOCAL_DIR_STRING'))
            if os.path.isdir(l):  # making sure the directory exists
                if 'SPOOL_DIR_STRING' in el:
                    return {'_CONDOR_SPOOL': '%s' %l }
                else:  # LOCAL_DIR_STRING, assuming spool is LOCAL_DIR_STRING/spool
                    if os.path.isdir('%s/spool' %l):
                        return {'_CONDOR_SPOOL': '%s/spool' %l }
            else:
                # dir does not exist, not relevant, revert to standard behaviour
                return None
        else:
            # not local
            return None

# default global object
local_schedd_cache = LocalScheddCache()


def condorq_attrs(q_constraint, attribute_list):
    """
    Retrieves a list of a single item from the all the factory queues.
    """
    attr_str = ""
    for attr in attribute_list:
        attr_str += " -attr %s" % attr

    xml_data = condorExe.exe_cmd("condor_q", "-g -l %s -xml -constraint '%s'" % (attr_str, q_constraint))

    classads_xml = []
    tmp_list = []
    for line in xml_data:
        # look for the xml header
        if line[:5] == "<?xml":
            if len(tmp_list) > 0:
                classads_xml.append(tmp_list)
            tmp_list = []
        tmp_list.append(line)

    q_proxy_list = []
    for ad_xml in classads_xml:
        cred_list = xml2list(ad_xml)
        q_proxy_list.extend(cred_list)

    return q_proxy_list


#
# Condor monitoring classes
#

class AbstractQuery:
    """
    Pure virtual class to have a minimum set of methods defined
    """

    def fetch(self, constraint=None, format_list=None):
        """
        Fetch the classad attributes specified in the format_list
        matching the constraint

        @rtype: dict
        @return: Dict containing classad attributes and values
        """
        raise NotImplementedError, "Fetch not implemented"

    def load(self, constraint=None, format_list=None):
        """
        Fetch the data and store it in self.stored_data
        """
        raise NotImplementedError, "Load not implemented"

    def fetchStored(self, constraint_func=None):
        """
        @param constraint_func: A boolean function, with only one argument
                                (data el). If None, return all the data.
        @type constraint_func: Boolean function

        @rtype: dict
        @return: Same as fetch(), but limited to constraint_func(el)==True
        """
        raise NotImplementedError, "fetchStored not implemented"


class StoredQuery(AbstractQuery):
    """
    Virtual class that implements fetchStored
    """
    stored_data = {}

    def fetchStored(self, constraint_func=None):
        """
        @param constraint_func: A boolean function, with only one argument
                                (data el). If None, return all the data.
        @type constraint_func: Boolean function

        @rtype: dict
        @return: Same as fetch(), but limited to constraint_func(el)==True
        """
        return applyConstraint(self.stored_data, constraint_func)


class CondorQEdit:
    """
    Fully implemented class that executes condorq_edit commands. Only provides a method to do bulk
    updates of jobs using transaction-based API and the condor python bindings. Cannot be used without
    python bindings
    """

    def __init__(self, pool_name=None, schedd_name=None):
        """ Raises QueryError in case python bindings are not available
        """
        self.pool_name=pool_name
        self.schedd_name=schedd_name
        if not USE_HTCONDOR_PYTHON_BINDINGS:
            raise QueryError("QEdit class only implemented with python bindings")

    def executeAll(self, joblist=None, attributes=None, values=None):
        """ Given equal sized lists of job ids, attributes and values,
            executes in one large transaction a single qedit for each job.
        """
        joblist = joblist or []
        attributes = attributes or []
        values = values or []
        if not (len(joblist) == len(attributes) == len(values)):
            raise QueryError("Arguments to QEdit.executeAll should have the same length")
        try:
            htcondor.reload_config()
            if self.pool_name:
                collector = htcondor.Collector(str(self.pool_name))
            else:
                collector = htcondor.Collector()

            if self.schedd_name:
                schedd_ad = collector.locate(htcondor.DaemonTypes.Schedd,
                                             self.schedd_name)
                schedd = htcondor.Schedd(schedd_ad)
            else:
                schedd = htcondor.Schedd()
            with schedd.transaction() as _:
                for jobid, attr, val in zip(joblist, attributes, values):
                    schedd.edit([jobid], attr, classad.quote(val))
        except Exception as ex:
            s = 'default'
            if self.schedd_name is not None:
                s = self.schedd_name
            p = 'default'
            if self.pool_name is not None:
                p = self.pool_name
            err_str = 'Error querying schedd %s in pool %s using python bindings: %s' % (s, p, ex)
            raise QueryError(err_str)


#
# format_list is a list of
#  (attr_name, attr_type)
# where attr_type is one of
#  "s" - string
#  "i" - integer
#  "r" - real (float)
#  "b" - bool
#
#
# security_obj, if defined, should be a child of condorSecurity.ProtoRequest
class CondorQuery(StoredQuery):
    """
    Fully implemented class that executes condor commands
    """

    def __init__(self, exe_name, resource_str, group_attribute,
                 pool_name=None, security_obj=None, env={}):
        self.exe_name=exe_name
        self.env=env
        self.resource_str=resource_str
        self.group_attribute=group_attribute
        self.pool_name=pool_name
        if pool_name is None:
            self.pool_str=""
        else:
            self.pool_str = "-pool %s" % pool_name

        if security_obj is not None:
            if security_obj.has_saved_state():
                raise RuntimeError, "Cannot use a security object which has saved state."
            self.security_obj=copy.deepcopy(security_obj)
        else:
            self.security_obj=condorSecurity.ProtoRequest()

    def require_integrity(self, requested_integrity):
        """
        Set client integerity settings to use for condor commands
        """
        if requested_integrity is None:
            condor_val = None
        elif requested_integrity:
            condor_val = "REQUIRED"
        else:
            # Not required, set OPTIONAL if the other side requires it
            condor_val='OPTIONAL'
        self.security_obj.set('CLIENT', 'INTEGRITY', condor_val)

    def get_requested_integrity(self):
        """
        Get the current integrity settings

        @return: None->None; REQUIRED->True; OPTIONAL->False
        """
        condor_val = self.security_obj.get('CLIENT', 'INTEGRITY')
        if condor_val is None:
            return None
        return (condor_val == 'REQUIRED')

    def require_encryption(self, requested_encryption):
        """
        Set client encryption settings to use for condor commands
        """
        if requested_encryption is None:
            condor_val = None
        elif requested_encryption:
            condor_val = "REQUIRED"
        else:
            # Not required, set OPTIONAL if the other side requires it
            condor_val = 'OPTIONAL'
        self.security_obj.set('CLIENT', 'ENCRYPTION', condor_val)

    def get_requested_encryption(self):
        """
        Get the current encryption settings

        @return: None->None; REQUIRED->True; OPTIONAL->False
        """

        condor_val = self.security_obj.get('CLIENT', 'ENCRYPTION')
        if condor_val is None:
            return None
        return (condor_val == 'REQUIRED')

    def fetch(self, constraint=None, format_list=None):
        """
        Return the results obtained using HTCondor commands or python bindings
        """
        try:
            if USE_HTCONDOR_PYTHON_BINDINGS:
                return self.fetch_using_bindings(constraint=constraint,
                                                 format_list=format_list)
            else:
                return self.fetch_using_exe(constraint=constraint,
                                            format_list=format_list)
        except Exception as ex:
            err_str = 'Error executing htcondor query with constraint %s and format_list %s: %s' % (constraint, format_list, ex)
            raise QueryError(err_str), None, sys.exc_info()[2]

    def fetch_using_exe(self, constraint=None, format_list=None):
        """
        Return the results obtained from executing the HTCondor query command

        @param constraint: Constraints to be applied to the query
        @type constraint: string

        @param format_list: Classad attr & type. [(attr1, 'i'), ('attr2', 's')]
        @type format_list: list

        @return: Dict containing the results
        @rtype: dict
        """

        if constraint is None:
            constraint_str = ""
        else:
            constraint_str = "-constraint '%s'"%constraint

        full_xml=(format_list is None)
        if format_list is not None:
            format_arr = []
            for format_el in format_list:
                attr_name, attr_type = format_el
                attr_format = {'s': '%s', 'i': '%i', 'r': '%f', 'b': '%i'}[attr_type]
                format_arr.append('-format "%s" "%s"' % (attr_format, attr_name))
            format_str = string.join(format_arr, " ")

        # set environment for security settings
        self.security_obj.save_state()
        try:
            self.security_obj.enforce_requests()

            if full_xml:
                xml_data = condorExe.exe_cmd(self.exe_name, "%s -xml %s %s" %
                                             (self.resource_str, self.pool_str, constraint_str), env=self.env)
            else:
                xml_data = condorExe.exe_cmd(self.exe_name, "%s %s -xml %s %s" %
                                             (self.resource_str, format_str, self.pool_str, constraint_str), env=self.env)
        finally:
            # restore old security context
            self.security_obj.restore_state()

        list_data = xml2list(xml_data)
        del xml_data
        dict_data = list2dict(list_data, self.group_attribute)
        return dict_data

    def fetch_using_bindings(self, constraint=None, format_list=None):
        """
        Fetch the results using htcondor-python bindings
        """
        raise NotImplementedError, "fetch_using_bindings() not implemented"

    def load(self, constraint=None, format_list=None):
        """
        Fetch the results and cache it in self.stored_data
        """
        self.stored_data = self.fetch(constraint, format_list)

    def __repr__(self):
        output = "%s:\n" % self.__class__.__name__
        output += "exe_name = %s\n" % str(self.exe_name)
        output += "env = %s\n" % str(self.env)
        output += "resource_str = %s\n" % str(self.resource_str)
        output += "group_attribute = %s\n" % str(self.group_attribute)
        output += "pool_name = %s\n" % str(self.pool_name)
        output += "pool_str = %s\n" % str(self.pool_str)
        output += "security_obj = %s\n" % str(self.security_obj)
        output += "used_python_bindings = %s\n" % USE_HTCONDOR_PYTHON_BINDINGS
        output += "stored_data = %s" % str(self.stored_data)
        return output


class CondorQ(CondorQuery):
    """
    Class to implement condor_q. Uses htcondor-python bindings if possible.
    """

    def __init__(self, schedd_name=None, pool_name=None, security_obj=None,
                 schedd_lookup_cache=local_schedd_cache):
        self.schedd_name = schedd_name

        if schedd_lookup_cache is None:
            schedd_lookup_cache = NoneScheddCache()

        schedd_str, env = schedd_lookup_cache.getScheddId(schedd_name,
                                                          pool_name)
        CondorQuery.__init__(self, "condor_q", schedd_str,
                             ["ClusterId", "ProcId"],
                             pool_name, security_obj, env)

    def fetch(self, constraint=None, format_list=None):
        if format_list is not None:
            # If format_list, make sure ClusterId and ProcId are present
            format_list = complete_format_list(
                format_list, [("ClusterId", 'i'), ("ProcId", 'i')])
        return CondorQuery.fetch(self, constraint=constraint,
                                 format_list=format_list)

    def fetch_using_bindings(self, constraint=None, format_list=None):
        """
        Fetch the results using htcondor-python bindings
        """

        results_dict = {}  # defined here in case of exception
        constraint = bindings_friendly_constraint(constraint)
        attrs = bindings_friendly_attrs(format_list)

        self.security_obj.save_state()
        try:
            self.security_obj.enforce_requests()
            htcondor.reload_config()
            if self.pool_name:
                collector = htcondor.Collector(str(self.pool_name))
            else:
                collector = htcondor.Collector()

            if self.schedd_name is None:
                schedd = htcondor.Schedd()
            else:
                schedd_ad = collector.locate(htcondor.DaemonTypes.Schedd,
                                             self.schedd_name)
                schedd = htcondor.Schedd(schedd_ad)
            results = schedd.query(constraint, attrs)
            results_dict = list2dict(results, self.group_attribute)
        except Exception as ex:
            s = 'default'
            if self.schedd_name is not None:
                s = self.schedd_name
            p = 'default'
            if self.pool_name is not None:
                p = self.pool_name
            err_str = 'Error querying schedd %s in pool %s using python bindings: %s' % (s, p, ex)
            raise PBError(err_str), None, sys.exc_info()[2]
        finally:
            self.security_obj.restore_state()

        return results_dict


class CondorStatus(CondorQuery):
    """
    Class to implement condor_status. Uses htcondor-python bindings if possible.
    """

    def __init__(self, subsystem_name=None, pool_name=None, security_obj=None):
        if subsystem_name is None:
            subsystem_str = ""
        else:
            subsystem_str = "-%s" % subsystem_name
        CondorQuery.__init__(self, "condor_status", subsystem_str,
                             "Name", pool_name, security_obj, {})

    def fetch(self, constraint=None, format_list=None):
        if format_list is not None:
            # If format_list, make sure Name is present
            format_list = complete_format_list(format_list, [("Name", 's')])
        return CondorQuery.fetch(self, constraint=constraint,
                                 format_list=format_list)

    def fetch_using_bindings(self, constraint=None, format_list=None):
        """
        Fetch the results using htcondor-python bindings
        """
        results_dict = {}  # defined here in case of exception
        constraint = bindings_friendly_constraint(constraint)
        attrs = bindings_friendly_attrs(format_list)

        adtype = resource_str_to_py_adtype(self.resource_str)
        self.security_obj.save_state()
        try:
            self.security_obj.enforce_requests()
            htcondor.reload_config()
            if self.pool_name:
                collector = htcondor.Collector(str(self.pool_name))
            else:
                collector = htcondor.Collector()

            results = collector.query(adtype, constraint, attrs)
            results_dict = list2dict(results, self.group_attribute)
        except Exception as ex:
            p = 'default'
            if self.pool_name is not None:
                p = self.pool_name
            err_str = 'Error querying pool %s using python bindings: %s' % (p, ex)
            raise PBError(err_str), None, sys.exc_info()[2]
        finally:
            self.security_obj.restore_state()

        return results_dict


#
# Subquery classes
#

class BaseSubQuery(StoredQuery):
    """
    Virtual class that implements fetch for StoredQuery()
    """

    def __init__(self, query, subquery_func):
        self.query = query
        self.subquery_func = subquery_func

    def fetch(self, constraint=None):
        indata = self.query.fetch(constraint)
        return self.subquery_func(self, indata)

    #
    # NOTE: You need to call load on the SubQuery object to use fetchStored
    #       and had query.load issued before
    #
    def load(self, constraint=None):
        indata = self.query.fetchStored(constraint)
        self.stored_data = self.subquery_func(indata)


class SubQuery(BaseSubQuery):
    """
    Fully usable subquery class, typically used on CondorQ() or CondorStatus()
    """

    def __init__(self, query, constraint_func=None):
        BaseSubQuery.__init__(self, query,
                              lambda d: applyConstraint(d, constraint_func))

    def __repr__(self):
        output = "%s:\n" % self.__class__.__name__
        # output += "client_name = %s\n" % str(self.client_name)
        # output += "entry_name = %s\n" % str(self.entry_name)
        # output += "factory_name = %s\n" % str(self.factory_name)
        # output += "glidein_name = %s\n" % str(self.glidein_name)
        # output += "schedd_name = %s\n" % str(self.schedd_name)
        output += "stored_data = %s" % str(self.stored_data)
        return output


class Group(BaseSubQuery):
    """
    Sub Query class with grouping functionality
    """

    def __init__(self, query, group_key_func, group_data_func):
        """
        group_key_func  - Key extraction function
                          One argument: classad dictionary
                          Returns: value of the group key
        group_data_func - Group extraction function
                          One argument: list of classad dictionaries
                          Returns: a summary classad dictionary
        """
        BaseSubQuery.__init__(
            self, query, lambda d: doGroup(d, group_key_func, group_data_func))


class Summarize:
    """
    Summarizing classes
    """

    #  hash_func   - Hashing function
    #                One argument: classad dictionary
    #                Returns: hash value
    #                          if None, will not be counted
    #                          if a list, all elements will be used
    def __init__(self, query, hash_func=lambda x: 1):
        self.query = query
        self.hash_func = hash_func

    # Parameters:
    #    constraint - string to be passed to query.fetch()
    #    hash_func  - if !=None, use this instead of the main one
    # Returns a dictionary of hash values
    #    Elements are counts (or more dictionaries if hash returns lists)
    def count(self, constraint=None, hash_func=None):
        data = self.query.fetch(constraint)
        return fetch2count(data, self.getHash(hash_func))

    # Use data pre-stored in query
    # Same output as count
    def countStored(self, constraint_func=None, hash_func=None):
        data = self.query.fetchStored(constraint_func)
        return fetch2count(data, self.getHash(hash_func))

    # Parameters, same as count
    # Returns a dictionary of hash values
    #    Elements are lists of keys (or more dictionaries if hash returns lists)
    def list(self, constraint=None, hash_func=None):
        data = self.query.fetch(constraint)
        return fetch2list(data, self.getHash(hash_func))

    # Use data pre-stored in query
    # Same output as list
    def listStored(self, constraint_func=None, hash_func=None):
        data = self.query.fetchStored(constraint_func)
        return fetch2list(data, self.getHash(hash_func))

    ### Internal
    def getHash(self, hash_func):
        if hash_func is None:
            return self.hash_func
        else:
            return hash_func


############################################################
#
# P R I V A T E, do not use
#
############################################################

# check that req_format_els are present in in_format_list, and if not add them
# return a new format_list
def complete_format_list(in_format_list, req_format_els):
    out_format_list = in_format_list[0:]
    for req_format_el in req_format_els:
        found = False
        for format_el in in_format_list:
            if format_el[0] == req_format_el[0]:
                found = True
                break
        if not found:
            out_format_list.append(req_format_el)
    return out_format_list


#
# Convert Condor XML to list
#
# For Example:
#
#<?xml version="1.0"?>
#<!DOCTYPE classads SYSTEM "classads.dtd">
#<classads>
#<c>
#    <a n="MyType"><s>Job</s></a>
#    <a n="TargetType"><s>Machine</s></a>
#    <a n="AutoClusterId"><i>0</i></a>
#    <a n="ExitBySignal"><b v="f"/></a>
#    <a n="TransferOutputRemaps"><un/></a>
#    <a n="WhenToTransferOutput"><s>ON_EXIT</s></a>
#</c>
#<c>
#    <a n="MyType"><s>Job</s></a>
#    <a n="TargetType"><s>Machine</s></a>
#    <a n="AutoClusterId"><i>0</i></a>
#    <a n="OnExitRemove"><b v="t"/></a>
#    <a n="x509userproxysubject"><s>/DC=gov/DC=fnal/O=Fermilab/OU=People/CN=Igor Sfiligoi/UID=sfiligoi</s></a>
#</c>
#</classads>
#

# 3 xml2list XML handler functions
def xml2list_start_element(name, attrs):
    global xml2list_data, xml2list_inclassad, xml2list_inattr, xml2list_intype
    if name == "c":
        xml2list_inclassad = {}
    elif name == "a":
        xml2list_inattr = {"name": attrs["n"], "val": ""}
        xml2list_intype = "s"
    elif name == "i":
        xml2list_intype = "i"
    elif name == "r":
        xml2list_intype = "r"
    elif name == "b":
        xml2list_intype = "b"
        if 'v' in attrs:
            xml2list_inattr["val"] = (attrs["v"] in ('T', 't', '1'))
        else:
            # extended syntax... value in text area
            xml2list_inattr["val"] = None
    elif name == "un":
        xml2list_intype = "un"
        xml2list_inattr["val"] = None
    elif name in ("s", "e"):
        pass # nothing to do
    elif name == "classads":
        pass # top element, nothing to do
    else:
        raise TypeError, "Unsupported type: %s" % name

def xml2list_end_element(name):
    global xml2list_data, xml2list_inclassad, xml2list_inattr, xml2list_intype
    if name == "c":
        xml2list_data.append(xml2list_inclassad)
        xml2list_inclassad = None
    elif name == "a":
        xml2list_inclassad[xml2list_inattr["name"]] = xml2list_inattr["val"]
        xml2list_inattr = None
    elif name in ("i", "b", "un", "r"):
        xml2list_intype = "s"
    elif name in ("s", "e"):
        pass # nothing to do
    elif name == "classads":
        pass # top element, nothing to do
    else:
        raise TypeError, "Unexpected type: %s" % name

def xml2list_char_data(data):
    global xml2list_data, xml2list_inclassad, xml2list_inattr, xml2list_intype
    if xml2list_inattr is None:
        # only process when in attribute
        return

    if xml2list_intype == "i":
        xml2list_inattr["val"] = int(data)
    elif xml2list_intype == "r":
        xml2list_inattr["val"] = float(data)
    elif xml2list_intype == "b":
        if xml2list_inattr["val"] is not None:
            #nothing to do, value was in attribute
            pass
        else:
            xml2list_inattr["val"] = (data[0] in ('T', 't', '1'))
    elif xml2list_intype == "un":
        #nothing to do, value was in attribute
        pass
    else:
        unescaped_data = string.replace(data, '\\"', '"')
        xml2list_inattr["val"] += unescaped_data

def xml2list(xml_data):
    global xml2list_data, xml2list_inclassad, xml2list_inattr, xml2list_intype

    xml2list_data = []
    xml2list_inclassad = None
    xml2list_inattr = None
    xml2list_intype = None

    p = xml.parsers.expat.ParserCreate()
    p.StartElementHandler = xml2list_start_element
    p.EndElementHandler = xml2list_end_element
    p.CharacterDataHandler = xml2list_char_data

    found_xml = -1
    for line in range(len(xml_data)):
        # look for the xml header
        if xml_data[line][:5] == "<?xml":
            found_xml = line
            break

    if found_xml >= 0:
        try:
            p.Parse(string.join(xml_data[found_xml:]), 1)
        except TypeError as e:
            raise RuntimeError, "Failed to parse XML data, TypeError: %s" % e
        except:
            raise RuntimeError, "Failed to parse XML data, generic error"
    # else no xml, so return an empty list

    return xml2list_data

def list2dict(list_data, attr_name):
    """
    Convert a list to a dictionary and group the results based on
    attributes specified by attr_name
    """

    if type(attr_name) in (type([]), type((1, 2))):
        attr_list = attr_name
    else:
        attr_list = [attr_name]

    dict_data = {}
    for list_el in list_data:
        if type(attr_name) in (type([]), type((1, 2))):
            dict_name = []
            for an in attr_name:
                if an in list_el:
                    dict_name.append(list_el[an])
                else:
                    # Try lower cases
                    for k in list_el:
                        if an.lower()==k.lower():
                            dict_name.append(list_el[k])
                            break
            dict_name=tuple(dict_name)
        else:
            dict_name = list_el[attr_name]
        # dict_el will have all the elements but those in attr_list
        dict_el = {}
        for a in list_el:
            if not (a in attr_list):
                try:
                    if (USE_HTCONDOR_PYTHON_BINDINGS == True):
                        if (list_el[a].__class__.__name__ == 'ExprTree'):
                            # Try to evaluate the condor expr and use its value
                            # If cannot be evaluated, keep the expr as is
                            a_value = list_el[a].eval()
                            if '%s'%a_value != 'Undefined':
                                # Cannot use classad.Value.Undefined for
                                # for comparison as it gets cast to int
                                dict_el[a] = a_value
                        elif str(list_el[a]) != 'Undefined':
                            # No need for Undefined check to see if
                            # attribute exists in the fetched classad
                            dict_el[a] = list_el[a]
                    else:
                        dict_el[a] = list_el[a]
                except:
                    # Do not fail
                    pass

        dict_data[dict_name] = dict_el
    return dict_data


def applyConstraint(data, constraint_func):
    """
    Return a subset of data that satisfies constraint_function
    If constraint_func is None, return back entire data
    """

    if constraint_func is None:
        return data
    else:
        outdata = {}
        for key, val in data.iteritems():
            if constraint_func(val):
                outdata[key] = val
    return outdata


def doGroup(indata, group_key_func, group_data_func):
    """
    Group the indata based on the keys that satisfy group_key_func
    Return dict of groups that satisfy group_data_func
    """

    gdata = {}
    for k, inel in indata.iteritems():
        gkey = group_key_func(inel)
        if gkey in gdata:
            gdata[gkey].append(inel)
        else:
            gdata[gkey] = [inel]

    outdata = {}
    for k in gdata:
        outdata[k] = group_data_func(gdata[k])

    return outdata

#
# Inputs
#  data        - data from a fetch()
#  hash_func   - Hashing function
#                One argument: classad dictionary
#                Returns: hash value
#                          if None, will not be counted
#                          if a list, all elements will be used
#
# Returns a dictionary of hash values
#    Elements are counts (or more dictionaries if hash returns lists)
#
def fetch2count(data, hash_func):
    count = {}
    for k in data.keys():
        el = data[k]

        hid = hash_func(el)
        if hid is None:
            # hash tells us it does not want to count this
            continue

        # cel will point to the real counter
        cel = count

        # check if it is a list
        if (isinstance(hid, list)):
            # have to create structure inside count
            for h in hid[:-1]:
                if h not in cel:
                    cel[h] = {}
                cel = cel[h]
            hid = hid[-1]

        if hid in cel:
            count_el = cel[hid] + 1
        else:
            count_el = 1
        cel[hid] = count_el

    return count

#
# Inputs
#  data        - data from a fetch()
#  hash_func   - Hashing function
#                One argument: classad dictionary
#                Returns: hash value
#                          if None, will not be counted
#                          if a list, all elements will be used
#
# Returns a dictionary of hash values
#    Elements are lists of keys (or more dictionaries if hash returns lists)
#
def fetch2list(data, hash_func):
    return_list = {}
    for k in data.keys():
        el = data[k]

        hid = hash_func(el)
        if hid is None:
            # hash tells us it does not want to list this
            continue

        # lel will point to the real list
        lel = return_list

        # check if it is a list
        if (isinstance(hid, list)):
            # have to create structure inside list
            for h in hid[:-1]:
                if h not in lel:
                    lel[h] = {}
                lel = lel[h]
            hid = hid[-1]

        if hid in lel:
            list_el = lel[hid].append[k]
        else:
            list_el = [k]
        lel[hid] = list_el

    return return_list

#
# Recursivelly add two dictionaries
# Do it in place, using the first one
#
def addDict(base_dict, new_dict):
    for k in new_dict.keys():
        new_el = new_dict[k]
        if k not in base_dict:
            # nothing there?, just copy
            base_dict[k] = new_el
        else:
            if isinstance(new_el, dict):
                #another dictionary, recourse
                addDict(base_dict[k], new_el)
            else:
                base_dict[k] += new_el



################################################################################
# Functions to convert existing data type to their bindings friendly equivalent
################################################################################

def resource_str_to_py_adtype(resource_str):
    """
    Given the resource string return equivalent classad type
    """

    adtype = resource_str
    if USE_HTCONDOR_PYTHON_BINDINGS:
        adtypes = {
            '-any': htcondor.AdTypes.Any,
            '-collector': htcondor.AdTypes.Collector,
            '-generic': htcondor.AdTypes.Generic,
            '-grid': htcondor.AdTypes.Grid,
            '-had': htcondor.AdTypes.HAD,
            '-license': htcondor.AdTypes.License,
            '-master': htcondor.AdTypes.Master,
            '-negotiator': htcondor.AdTypes.Negotiator,
            '-schedd': htcondor.AdTypes.Schedd,
            '-startd': htcondor.AdTypes.Startd,
            '-submitter': htcondor.AdTypes.Submitter
        }
        # Default to startd ads, even if resource_str is empty
        adtype = adtypes.get(resource_str, htcondor.AdTypes.Startd)
    return adtype


def bindings_friendly_constraint(constraint):
    """
    Convert the constraint to format that can be used with python bindings
    """
    if constraint is None:
        return True
    return constraint


def bindings_friendly_attrs(format_list):
    """
    Convert the format_list into attrs that can be used with python bindings
    Python bindings should take care of the typing
    """
    if format_list is not None:
        return [f[0] for f in format_list]
    return []


################################################################################
# TODO: Following code is never used. Maybe we should yank it off in future
#       during code cleanup.
################################################################################

class SummarizeMulti:
    def __init__(self, queries, hash_func=lambda x:1):
        self.counts = []
        for query in queries:
            self.counts.append(self.count(query, hash_func))
        self.hash_func=hash_func

    # see Count for description
    def count(self, constraint=None, hash_func=None):
        out = {}

        for c in self.counts:
            data = c.count(constraint, hash_func)
            addDict(out, data)

        return out

    # see Count for description
    def countStored(self, constraint_func=None, hash_func=None):
        out = {}

        for c in self.counts:
            data = c.countStored(constraint_func, hash_func)
            addDict(out, data)

        return out


# condor_q, where we have only one ProcId x ClusterId
class CondorQLite(CondorQuery):
    def __init__(self,schedd_name=None,pool_name=None,security_obj=None,schedd_lookup_cache=local_schedd_cache):
        self.schedd_name=schedd_name

        if schedd_lookup_cache is None:
            schedd_lookup_cache=NoneScheddCache()

        schedd_str, env=schedd_lookup_cache.getScheddId(schedd_name, pool_name)

        CondorQuery.__init__(self, "condor_q", schedd_str, "ClusterId",
                             pool_name, security_obj, env)

    def fetch(self, constraint=None, format_list=None):
        if format_list is not None:
            # check that ClusterId is present, and if not add it
            format_list = complete_format_list(format_list, [("ClusterId", 'i')])
        return CondorQuery.fetch(self, constraint=constraint,
                                 format_list=format_list)
