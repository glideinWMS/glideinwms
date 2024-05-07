# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the Match Policy related class
"""

import os
import os.path

# import copy
import re

from glideinwms.lib.util import import_module

# import string
# import socket
# from collections import OrderedDict
from glideinwms.lib.xmlParse import OrderedDict

# from . import cWParams
# import pprint


class MatchPolicyLoadError(Exception):
    def __init__(self, file="", search_path=[]):
        self.file = file
        self.searchPath = search_path

    def __str__(self):
        err_str = ""
        if self.file == "":
            err_str = "No match policy file provided"
        else:
            err_str = f"Failed to load policy from the file {self.file} in the search path {self.searchPath}"
        return err_str


class MatchPolicyContentError(Exception):
    def __init__(self, file, attr, expected_type, actual_type):
        self.file = file
        self.attr = attr
        self.attrExpectedType = expected_type
        self.attrType = actual_type

    def __str__(self):
        return "{} in policy file {} should be of type {} and not {}".format(
            self.attr,
            self.file,
            self.attrExpectedType,
            self.attrType,
        )


class MatchPolicy:
    def __init__(self, file, search_path=[]):
        """
        Load match policy from the policy file

        @param file: Path to the python file
        @type file: string

        @param search_path: Search path to the python module to load
        @type search_path: list

        @rtype: MatchPolicy Object
        """

        if (file is not None) and (file != ""):
            self.file = file
            self.name = self.policyFileToPyModuleName()
            search_path.append(os.path.dirname(os.path.realpath(file)))
            self.searchPath = search_path
            try:
                self.pyObject = import_module(self.name, self.searchPath)
            except Exception:
                raise MatchPolicyLoadError(file=file, search_path=self.searchPath)
        else:
            raise MatchPolicyLoadError()

        match_attrs = self.loadMatchAttrs()
        self.factoryMatchAttrs = match_attrs.get("factory_match_attrs")
        self.jobMatchAttrs = match_attrs.get("job_match_attrs")

        # Assume TRUE as default for all expressions
        self.factoryQueryExpr = "TRUE"
        if "factory_query_expr" in dir(self.pyObject):
            self.factoryQueryExpr = self.pyObject.factory_query_expr

        self.jobQueryExpr = "TRUE"
        if "job_query_expr" in dir(self.pyObject):
            self.jobQueryExpr = self.pyObject.job_query_expr

        self.startExpr = "TRUE"
        if "start_expr" in dir(self.pyObject):
            self.startExpr = self.pyObject.start_expr

    def policyFileToPyModuleName(self):
        policy_fname = os.path.basename(self.file)
        policy_module_name = re.sub(".py$", "", policy_fname)
        return policy_module_name

    def loadMatchAttrs(self):
        """
        If given match_attr i.e. factory_match_attr or job_match_attr exits
        load it from the pyObject
        """

        # match_attrs = {}
        match_attrs = {"factory_match_attrs": {}, "job_match_attrs": {}}
        for ma_name in ("factory_match_attrs", "job_match_attrs"):
            if ma_name in dir(self.pyObject):
                ma_attr = getattr(self.pyObject, ma_name)
                # Check if the match_attr is of dict type
                # TODO: Also need to check that match_attr is of string/int/bool
                if isinstance(ma_attr, dict):
                    data = OrderedDict()
                    for k, v in ma_attr.items():
                        data[k] = OrderedDict(v)
                    match_attrs[ma_name] = data
                else:
                    # Raise error if match_attr is not of type dict
                    raise MatchPolicyContentError(self.file, ma_name, type(ma_attr).__name__, "dict")
        return match_attrs

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        contents = {
            "file": self.file,
            "name": self.name,
            "searchPath": "%s" % self.searchPath,
            "pyObject": "%s" % self.pyObject,
            "factoryMatchAttrs": "%s" % self.factoryMatchAttrs,
            "jobMatchAttrs": "%s" % self.jobMatchAttrs,
            "factoryQueryExpr": "%s" % self.factoryQueryExpr,
            "jobQueryExpr": "%s" % self.jobQueryExpr,
            "startExpr": "%s" % self.startExpr,
        }
        return "%s" % contents
