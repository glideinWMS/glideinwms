# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Frontend creation module
Classes and functions needed to handle dictionary files created out of the parameter object
"""

import os
import os.path
import shutil

from glideinwms.frontend.glideinFrontendLib import getGlideinCpusNum

# import re - not used
from glideinwms.lib import x509Support
from glideinwms.lib.util import str2bool

from . import cvWConsts, cvWCreate, cvWDictFile, cWConsts, cWDictFile, cWExpand
from .cWParamDict import add_file_unparsed, has_file_wrapper, has_file_wrapper_params, is_true

# from .cvWParams import MatchPolicy
from .matchPolicy import MatchPolicy

####################################################################################
# Functions to validate the match expression once expanded
# validate_node() was moved to cWDictFile, should these also be removed or moved somewhere else?


def translate_match_attrs(loc_str, match_attrs_name, match_attrs):
    """Translate the passed factory/job match_attrs to a format useful
    for match validation step

    Args:
        loc_str:
        match_attrs_name:
        match_attrs:

    Returns:

    """

    translations = {"string": "a", "int": 1, "bool": True, "real": 1.0}
    translated_attrs = {}

    for attr_name in match_attrs.keys():
        attr_type = match_attrs[attr_name]["type"]
        try:
            translated_attrs[attr_name] = translations[attr_type]
        except KeyError as e:
            raise RuntimeError(f"Invalid {loc_str} {match_attrs_name} attr type '{attr_type}'") from e

    return translated_attrs


def validate_match(loc_str, match_str, factory_attrs, job_attrs, attr_dict, policy_modules):
    """Validate match_expr, factory_match_attrs, job_match_attrs,
    <attrs> and their equivalents in policy_modules, by actually evaluating
    the match_expr string.
    Since it will likely use the external dictionaries,
      create a mock version of them, just making sure the types are correct

    Args:
        loc_str (str): Section to be validated. i.e. 'frontend' or 'group x'
        match_str (str): match_expr to be applied to this section
        factory_attrs (dict): factory_match_attrs for this section
        job_attrs (dict): job_match_attrs for this section
        attr_dict (dict): attrs for this section
        policy_modules (list): policy modules

    """

    # Globals/Locals that will be passed to the eval so that we
    # can validate the match_expr as well
    env = {"glidein": {"attrs": {}}, "job": {}, "attr_dict": {}, "getGlideinCpusNum": getGlideinCpusNum}

    # Validate factory's match_attrs
    env["glidein"]["attrs"] = translate_match_attrs(loc_str, "factory", factory_attrs)

    # Validate job's match_attrs
    env["job"] = translate_match_attrs(loc_str, "job", job_attrs)

    # Validate attr
    for attr_name in attr_dict.keys():
        attr_type = attr_dict[attr_name]["type"]
        if attr_type == "string":
            attr_val = "a"
        elif attr_type == "int":
            attr_val = 1
        elif attr_type == "expr":
            attr_val = "a"
        else:
            raise RuntimeError(f"Invalid {loc_str} attr type '{attr_type}'")
        env["attr_dict"][attr_name] = attr_val

    # Now that we have validated the match_attrs, compile match_obj
    try:
        match_obj = compile(match_str, "<string>", "exec")
        eval(match_obj, env)
    except KeyError as e:
        raise RuntimeError(f"Invalid {loc_str} match_expr '{match_str}': Missing attribute {e}") from e
    except Exception as e:
        raise RuntimeError(f"Invalid {loc_str} match_expr '{match_str}': {e}") from e

    # Validate the match(job, glidein) from the policy modules
    for pmodule in policy_modules:
        try:
            if "match" in dir(pmodule.pyObject):
                # Done to test errors, OK not to assign
                match_result = pmodule.pyObject.match(env["job"], env["glidein"])  # noqa: F841
        except KeyError as e:
            raise RuntimeError(
                f"Error in {loc_str} policy module's {pmodule.name}.match(job, glidein): Missing attribute {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Error in {loc_str} policy module's {pmodule.name}.match(job, glidein): {e}") from e

    return


# TODO: 5345 to move to cvWParamDict, replacing the validation functions, after expansion
# verify match data and create the attributes if needed


def derive_and_validate_match(
    group_name, match_expr_pair, factory_attr_list_pair, job_attr_list_pair, attr_dict_pair, policy_files_pair
):
    """Validate match strings, by first concatenating and then evaluating them
    Since the eval will likely use the external dictionaries,
      create a mock version of them, just making sure the types are correct
    The complete list of attributes is created by merging main and group dictionaries

    Args:
        group_name (str): name of the group (frontend for the global attributes only)
        match_expr_pair  (tuple): Pair of (main,group) match strings to validate
        factory_attr_list_pair (tuple): Pair of (main,group) descriptions of the queried factory attributes
        job_attr_list_pair (tuple): Pair of (main,group) descriptions of the queried user job attributes
        attr_dict_pair (tuple): Pair of (main,group) descriptions of the frontend attributes
        policy_modules_pair (tuple): Pair of (main,group) descriptions of the frontend attributes

    Returns:

    """

    # TODO: Do we really need to validate frontend main section?
    # This gets validated any ways in the groups section
    policy_modules = []
    if policy_files_pair[0]:
        policy_modules.append(MatchPolicy(policy_files_pair[0]))
    #    validate_match('frontend',
    #                   match_expr_pair[0],
    #                   factory_attr_list_pair[0],
    #                   job_attr_list_pair[0], attr_dict_pair[0],
    #                   policy_modules)

    # Merge group match info and attrs from
    # global section with those specific to group
    # Match and query expressions are ANDed
    # attrs, job & factory match_attrs are appended with group
    # specific values overriding the global values

    # Get frontend and group specific policy modules to use
    pmodules = list(policy_modules)
    if policy_files_pair[1]:
        pmodules.append(MatchPolicy(policy_files_pair[1]))

    # Construct group specific dict of attrs in <attrs>
    attrs_dict = {}
    for d in attr_dict_pair:
        for attr_name in d.keys():
            # they are all strings
            # just make group override main
            attrs_dict[attr_name] = d[attr_name]  # "string"
    # Construct group specific dict of factory_attrs in <match_attrs>
    # and those from the policy_modules
    factory_attrs = {}
    for d in factory_attr_list_pair:
        for attr_name in d.keys():
            if (attr_name in factory_attrs) and (factory_attrs[attr_name] != d[attr_name]["type"]):
                raise RuntimeError(
                    "Conflicting factory attribute type %s (%s,%s)"
                    % (attr_name, factory_attrs[attr_name], d[attr_name]["type"])
                )
            else:
                factory_attrs[attr_name] = d[attr_name]
    for pmodule in pmodules:
        if pmodule.factoryMatchAttrs:
            for attr_name in pmodule.factoryMatchAttrs.keys():
                factory_attrs[attr_name] = pmodule.factoryMatchAttrs[attr_name]

    # Construct group specific dict of job_attrs in <match_attrs>
    # and those from the policy_modules
    job_attrs = {}
    for d in job_attr_list_pair:
        for attr_name in d.keys():
            if (attr_name in job_attrs) and (job_attrs[attr_name]["type"] != d[attr_name]["type"]):
                raise RuntimeError(
                    "Conflicting job attribute type %s (%s,%s)"
                    % (attr_name, job_attrs[attr_name], d[attr_name]["type"])
                )
            else:
                job_attrs[attr_name] = d[attr_name]
    for pmodule in pmodules:
        if pmodule.jobMatchAttrs:
            for attr_name in pmodule.jobMatchAttrs.keys():
                job_attrs[attr_name] = pmodule.jobMatchAttrs[attr_name]

    # AND global and group specific match_expr
    # and those from the policy_modules
    match_expr = "(%s) and (%s)" % (match_expr_pair)

    return validate_match("group %s" % group_name, match_expr, factory_attrs, job_attrs, attrs_dict, pmodules)


################################################
#
# This Class contains the main dicts
#
################################################


class frontendMainDicts(cvWDictFile.frontendMainDicts):
    def __init__(self, params, workdir_name):
        cvWDictFile.frontendMainDicts.__init__(
            self,
            params.work_dir,
            params.stage_dir,
            workdir_name,
            simple_work_dir=False,
            assume_groups=True,
            log_dir=params.log_dir,
        )
        self.monitor_dir = params.monitor_dir
        self.add_dir_obj(cWDictFile.MonitorWLinkDirSupport(self.monitor_dir, self.work_dir))
        self.monitor_jslibs_dir = os.path.join(self.monitor_dir, "jslibs")
        self.add_dir_obj(cWDictFile.SimpleDirSupport(self.monitor_jslibs_dir, "monitor"))
        self.params = params
        self.enable_expansion = str2bool(self.params.data.get("enable_attribute_expansion", "False"))
        self.active_sub_list = []
        self.monitor_jslibs = []
        self.monitor_htmls = []
        self.client_security = {}

    def populate(self, params=None):
        """Populate the main dictionary. Return a dictionary of attributes that must go into the group section

        Args:
            params:

        Returns:
            dict: dictionary of attributes that must go into the group section

        """
        if params is None:
            params = self.params

        outdict = {"descript": {}}

        # put default files in place first
        self.dicts["preentry_file_list"].add_placeholder(cWConsts.CONSTS_FILE, allow_overwrite=True)
        self.dicts["preentry_file_list"].add_placeholder(cWConsts.VARS_FILE, allow_overwrite=True)
        self.dicts["preentry_file_list"].add_placeholder(
            cWConsts.UNTAR_CFG_FILE, allow_overwrite=True
        )  # this one must be loaded before any tarball
        self.dicts["preentry_file_list"].add_placeholder(
            cWConsts.GRIDMAP_FILE, allow_overwrite=True
        )  # this one must be loaded before factory runs setup_x509.sh

        # follow by the blacklist file
        file_name = cWConsts.BLACKLIST_FILE
        self.dicts["preentry_file_list"].add_from_file(
            file_name,
            cWDictFile.FileDictFile.make_val_tuple(file_name, "nocache", config_out="BLACKLIST_FILE"),
            os.path.join(params.src_dir, file_name),
        )

        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ("cat_consts.sh", "check_blacklist.sh"):
            self.dicts["preentry_file_list"].add_from_file(
                script_name,
                cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), "exec"),
                os.path.join(params.src_dir, script_name),
            )
        # TODO: gwms25073 change the following lines, this file will have to be fixed w/ special type/time
        #  to be picked as file to source pre-job
        for script_name in ("setup_prejob.sh",):
            self.dicts["preentry_file_list"].add_from_file(
                script_name,
                cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), "regular"),
                os.path.join(params.src_dir, script_name),
            )

        # put user files in stage
        for user_file in params.files:
            add_file_unparsed(user_file, self.dicts, False)

        # start expr is special
        start_expr = None

        # put user attributes into config files
        for attr_name in list(params.attrs.keys()):
            if attr_name in ("GLIDECLIENT_Start", "GLIDECLIENT_Group_Start"):
                if start_expr is None:
                    start_expr = params.attrs[attr_name].value
                elif params.attrs[attr_name].value not in (None, "True"):
                    start_expr = f"({start_expr})&&({params.attrs[attr_name].value})"
                # delete from the internal structure... that's legacy only
                del params.data["attrs"][attr_name]
            elif (
                params.attrs[attr_name].value.find("$") == -1 or not self.enable_expansion
            ):  # does not need to be expanded
                add_attr_unparsed(attr_name, params, self.dicts, "main")
            # ignore attributes in the global section that need expansion

        real_start_expr = params.match.start_expr
        if start_expr is not None:
            if real_start_expr != "True":
                real_start_expr = f"({real_start_expr})&&({start_expr})"
            else:
                real_start_expr = start_expr
            # since I removed the attributes, roll back into the match.start_expr
            params.data["match"]["start_expr"] = real_start_expr

        if real_start_expr.find("$") == -1 or not self.enable_expansion:
            self.dicts["consts"].add("GLIDECLIENT_Start", real_start_expr)
        else:
            # the start expression must be expanded, so will deal with it in the group section
            # use a simple placeholder, since the glideins expect it
            self.dicts["consts"].add("GLIDECLIENT_Start", "True")

        # create GLIDEIN_Collector attribute
        self.dicts["params"].add_extended("GLIDEIN_Collector", False, str(calc_glidein_collectors(params.collectors)))
        # create GLIDEIN_CCB attribute only if CCBs list is in config file
        tmp_glidein_ccbs_string = str(calc_glidein_ccbs(params.ccbs))
        if tmp_glidein_ccbs_string:
            self.dicts["params"].add_extended("GLIDEIN_CCB", False, tmp_glidein_ccbs_string)
        populate_gridmap(params, self.dicts["gridmap"])

        if self.dicts["preentry_file_list"].is_placeholder(
            cWConsts.GRIDMAP_FILE
        ):  # gridmapfile is optional, so if not loaded, remove the placeholder
            self.dicts["preentry_file_list"].remove(cWConsts.GRIDMAP_FILE)

        # Tell condor to advertise GLIDECLIENT_ReqNode
        self.dicts["vars"].add_extended("GLIDECLIENT_ReqNode", "string", None, None, False, True, False)

        # derive attributes
        populate_common_attrs(self.dicts)

        # populate complex files
        populate_frontend_descript(self.work_dir, self.dicts["frontend_descript"], self.active_sub_list, params)
        populate_common_descript(self.dicts["frontend_descript"], params)

        # some of the descript attributes may need expansion... push them into group
        for attr_name in ("JobQueryExpr", "FactoryQueryExpr", "MatchExpr"):
            if (
                (type(self.dicts["frontend_descript"][attr_name]) in (str, str))
                and (self.dicts["frontend_descript"][attr_name].find("$") != -1)
                and self.enable_expansion
            ):
                # needs to be expanded, put in group
                outdict["descript"][attr_name] = self.dicts["frontend_descript"][attr_name]
                # set it to the default True value here
                self.dicts["frontend_descript"].add(attr_name, "True", allow_overwrite=True)

        # Apply multicore policy so frontend can deal with multicore
        # glideins and requests correctly
        apply_multicore_policy(self.dicts["frontend_descript"])

        # populate the monitor files
        javascriptrrd_dir = params.monitor.javascriptRRD_dir
        for mfarr in ((params.src_dir, "frontend_support.js"), (javascriptrrd_dir, "javascriptrrd.wlibs.js")):
            mfdir, mfname = mfarr
            parent_dir = self.find_parent_dir(mfdir, mfname)
            mfobj = cWDictFile.SimpleFile(parent_dir, mfname)
            mfobj.load()
            self.monitor_jslibs.append(mfobj)

        for mfarr in (
            (params.src_dir, "frontendRRDBrowse.html"),
            (params.src_dir, "frontendRRDGroupMatrix.html"),
            (params.src_dir, "frontendGroupGraphStatusNow.html"),
            (params.src_dir, "frontendStatus.html"),
        ):
            mfdir, mfname = mfarr
            mfobj = cWDictFile.SimpleFile(mfdir, mfname)
            mfobj.load()
            self.monitor_htmls.append(mfobj)

        mfobj = cWDictFile.SimpleFile(params.src_dir + "/frontend", "index.html")
        mfobj.load()
        self.monitor_htmls.append(mfobj)

        for imgfil in (
            "frontendGroupGraphsNow.small.png",
            "frontendRRDBrowse.small.png",
            "frontendRRDGroupMatix.small.png",
            "frontendStatus.small.png",
        ):
            mfobj = cWDictFile.SimpleFile(params.src_dir + "/frontend/images", imgfil)
            mfobj.load()
            self.monitor_htmls.append(mfobj)

        # populate security data
        populate_main_security(self.client_security, params)

        return outdict

    def find_parent_dir(self, search_path, name):
        """Given a search path, determine if the given file exists
        somewhere in the path.
        Returns: if found. returns the parent directory
                 if not found, raises an Exception
        """
        for root, dirs, files in os.walk(search_path, topdown=True):
            for filename in files:
                if filename == name:
                    return root
        raise RuntimeError(f"Unable to find {name} in {search_path} path")

    def reuse(self, other):
        """
        Reuse as much of the other as possible
        other must be of the same class

        @type other: frontendMainDicts
        @param other: Object to reuse
        """
        if self.monitor_dir != other.monitor_dir:
            print(
                "WARNING: main monitor base_dir has changed, stats may be lost: '%s'!='%s'"
                % (self.monitor_dir, other.monitor_dir)
            )

        return cvWDictFile.frontendMainDicts.reuse(self, other)

    def save(self, set_readonly=True):
        cvWDictFile.frontendMainDicts.save(self, set_readonly)
        self.save_monitor()
        self.save_client_security()
        # Create a local copy of the policy file so we are not impacted
        # if the admin is changing the file and if it has errors
        if self.params.match["policy_file"]:
            shutil.copy(self.params.match["policy_file"], self.work_dir)

    ########################################
    # INTERNAL
    ########################################

    def save_monitor(self):
        for fobj in self.monitor_jslibs:
            fobj.save(dir=self.monitor_jslibs_dir, save_only_if_changed=False)
        for fobj in self.monitor_htmls:
            fobj.save(dir=self.monitor_dir, save_only_if_changed=False)
        return

    def save_client_security(self):
        # create a dummy mapfile so we have a reasonable default
        cvWCreate.create_client_mapfile(
            os.path.join(self.work_dir, cvWConsts.FRONTEND_MAP_FILE), self.client_security["proxy_DN"], [], [], []
        )
        # but the real mapfile will be (potentially) different for each
        # group, so frontend daemons will need to point to the real one at runtime
        cvWCreate.create_client_condor_config(
            os.path.join(self.work_dir, cvWConsts.FRONTEND_CONDOR_CONFIG_FILE),
            os.path.join(self.work_dir, cvWConsts.FRONTEND_MAP_FILE),
            self.client_security["collector_nodes"],
            self.params.security["classad_proxy"],
        )
        return


################################################
#
# This Class contains the group dicts
#
################################################


class frontendGroupDicts(cvWDictFile.frontendGroupDicts):
    def __init__(self, params, sub_name, summary_signature, workdir_name):
        cvWDictFile.frontendGroupDicts.__init__(
            self,
            params.work_dir,
            params.stage_dir,
            sub_name,
            summary_signature,
            workdir_name,
            simple_work_dir=False,
            base_log_dir=params.log_dir,
        )
        self.monitor_dir = cvWConsts.get_group_monitor_dir(params.monitor_dir, sub_name)
        self.add_dir_obj(cWDictFile.MonitorWLinkDirSupport(self.monitor_dir, self.work_dir))
        self.params = params
        self.enable_expansion = str2bool(self.params.data.get("enable_attribute_expansion", "False"))
        self.client_security = {}

    def populate(self, promote_dicts, main_dicts, params=None):
        if params is None:
            params = self.params

        sub_params = params.groups[self.sub_name]

        # put default files in place first
        self.dicts["preentry_file_list"].add_placeholder(cWConsts.CONSTS_FILE, allow_overwrite=True)
        self.dicts["preentry_file_list"].add_placeholder(cWConsts.VARS_FILE, allow_overwrite=True)
        self.dicts["preentry_file_list"].add_placeholder(
            cWConsts.UNTAR_CFG_FILE, allow_overwrite=True
        )  # this one must be loaded before any tarball

        # follow by the blacklist file
        file_name = cWConsts.BLACKLIST_FILE
        self.dicts["preentry_file_list"].add_from_file(
            file_name,
            cWDictFile.FileDictFile.make_val_tuple(file_name, "nocache", config_out="BLACKLIST_FILE"),
            os.path.join(params.src_dir, file_name),
        )

        # TODO: should these 2 scripts be removed? files above and blacklist may be different between global and group
        #  but the scripts should be the same and could be used from the other client directory
        #  or should all be duplicate?
        # Load initial system scripts
        # These should be executed before the other scripts
        for script_name in ("cat_consts.sh", "check_blacklist.sh"):
            self.dicts["preentry_file_list"].add_from_file(
                script_name,
                cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(script_name), "exec"),
                os.path.join(params.src_dir, script_name),
            )

        # put user files in stage
        for user_file in sub_params.files:
            add_file_unparsed(user_file, self.dicts, False)

        # insert the global values that need to be expanded
        # will be in the group section now
        for attr_name in params.attrs.keys():
            if params.attrs[attr_name].value.find("$") != -1 and self.enable_expansion:
                if attr_name not in sub_params.attrs.keys():
                    add_attr_unparsed(attr_name, params, self.dicts, self.sub_name)
                # else the group value will override it later on

        # start expr is special
        start_expr = None

        # put user attributes into config files
        for attr_name in list(sub_params.attrs.keys()):
            if attr_name in ("GLIDECLIENT_Group_Start", "GLIDECLIENT_Start"):
                if start_expr is None:
                    start_expr = sub_params.attrs[attr_name].value
                elif sub_params.attrs[attr_name].value is not None:
                    start_expr = f"({start_expr})&&({sub_params.attrs[attr_name].value})"
                # delete from the internal structure... that's legacy only
                del sub_params.data["attrs"][attr_name]
            else:
                add_attr_unparsed(attr_name, sub_params, self.dicts, self.sub_name)

        real_start_expr = sub_params.match.start_expr
        if start_expr is not None:
            if real_start_expr != "True":
                real_start_expr = f"({real_start_expr})&&({start_expr})"
            else:
                real_start_expr = start_expr
            # since I removed the attributes, roll back into the match.start_expr
            sub_params.data["match"]["start_expr"] = real_start_expr

        if params.match.start_expr.find("$") != -1 and self.enable_expansion:
            # the global one must be expanded, so deal with it at the group level
            real_start_expr = f"({params.match.start_expr})&&({real_start_expr})"

        self.dicts["consts"].add("GLIDECLIENT_Group_Start", real_start_expr)

        # derive attributes
        populate_common_attrs(self.dicts)

        # populate complex files
        populate_group_descript(self.work_dir, self.dicts["group_descript"], self.sub_name, sub_params)
        populate_common_descript(self.dicts["group_descript"], sub_params)  # MMDB 5345 , self.dicts['attrs'])

        # Apply group specific singularity policy
        validate_singularity(self.dicts, sub_params, params, self.sub_name)
        validate_schedds(main_dicts["frontend_descript"]["JobSchedds"], self.dicts["group_descript"]["JobSchedds"])

        apply_group_singularity_policy(self.dicts["group_descript"], sub_params, params)

        # look up global descript value, and if they need to be expanded, move them in the entry
        for kt in (("JobQueryExpr", "&&"), ("FactoryQueryExpr", "&&"), ("MatchExpr", "and")):
            attr_name, connector = kt
            if attr_name in promote_dicts["descript"]:
                # needs to be expanded, put it here, already joined with local one
                self.dicts["group_descript"].add(
                    attr_name,
                    "(%s)%s(%s)"
                    % (promote_dicts["descript"][attr_name], connector, self.dicts["group_descript"][attr_name]),
                    allow_overwrite=True,
                )

        # populate security data
        populate_main_security(self.client_security, params)
        populate_group_security(self.client_security, params, sub_params, self.sub_name)

        # we now have all the attributes... do the expansion
        # first, let's merge the attributes
        summed_attrs = {}
        for d in (main_dicts["attrs"], self.dicts["attrs"]):
            for k in d.keys:
                # if the same key is in both global and group (i.e. local), group wins
                summed_attrs[k] = d[k]

        for dname in ("attrs", "consts", "group_descript"):
            for attr_name in self.dicts[dname].keys:
                if (
                    (type(self.dicts[dname][attr_name]) in (str, str))
                    and (self.dicts[dname][attr_name].find("$") != -1)
                    and self.enable_expansion
                ):
                    self.dicts[dname].add(
                        attr_name, cWExpand.expand_DLR(self.dicts[dname][attr_name], summed_attrs), allow_overwrite=True
                    )
        for dname in ("params",):
            for attr_name in self.dicts[dname].keys:
                if (
                    (type(self.dicts[dname][attr_name][1]) in (str, str))
                    and (self.dicts[dname][attr_name][1].find("$") != -1)
                    and self.enable_expansion
                ):
                    self.dicts[dname].add(
                        attr_name,
                        (
                            self.dicts[dname][attr_name][0],
                            cWExpand.expand_DLR(self.dicts[dname][attr_name][1], summed_attrs),
                        ),
                        allow_overwrite=True,
                    )

        # now that all is expanded, validate match_expression

        derive_and_validate_match(
            self.sub_name,
            (main_dicts["frontend_descript"]["MatchExpr"], self.dicts["group_descript"]["MatchExpr"]),
            (params.match.factory.match_attrs, sub_params.match.factory.match_attrs),
            (params.match.job.match_attrs, sub_params.match.job.match_attrs),
            #                                  (main_dicts['attrs'], self.dicts['attrs']),
            (self.params.attrs, self.params.groups[self.sub_name]["attrs"]),
            (params.match.policy_file, sub_params.match.policy_file),
        )

    def reuse(self, other):
        """
        Reuse as much of the other as possible
        other must be of the same class

        @type other: frontendGroupDicts
        @param other: Object to reuse
        """
        if self.monitor_dir != other.monitor_dir:
            print(
                "WARNING: group monitor base_dir has changed, stats may be lost: '%s'!='%s'"
                % (self.monitor_dir, other.monitor_dir)
            )
        return cvWDictFile.frontendGroupDicts.reuse(self, other)

    def save(self, set_readonly=True):
        cvWDictFile.frontendGroupDicts.save(self, set_readonly)
        self.save_client_security()
        # Create a local copy of the policy file so we are not impacted
        # if the admin is changing the file and if it has errors
        if self.params.groups[self.sub_name].match["policy_file"]:
            shutil.copy(self.params.groups[self.sub_name].match["policy_file"], self.work_dir)

    ########################################
    # INTERNAL
    ########################################

    def save_client_security(self):
        # create the real mapfiles
        cvWCreate.create_client_mapfile(
            os.path.join(self.work_dir, cvWConsts.GROUP_MAP_FILE),
            self.client_security["proxy_DN"],
            self.client_security["factory_DNs"],
            self.client_security["schedd_DNs"],
            self.client_security["collector_DNs"],
        )
        cvWCreate.create_client_mapfile(
            os.path.join(self.work_dir, cvWConsts.GROUP_WPILOTS_MAP_FILE),
            self.client_security["proxy_DN"],
            self.client_security["factory_DNs"],
            self.client_security["schedd_DNs"],
            self.client_security["collector_DNs"],
            self.client_security["pilot_DNs"],
        )
        return


################################################
#
# This Class contains both the main and
# the group dicts
#
################################################


class frontendDicts(cvWDictFile.frontendDicts):
    def __init__(self, params, sub_list=None):  # if sub_list None, get it from params
        if sub_list is None:
            sub_list = list(params.groups.keys())

        self.params = params
        cvWDictFile.frontendDicts.__init__(
            self, params.work_dir, params.stage_dir, sub_list, simple_work_dir=False, log_dir=params.log_dir
        )

        self.monitor_dir = params.monitor_dir
        self.active_sub_list = []
        return

    def populate(self, params=None):  # will update params (or self.params)
        if params is None:
            params = self.params

        promote_dicts = self.main_dicts.populate(params)
        self.active_sub_list = self.main_dicts.active_sub_list

        self.local_populate(params)
        for sub_name in self.sub_list:
            self.sub_dicts[sub_name].populate(promote_dicts, self.main_dicts.dicts, params)

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        if self.monitor_dir != other.monitor_dir:
            print(
                "WARNING: monitor base_dir has changed, stats may be lost: '%s'!='%s'"
                % (self.monitor_dir, other.monitor_dir)
            )

        return cvWDictFile.frontendDicts.reuse(self, other)

    ###########
    # PRIVATE
    ###########

    def local_populate(self, params):
        return  # nothing to do

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return frontendMainDicts(self.params, self.workdir_name)

    def new_SubDicts(self, sub_name):
        return frontendGroupDicts(self.params, sub_name, self.main_dicts.get_summary_signature(), self.workdir_name)


############################################################
#
# P R I V A T E - Do not use
#
############################################################


#######################
# Register an attribute
# attr_obj as described by Params.attr_defaults
def add_attr_unparsed(attr_name, params, dicts, description):
    try:
        add_attr_unparsed_real(attr_name, params, dicts)
    except RuntimeError as e:
        raise RuntimeError(f"Error parsing attr {description}[{attr_name}]: {str(e)}") from e


def validate_attribute(attr_name, attr_val):
    """Check the attribute value is valid. Otherwise throw RuntimeError"""
    if not attr_name or not attr_val:
        return
    # Consider adding a common one in cWParamDict
    # Series of if/elif sections validating the attributes
    if attr_name == "GLIDEIN_Singularity_Use":
        if attr_val not in ("DISABLE_GWMS", "NEVER", "OPTIONAL", "PREFERRED", "REQUIRED"):
            raise RuntimeError(
                "Invalid value for GLIDEIN_Singularity_Use: %s not in DISABLE_GWMS, NEVER, OPTIONAL, PREFERRED, REQUIRED."
                % attr_val
            )


def add_attr_unparsed_real(attr_name, params, dicts):
    attr_obj = params.attrs[attr_name]

    if attr_obj.value is None:
        raise RuntimeError(f"Attribute '{attr_name}' does not have a value: {attr_obj}")

    is_parameter = is_true(attr_obj.parameter)
    # attr_obj.type=="expr" is now used for HTCondor expression
    is_expr = False
    attr_val = params.extract_attr_val(attr_obj)

    validate_attribute(attr_name, attr_val)

    if is_parameter:
        dicts["params"].add_extended(attr_name, is_expr, attr_val)
    else:
        dicts["consts"].add(attr_name, attr_val)

    do_glidein_publish = is_true(attr_obj.glidein_publish)
    do_job_publish = is_true(attr_obj.job_publish)

    if do_glidein_publish or do_job_publish:
        # need to add a line only if will be published
        if attr_name in dicts["vars"]:
            # already in the var file, check if compatible
            attr_var_el = dicts["vars"][attr_name]
            attr_var_type = attr_var_el[0]
            if (
                ((attr_obj.type == "int") and (attr_var_type != "I"))
                or ((attr_obj.type == "expr") and (attr_var_type == "I"))
                or ((attr_obj.type == "string") and (attr_var_type == "I"))
            ):
                raise RuntimeError(f"Types not compatible ({attr_obj.type},{attr_var_type})")
            attr_var_export = attr_var_el[4]
            if do_glidein_publish and (attr_var_export == "N"):
                raise RuntimeError("Cannot force glidein publishing")
            attr_var_job_publish = attr_var_el[5]
            if do_job_publish and (attr_var_job_publish == "-"):
                raise RuntimeError("Cannot force job publishing")
        else:
            dicts["vars"].add_extended(attr_name, attr_obj.type, None, None, False, do_glidein_publish, do_job_publish)


###################################
# Create the frontend descript file
def populate_frontend_descript(work_dir, frontend_dict, active_sub_list, params):  # will be modified
    frontend_dict.add("DowntimesFile", params.downtimes_file)
    frontend_dict.add("FrontendName", params.frontend_name)
    frontend_dict.add("WebURL", params.web_url)
    if hasattr(params, "monitoring_web_url") and (params.monitoring_web_url is not None):
        frontend_dict.add("MonitoringWebURL", params.monitoring_web_url)
    else:
        frontend_dict.add("MonitoringWebURL", params.web_url.replace("stage", "monitor"))

    # TODO: refcred (refactoring of credentials) remove proxy requirement, replace w/ any credential, maybe ID
    if params.security.classad_proxy is None:
        params.subparams.data["security"]["classad_proxy"] = None
    else:
        params.subparams.data["security"]["classad_proxy"] = os.path.abspath(params.security.classad_proxy)
        if not os.path.isfile(params.security.classad_proxy):
            raise RuntimeError("security.classad_proxy(%s) is not a file" % params.security.classad_proxy)

    frontend_dict.add("ClassAdProxy", params.security.classad_proxy)

    frontend_dict.add("SymKeyType", params.security.sym_key)

    active_sub_list[:]  # erase all
    for sub in list(params.groups.keys()):
        if is_true(params.groups[sub].enabled):
            active_sub_list.append(sub)
    frontend_dict.add("Groups", ",".join(active_sub_list))

    frontend_dict.add("LoopDelay", params.loop_delay)
    frontend_dict.add("AdvertiseDelay", params.advertise_delay)
    frontend_dict.add("GroupParallelWorkers", params.group_parallel_workers)
    frontend_dict.add("RestartAttempts", params.restart_attempts)
    frontend_dict.add("RestartInterval", params.restart_interval)
    frontend_dict.add("AdvertiseWithTCP", params.advertise_with_tcp)
    frontend_dict.add("AdvertiseWithMultiple", params.advertise_with_multiple)

    frontend_dict.add("MonitorDisplayText", params.monitor_footer.display_txt)
    frontend_dict.add("MonitorLink", params.monitor_footer.href_link)

    frontend_dict.add("CondorConfig", os.path.join(work_dir, cvWConsts.FRONTEND_CONDOR_CONFIG_FILE))

    frontend_dict.add("LogDir", params.log_dir)
    frontend_dict.add("ProcessLogs", str(params.log_retention["process_logs"]))

    frontend_dict.add("IgnoreDownEntries", params.config.ignore_down_entries)
    frontend_dict.add("RampUpAttenuation", params.config.ramp_up_attenuation)
    frontend_dict.add("MaxIdleVMsTotal", params.config.idle_vms_total.max)
    frontend_dict.add("CurbIdleVMsTotal", params.config.idle_vms_total.curb)
    frontend_dict.add("MaxIdleVMsTotalGlobal", params.config.idle_vms_total_global.max)
    frontend_dict.add("CurbIdleVMsTotalGlobal", params.config.idle_vms_total_global.curb)
    frontend_dict.add("MaxRunningTotal", params.config.running_glideins_total.max)
    frontend_dict.add("CurbRunningTotal", params.config.running_glideins_total.curb)
    frontend_dict.add("MaxRunningTotalGlobal", params.config.running_glideins_total_global.max)
    frontend_dict.add("CurbRunningTotalGlobal", params.config.running_glideins_total_global.curb)
    frontend_dict.add("HighAvailability", params.high_availability)


#######################
# Populate group descript
def populate_group_descript(work_dir, group_descript_dict, sub_name, sub_params):  # will be modified
    group_descript_dict.add("GroupName", sub_name)

    group_descript_dict.add("MapFile", os.path.join(work_dir, cvWConsts.GROUP_MAP_FILE))
    group_descript_dict.add("MapFileWPilots", os.path.join(work_dir, cvWConsts.GROUP_WPILOTS_MAP_FILE))

    group_descript_dict.add("PartGlideinMinMemory", sub_params.config.partitionable_glidein.min_memory)

    group_descript_dict.add("IgnoreDownEntries", sub_params.config.ignore_down_entries)
    group_descript_dict.add("RampUpAttenuation", sub_params.config.ramp_up_attenuation)
    group_descript_dict.add("MaxRunningPerEntry", sub_params.config.running_glideins_per_entry.max)
    group_descript_dict.add("MinRunningPerEntry", sub_params.config.running_glideins_per_entry.min)
    group_descript_dict.add("FracRunningPerEntry", sub_params.config.running_glideins_per_entry.relative_to_queue)
    group_descript_dict.add("MaxIdlePerEntry", sub_params.config.idle_glideins_per_entry.max)
    group_descript_dict.add("ReserveIdlePerEntry", sub_params.config.idle_glideins_per_entry.reserve)
    group_descript_dict.add("IdleLifetime", sub_params.config.idle_glideins_lifetime.max)
    group_descript_dict.add("MaxIdleVMsPerEntry", sub_params.config.idle_vms_per_entry.max)
    group_descript_dict.add("CurbIdleVMsPerEntry", sub_params.config.idle_vms_per_entry.curb)
    group_descript_dict.add("MaxIdleVMsTotal", sub_params.config.idle_vms_total.max)
    group_descript_dict.add("CurbIdleVMsTotal", sub_params.config.idle_vms_total.curb)
    group_descript_dict.add("MaxRunningTotal", sub_params.config.running_glideins_total.max)
    group_descript_dict.add("CurbRunningTotal", sub_params.config.running_glideins_total.curb)
    group_descript_dict.add("MaxMatchmakers", sub_params.config.processing_workers.matchmakers)
    group_descript_dict.add("RemovalType", sub_params.config.glideins_removal.type)
    group_descript_dict.add("RemovalWait", sub_params.config.glideins_removal.wait)
    group_descript_dict.add("RemovalRequestsTracking", sub_params.config.glideins_removal.requests_tracking)
    group_descript_dict.add("RemovalMargin", sub_params.config.glideins_removal.margin)


#####################################################
# Populate values common to frontend and group dicts
MATCH_ATTR_CONV = {"string": "s", "int": "i", "real": "r", "bool": "b"}


def apply_group_singularity_policy(descript_dict, sub_params, params):
    glidein_singularity_use = None
    query_expr = descript_dict["FactoryQueryExpr"]
    match_expr = descript_dict["MatchExpr"]
    ma_arr = []
    match_attrs = None

    # Consider GLIDEIN_Singularity_Use from Group level, else global
    if "GLIDEIN_Singularity_Use" in sub_params.attrs:
        glidein_singularity_use = sub_params.attrs["GLIDEIN_Singularity_Use"]["value"]
    elif "GLIDEIN_Singularity_Use" in params.attrs:
        glidein_singularity_use = params.attrs["GLIDEIN_Singularity_Use"]["value"]

    if glidein_singularity_use:
        descript_dict.add("GLIDEIN_Singularity_Use", glidein_singularity_use)

        if glidein_singularity_use == "REQUIRED":  # avoid NEVER and undefiled (probably will not have Singularity)
            # NOTE: 3.5 behavior is different from 3.4.x or earlier, the SINGULARITY_BIN meaning changes
            #  SINGULARITY_BIN is no more used as flag to select Singularity, only for the binary selection
            query_expr = (
                '(%s) && (GLIDEIN_SINGULARITY_REQUIRE=!="NEVER") && (GLIDEIN_SINGULARITY_REQUIRE=!=UNDEFINED)'
                % query_expr
            )
            match_expr = (
                '(%s) and (glidein["attrs"].get("GLIDEIN_SINGULARITY_REQUIRE", "NEVER") != "NEVER")' % match_expr
            )
            ma_arr.append(("GLIDEIN_SINGULARITY_REQUIRE", "s"))
        elif glidein_singularity_use == "NEVER":  # avoid REQUIRED, REQUIRED_GWMS
            query_expr = (
                '(%s) && (GLIDEIN_SINGULARITY_REQUIRE=!="REQUIRED") && (GLIDEIN_SINGULARITY_REQUIRE=!="REQUIRED_GWMS")'
                % query_expr
            )
            match_expr = (
                '(%s) and (glidein["attrs"].get("GLIDEIN_SINGULARITY_REQUIRE", "NEVER")[:8] != "REQUIRED")' % match_expr
            )
            ma_arr.append(("GLIDEIN_SINGULARITY_REQUIRE", "s"))

        if ma_arr:
            match_attrs = eval(descript_dict["FactoryMatchAttrs"]) + ma_arr
            descript_dict.add("FactoryMatchAttrs", repr(match_attrs), allow_overwrite=True)

        descript_dict.add("FactoryQueryExpr", query_expr, allow_overwrite=True)
        descript_dict.add("MatchExpr", match_expr, allow_overwrite=True)


def validate_singularity(descript_dict, sub_params, params, name):
    """If Singularity is enabled in a group, there should be at least one user wrapper for that group

    @param descript_dict: dictionaries with user files
    @param sub_params: attributes in the group section of the XML file
    @param params: attributes in the general section of the XML file
    @param name: group name
    @return:
    """
    glidein_singularity_use = ""
    if "GLIDEIN_Singularity_Use" in sub_params.attrs:
        glidein_singularity_use = sub_params.attrs["GLIDEIN_Singularity_Use"]["value"]
    elif "GLIDEIN_Singularity_Use" in params.attrs:
        glidein_singularity_use = params.attrs["GLIDEIN_Singularity_Use"]["value"]

    if glidein_singularity_use in ["OPTIONAL", "PREFERRED", "REQUIRED", "REQUIRED_GWMS"]:
        # Using Singularity, check that there is a wrapper
        if not has_file_wrapper(descript_dict):  # Checks within the group files
            if not has_file_wrapper_params(
                params.files
            ):  # Check global files using the params (main file dict is not accessible)
                raise RuntimeError(
                    "Error: group %s allows Singularity (%s) but has no wrapper file in the files list"
                    % (name, glidein_singularity_use)
                )


def validate_schedds(main_list, group_list):
    """
    Validates the use of 'ALL' in schedd configurations.

    If 'ALL' is used, it must be the only entry in `main_list`, and `group_list` must be empty.
    Any other combination is considered invalid and will raise a RuntimeError.

    Args:
        main_list (str): Comma-separated schedd hostnames in the global configuration.
        group_list (str): Comma-separated schedd hostnames in a group configuration.

    Raises:
        RuntimeError: If 'ALL' is used incorrectly (e.g. mixed with other schedds or with a non-empty group list).
    """
    main_items = main_list.split(",") if main_list else []
    group_items = group_list.split(",") if group_list else []

    if "ALL" in main_items or "ALL" in group_items:
        if main_items != ["ALL"] or group_items:
            raise RuntimeError(
                f"""It seems you want to use the '<scheddDN="ALL" fullname="ALL">' feature.
In order to do so, you need to define it in the global schedd configuration,
and all the schedds in the frontend groups must be empty.

Found:
  global configuration: '{main_list}'
  group configuration:  '{group_list}'"""
            )


def apply_multicore_policy(descript_dict):
    match_expr = descript_dict["MatchExpr"]

    # Only consider sites that provide enough GLIDEIN_CPUS (GLIDEIN_ESTIMATED_CPUS) for jobs to run
    match_expr = '(%s) and (getGlideinCpusNum(glidein) >= int(job.get("RequestCpus", 1)))' % match_expr
    descript_dict.add("MatchExpr", match_expr, allow_overwrite=True)

    # Add GLIDEIN_CPUS, GLIDEIN_ESTIMATED_CPUS and GLIDEIN_NODES to the list of attrs queried in glidefactory classad
    fact_ma = eval(descript_dict["FactoryMatchAttrs"]) + [
        ("GLIDEIN_CPUS", "s"),
        ("GLIDEIN_ESTIMATED_CPUS", "s"),
        ("GLIDEIN_NODES", "s"),
    ]
    descript_dict.add("FactoryMatchAttrs", repr(fact_ma), allow_overwrite=True)

    # Add RequestCpus to the list of attrs queried in jobs classad
    job_ma = eval(descript_dict["JobMatchAttrs"]) + [("RequestCpus", "i")]
    descript_dict.add("JobMatchAttrs", repr(job_ma), allow_overwrite=True)


def get_pool_list(credential):
    pool_idx_len = credential["pool_idx_len"]
    if pool_idx_len is None:
        pool_idx_len = 0
    else:
        pool_idx_len = int(pool_idx_len)
    pool_idx_list_unexpanded = credential["pool_idx_list"].split(",")
    pool_idx_list_expanded = []

    # Expand ranges in pool list
    for idx in pool_idx_list_unexpanded:
        if "-" in idx:
            idx_range = idx.split("-")
            for i in range(int(idx_range[0]), int(idx_range[1]) + 1):
                pool_idx_list_expanded.append(str(i))
        else:
            pool_idx_list_expanded.append(idx.strip())

    pool_idx_list_strings = []
    for idx in pool_idx_list_expanded:
        pool_idx_list_strings.append(idx.zfill(pool_idx_len))
    return pool_idx_list_strings


def match_attrs_to_array(match_attrs):
    ma_array = []

    for attr_name in list(match_attrs.keys()):
        attr_type = match_attrs[attr_name]["type"]
        if attr_type not in MATCH_ATTR_CONV:
            raise RuntimeError(f"match_attr type '{attr_type}' not one of {list(MATCH_ATTR_CONV.keys())}")
        ma_array.append((str(attr_name), MATCH_ATTR_CONV[attr_type]))

    return ma_array


# In 5345 there was an additional parameter but it was not used in the function:
# def populate_common_descript(descript_dict, params, attrs_dict):
#    attrs_dict: dictionary of attributes to expand attributes (but expansion is handled later)
def populate_common_descript(descript_dict, params):
    """Populate info common for both frontend (global) and group in the descript dict.
    descript_dict will be modified in this function

    Args:
        descript_dict (cWDictFile.StrDictFile):  description dictionary, modified in this function (side effect)
        params: params or sub_params from the config file

    Raises:
        RuntimeError when no schedd is known to DNS (or via invoked validation functions)
    """

    if params.match.policy_file:
        policy_module = MatchPolicy(params.match.policy_file)

        # Populate the descript_dict
        descript_dict.add("MatchPolicyFile", params.match.policy_file)
        descript_dict.add("MatchPolicyModuleFactoryMatchAttrs", match_attrs_to_array(policy_module.factoryMatchAttrs))
        descript_dict.add("MatchPolicyModuleJobMatchAttrs", match_attrs_to_array(policy_module.jobMatchAttrs))
        descript_dict.add("MatchPolicyModuleFactoryQueryExpr", policy_module.factoryQueryExpr)
        descript_dict.add("MatchPolicyModuleJobQueryExpr", policy_module.jobQueryExpr)

    for tel in (("factory", "Factory"), ("job", "Job")):
        param_tname, str_tname = tel
        qry_expr = params.match[param_tname]["query_expr"]
        descript_dict.add("%sQueryExpr" % str_tname, qry_expr)
        ma_arr = match_attrs_to_array(params.match[param_tname]["match_attrs"])
        descript_dict.add("%sMatchAttrs" % str_tname, repr(ma_arr))

    if params.security.security_name is not None:
        descript_dict.add("SecurityName", params.security.security_name)

    collectors = []
    for el in params.match.factory.collectors:
        if el["factory_identity"][-9:] == "@fake.org":
            raise RuntimeError("factory_identity for %s not set! (i.e. it is fake)" % el["node"])
        if el["my_identity"][-9:] == "@fake.org":
            raise RuntimeError("my_identity for %s not set! (i.e. it is fake)" % el["node"])
        cWDictFile.validate_node(el["node"])
        collectors.append((el["node"], el["factory_identity"], el["my_identity"]))
    descript_dict.add("FactoryCollectors", repr(collectors))

    schedds = []
    valid_schedd = False
    undefined_schedds = 0
    for el in params.match.job.schedds:
        # A single submit host not in the DNS should not fail the reconfig
        # Especially in production there are many submit hosts, some are temporary nodes
        # Would be useful to have a WARNING message, but the current implementation allows only fail/continue
        # Still raising an invalid configuration exception if no schedd is in DNS
        try:
            # If schedd is ALL we don't validate and check the DNS
            el["fullname"] == "ALL" or cWDictFile.validate_node(el["fullname"], check_dns=False)
            valid_schedd = True  # skipped if exception is risen
        except RuntimeWarning:
            undefined_schedds += 1
        schedds.append(el["fullname"])
    if undefined_schedds > 0 and not valid_schedd:
        raise RuntimeError("No valid schedd found, all are unknown to DNS")
    descript_dict.add("JobSchedds", ",".join(schedds))

    if params.security.proxy_selection_plugin is not None:
        descript_dict.add("ProxySelectionPlugin", params.security.proxy_selection_plugin)
    if params.security.idtoken_lifetime is not None:
        descript_dict.add("IDTokenLifetime", params.security.idtoken_lifetime)
    if params.security.idtoken_keyname is not None:
        descript_dict.add("IDTokenKeyname", params.security.idtoken_keyname)

    if len(params.security.credentials) > 0:
        proxies = []
        # TODO: absfname - Moving from absfname to name to identify the credential - fix the duplications
        #       absfname should go in the proxy_attr_names, name should be removed because used as key
        proxy_attr_names = {
            "security_class": "ProxySecurityClasses",
            "trust_domain": "ProxyTrustDomains",
            "type": "ProxyTypes",
            # credential files probably should be handles as a list, each w/ name and path
            # or the attributes ending in _file are files
            # "file": "CredentialFiles",  # placeholder for when name will not be absfname
            "generator": "CredentialGenerators",
            "keyabsfname": "ProxyKeyFiles",
            "pilotabsfname": "ProxyPilotFiles",
            "remote_username": "ProxyRemoteUsernames",
            "vm_id": "ProxyVMIds",
            "vm_type": "ProxyVMTypes",
            "creation_script": "ProxyCreationScripts",
            "project_id": "ProxyProjectIds",
            "update_frequency": "ProxyUpdateFrequency",
        }
        # translation of attributes that can be added to the base type (name in list -> attribute name)
        proxy_attr_type_list = {
            "vm_id": "vm_id",
            "vm_type": "vm_type",
            "username": "remote_username",
            "project_id": "project_id",
        }

        # TODO: this list is used for loops, replace with "for i in proxy_attr_names"
        proxy_attrs = list(proxy_attr_names.keys())
        proxy_descript_values = {}
        for attr in proxy_attrs:
            proxy_descript_values[attr] = {}
        # print params.security.credentials
        for pel in params.security.credentials:
            validate_credential_type(pel["type"])
            # TODO: absfname - use name instead (add a credential name/ID)
            id_absfname_value = pel["absfname"]  # ID for a credential (file name or generator file name)
            if not pel["absfname"]:  # Check for both missing (None) or empty value
                if not pel["generator"]:  # Check for both missing (None) or empty value
                    raise RuntimeError("All credentials without generator need a absfname!")
                else:
                    # Cannot change the value of a SubParam (no assignment to pel["absfname"]
                    id_absfname_value = pel["generator"]
            for i in pel["type"].split("+"):
                attr = proxy_attr_type_list.get(i)
                if attr and pel[attr] is None:
                    raise RuntimeError(
                        "Required attribute '{}' ('{}') missing in credential type '{}'".format(attr, i, pel["type"])
                    )
            if (pel["pool_idx_len"] is None) and (pel["pool_idx_list"] is None):
                # only one
                proxies.append(id_absfname_value)
                for attr in proxy_attrs:
                    if pel[attr] is not None:
                        proxy_descript_values[attr][id_absfname_value] = pel[attr]
            else:  # pool
                # TODO: absfname - use name instead
                pool_idx_list_expanded_strings = get_pool_list(pel)
                for idx in pool_idx_list_expanded_strings:
                    absfname = f"{id_absfname_value}{idx}"
                    proxies.append(absfname)
                    for attr in proxy_attrs:
                        if pel[attr] is not None:
                            proxy_descript_values[attr][id_absfname_value] = pel[attr]

        descript_dict.add("Proxies", repr(proxies))
        for attr in proxy_attrs:
            if len(list(proxy_descript_values[attr].keys())) > 0:
                descript_dict.add(proxy_attr_names[attr], repr(proxy_descript_values[attr]))

    match_expr = params.match.match_expr
    descript_dict.add("MatchExpr", match_expr)


def validate_credential_type(cred_type):
    mutually_exclusive = {"grid_proxy", "cert_pair", "key_pair", "username_password", "auth_file"}
    types_set = set(cred_type.split("+"))
    common_types = mutually_exclusive.intersection(types_set)  # noqa: F841  # used in temporarily commented code below

    # turn this off temporarily while we figure out how to include tokens
    # in auth_file with grid_proxy
    # if len(common_types) > 1:
    #    raise RuntimeError("Credential type '%s' has mutually exclusive components %s" % (cred_type, list(common_types)))


def calc_glidein_collectors(collectors):
    """Return a string usable for GLIDEIN_Collector

    Args:
        collectors (list): list of collectors elements (dict)

    Returns:
        str: string usable for the GLIDEIN_Collector attribute
    """
    collector_nodes = {}
    glidein_collectors = []

    for el in collectors:
        if el.group not in collector_nodes:
            collector_nodes[el.group] = {"primary": [], "secondary": []}
        if is_true(el.secondary):
            if "sock=" in el.node:
                cWDictFile.validate_node(el.node, allow_range=True)
                collector_nodes[el.group]["secondary"].append(el.node)
            else:  # single port in secondary
                cWDictFile.validate_node(el.node, allow_range=True)
                collector_nodes[el.group]["secondary"].append(el.node)
        else:
            cWDictFile.validate_node(el.node)
            collector_nodes[el.group]["primary"].append(el.node)

    for group in list(collector_nodes.keys()):
        if len(collector_nodes[group]["secondary"]) > 0:
            glidein_collectors.append(",".join(collector_nodes[group]["secondary"]))
        else:
            glidein_collectors.append(",".join(collector_nodes[group]["primary"]))
    return ";".join(glidein_collectors)


def calc_glidein_ccbs(collectors):
    """Return a string usable for GLIDEIN_CCB

    Args:
        collectors (list): list of CCB collectors elements (dict)

    Returns:
        str: string usable for the GLIDEIN_CCB attribute

    """
    # CCB collectors are subdivided in groups, mainly to control how many to use at the same time
    ccb_nodes = {}
    glidein_ccbs = []

    for el in collectors:
        if el.group not in ccb_nodes:
            ccb_nodes[el.group] = []
        if "sock=" in el.node:
            cWDictFile.validate_node(el.node, allow_range=True)
            ccb_nodes[el.group].append(el.node)
        elif "-" in el.node:  # if ccb node has port range
            cWDictFile.validate_node(el.node, allow_range=True)
            ccb_nodes[el.group].append(el.node)
        else:
            cWDictFile.validate_node(el.node)
            ccb_nodes[el.group].append(el.node)

    for group in list(ccb_nodes.keys()):
        glidein_ccbs.append(",".join(ccb_nodes[group]))

    return ";".join(glidein_ccbs)


#####################################################
# Populate gridmap to be used by the glideins
def populate_gridmap(params, gridmap_dict):
    collector_dns = []
    for coll_list in (params.collectors, params.ccbs):
        # Add both collectors and CCB DNs (if any). Duplicates are skipped
        # The name is for both collector%i.
        for el in coll_list:
            dn = el.DN
            if dn is None:
                raise RuntimeError("DN not defined for pool collector or CCB %s" % el.node)
            if dn not in collector_dns:  # skip duplicates
                collector_dns.append(dn)
                gridmap_dict.add(dn, "collector%i" % len(collector_dns))

    # Add also the frontend DN, so it is easier to debug
    if params.security.proxy_DN is not None:
        if params.security.proxy_DN not in collector_dns:
            gridmap_dict.add(params.security.proxy_DN, "frontend")


#####################################################
# Populate security values
def populate_main_security(client_security, params):
    # if params.security.proxy_DN is None:
    #    raise RuntimeError("DN not defined for classad_proxy")
    client_security["proxy_DN"] = params.security.proxy_DN

    collector_dns = []
    collector_nodes = []
    for el in params.collectors:
        dn = el.DN
        if dn is None:
            raise RuntimeError("DN not defined for pool collector %s" % el.node)
        is_secondary = is_true(el.secondary)
        if is_secondary:
            continue  # only consider primary collectors for the main security config
        collector_nodes.append(el.node)
        collector_dns.append(dn)
    if len(collector_nodes) == 0:
        raise RuntimeError("Need at least one non-secondary pool collector")
    client_security["collector_nodes"] = collector_nodes
    client_security["collector_DNs"] = collector_dns


def populate_group_security(client_security, params, sub_params, group_name):
    """Populate the DNs in client_security (factory_DNs, schedd_DNs, pilot_DNs)

    There is no return. Only via side effects

    Args:
        client_security(dict): Frontend security info
        params: parameters form the configuration
        sub_params:
        group_name(str): group name

    """
    factory_dns = []
    for collectors in (params.match.factory.collectors, sub_params.match.factory.collectors):
        for el in collectors:
            dn = el.DN
            if dn is None:
                raise RuntimeError("DN not defined for factory %s" % el.node)
            # don't worry about conflict... there is nothing wrong if the DN is listed twice
            factory_dns.append(dn)
    client_security["factory_DNs"] = factory_dns

    schedd_dns = []
    for schedds in (params.match.job.schedds, sub_params.match.job.schedds):
        for el in schedds:
            dn = el.DN
            if dn is None:
                raise RuntimeError("DN not defined for schedd %s" % el.fullname)
            # don't worry about conflict... there is nothing wrong if the DN is listed twice
            schedd_dns.append(dn)
    client_security["schedd_DNs"] = schedd_dns

    pilot_dns = []
    exclude_from_pilot_dns = ["SCITOKEN", "IDTOKEN"]
    for credentials in (params.security.credentials, sub_params.security.credentials):
        if is_true(params.groups[group_name].enabled):
            for pel in credentials:
                if pel["type"].upper() in exclude_from_pilot_dns:
                    continue
                if pel["pilotabsfname"] is None:
                    proxy_fname = pel["absfname"]
                else:
                    proxy_fname = pel["pilotabsfname"]

                if (pel["pool_idx_len"] is None) and (pel["pool_idx_list"] is None):
                    try:
                        # only one
                        dn = x509Support.extract_DN(proxy_fname)
                        # don't worry about conflict... there is nothing wrong if the DN is listed twice
                        pilot_dns.append(dn)
                    except SystemExit:
                        print("...Failed to extract DN from %s, but continuing" % proxy_fname)
                else:
                    # pool
                    pool_idx_list_expanded_strings = get_pool_list(pel)
                    for idx in pool_idx_list_expanded_strings:
                        real_proxy_fname = f"{proxy_fname}{idx}"
                        dn = x509Support.extract_DN(real_proxy_fname)
                        # don't worry about conflict... there is nothing wrong if the DN is listed twice
                        pilot_dns.append(dn)

    client_security["pilot_DNs"] = pilot_dns


#####################################################
# Populate attrs
# This is a digest of the other values


def populate_common_attrs(dicts):
    # there should be no conflicts, so does not matter in which order I put them together
    for k in dicts["params"].keys:
        dicts["attrs"].add(k, dicts["params"].get_true_val(k))
    for k in dicts["consts"].keys:
        dicts["attrs"].add(k, dicts["consts"].get_typed_val(k))
