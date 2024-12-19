# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Description:
#   Glidein creation module Classes and functions needed to
#   handle dictionary files

"""Dictionary files used in the Factory

Main dictionaries are in the global configuration.
Entry dictionaries are in the entry configuration.
Common dictionaries are in both.
The versioned dictionary are stored in timestamp versioned files

Common dictionaries:
attrs (cWDictFile.ReprDictFile, cgWConsts.ATTRS_FILE): attributes in the "entry" XML tag and "attrs" set as constants
description (cWDictFile.DescriptionDictFile, cWConsts.DESCRIPTION_FILE, versioned): factory/entry description
consts (cWDictFile.StrDictFile, cWConsts.CONSTS_FILE, versioned): constant attrs - TODO: not written?
params (cWDictFile.ReprDictFile, cgWConsts.PARAMS_FILE): attrs that are not constant (const="False", default)
submit (cWDictFile.ReprDictFile, cgWConsts.SUBMIT_ATTRS_FILE): submit configuration attributes
vars (cWDictFile.VarsDictFile, cWConsts.VARS_FILE, versioned): condor variables
untar_cfg (cWDictFile.StrDictFile, cWConsts.UNTAR_CFG_FILE, versioned): instructions for files to un-compress
file_list (cWDictFile.FileDictFile, cWConsts.FILE_LISTFILE, versioned): list of files to transfers
signature (cWDictFile.SHA1DictFile, cWConsts.SIGNATURE_FILE, versioned): files signatures for tampering verification

Main dictionaries (common and):
summary_signature (cWDictFile.SummarySHA1DictFile, cWConsts.SUMMARY_SIGNATURE_FILE):
glidein (cWDictFile.StrDictFile, cgWConsts.GLIDEIN_FILE):
build_cvmfsexec (cWDictFile.ReprDictFile, cgWConsts.CVMFSEXEC_BUILD_FILE): cvmfsexec releases
frontend_descript (cWDictFile.ReprDictFile, cgWConsts.FRONTEND_DESCRIPT_FILE): frontend description
gridmap (cWDictFile.GridMapDict, cWConsts.GRIDMAP_FILE, versioned):
at_file_list (cWDictFile.FileDictFile, cgWConsts.AT_FILE_LISTFILE, versioned): list of files w/ intermediate priority (close to entry)
after_file_list (cWDictFile.FileDictFile, cgWConsts.AFTER_FILE_LISTFILE, versioned): list of files loaded later (after entry)

Entry dictionaries (common and):
job_descript (cWDictFile.StrDictFile, cgWConsts.JOB_DESCRIPT_FILE)
infosys (InfoSysDictFile, cgWConsts.INFOSYS_FILE)
mongroup (MonitorGroupDictFile, cgWConsts.MONITOR_CONFIG_FILE)


"""

import copy
import os
import os.path

import glideinwms.lib.subprocessSupport

from glideinwms.lib.util import chmod

from . import cgWConsts, cWConsts, cWDictFile


# values are (group_name)
class MonitorGroupDictFile(cWDictFile.DictFile):
    def file_header(self, want_comments):
        if want_comments:
            return "<!-- This entry is part of following monitoring groups -->\n" + "<monitorgroups>"
        else:
            return "<monitorgroups>"

    def file_footer(self, want_comments):
        return "</monitorgroups>"

    # key can be None
    # in that case it will be composed out of value
    def add(self, key, val, allow_overwrite=0):
        if type(val) not in (type(()), type([])):
            raise RuntimeError("Values '%s' not a list or tuple" % val)
        if len(val) != 1:
            raise RuntimeError("Values '%s' not (group_name)" % str(val))

        if key is None:
            key = "%s" % val
        return cWDictFile.DictFile.add(self, key, val, allow_overwrite)

    def add_extended(self, group_name, allow_overwrite=0):
        self.add(None, (group_name,))

    def format_val(self, key, want_comments):
        return f'  <monitorgroup group_name="{self.vals[key][0]}">'

    def parse_val(self, line):
        if len(line) == 0:
            return  # ignore emoty lines
        if line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 3)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 4:
            raise RuntimeError("Not a valid var line (expected 4, found %i elements): '%s'" % (len(arr), line))

        key = arr[-1]
        return self.add(key, arr[:-1])


# TODO CR190416: Factory operations would like to remove this
#  this was used to retrieve information from IS like BDII
#  ADD ticket
# values are (Type,System,Ref)
class InfoSysDictFile(cWDictFile.DictFile):
    def file_header(self, want_comments):
        if want_comments:
            return (
                cWDictFile.DictFile.file_header(self, want_comments)
                + "\n"
                + ("# %s \t%30s \t%s \t\t%s\n" % ("Type", "Server", "Ref", "ID"))
                + ("#" * 78)
            )
        else:
            return None

    # key can be None
    # in that case it will be composed out of value
    def add(self, key, val, allow_overwrite=0):
        if type(val) not in (type(()), type([])):
            raise RuntimeError("Values '%s' not a list or tuple" % val)
        if len(val) != 3:
            raise RuntimeError("Values '%s' not (Type,System,Ref)" % str(val))

        if key is None:
            key = "%s://%s/%s" % val
        return cWDictFile.DictFile.add(self, key, val, allow_overwrite)

    def add_extended(self, infosys_type, server_name, ref_str, allow_overwrite=0):
        self.add(None, (infosys_type, server_name, ref_str))

    def format_val(self, key, want_comments):
        return "%s \t%30s \t%s \t\t%s" % (self.vals[key][0], self.vals[key][1], self.vals[key][2], key)

    def parse_val(self, line):
        if len(line) == 0:
            return  # ignore emoty lines
        if line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 3)
        if len(arr) == 0:
            return  # empty line
        if len(arr) != 4:
            raise RuntimeError("Not a valid var line (expected 4, found %i elements): '%s'" % (len(arr), line))

        key = arr[-1]
        return self.add(key, arr[:-1])


class CondorJDLDictFile(cWDictFile.DictFile):
    """
    Creating the condor submit file

    NOTE: the 'environment' attribute should be in the new syntax format, to allow characters like ';' in the values
      value all double quoted, var=var_val space separated, var_val can be single quoted

    """

    def __init__(
        self, dir, fname, sort_keys=False, order_matters=False, jobs_in_cluster=None, fname_idx=None
    ):  # if none, use fname
        cWDictFile.DictFile.__init__(self, dir, fname, sort_keys, order_matters, fname_idx)
        self.jobs_in_cluster = jobs_in_cluster

    # append has been replaced by add_environment to ease the quote handling
    # If a generic version is needed, the code can be modified and restored
    # def append(self, key, val):
    #     if key == "environment":
    #         # assumed to be in the new format (quoted)
    #         if key not in self.keys:
    #             self.add(key, val)
    #         else:
    #             # should add some protection about correct quoting
    #             self.add(key, f"{val[:-1]} {self[key][1:]}", True)
    #     else:
    #         raise RuntimeError(f"CondorJDLDictFile append unsupported for key {key} (val: {val})!")

    def add_environment(self, val):
        """Add a variable definition to the "environment" key in the CondorJDLDictFile.
        Defines a new "environment" entry if not there,
        appends to the existing environment if there.
        The whole environment value is enclosed in double quotes (")

        Args:
            val (str): variable definition to add to the environment. Cannot contain double quotes (")
                Single quotes (') are OK and can be used to quote string values
        """
        # TODO: improve environment handling:
        #  - allow ordered dict as input
        #  - handling quoting and escaping, e.g. validate val for double quotes
        #  - formatting and overwriting the environment attribute in the submit file dict
        #    e.g. add a variable already in the environment
        curenv = self.get("environment")
        if curenv:
            if curenv[0] == '"':
                curenv = curenv[1:]
            if curenv[-1] == '"':
                curenv = curenv[:-1]
            curenv += " %s" % val
        else:
            curenv = val
        self.add("environment", '"' + curenv + '"', True)

    def file_footer(self, want_comments):
        if self.jobs_in_cluster is None:
            return "Queue"
        else:
            return "Queue %s" % self.jobs_in_cluster

    def format_val(self, key, want_comments):
        if self.vals[key] == "##PRINT_KEY_ONLY##":
            return "%s" % key
        else:
            return f"{key} = {self.vals[key]}"

    def parse_val(self, line):
        if line[0] == "#":
            return  # ignore comments
        arr = line.split(None, 2)
        if len(arr) == 0:
            return  # empty line
        if arr[0] == "Queue":
            # this is the final line
            if len(arr) == 1:
                # default
                self.jobs_in_cluster = None
            else:
                self.jobs_in_cluster = arr[1]
            return

        if len(arr) <= 2:
            return self.add(arr[0], "")  # key = <empty> or placeholder for env variable
        else:
            return self.add(arr[0], arr[2])

    def is_equal(
        self, other, compare_dir=False, compare_fname=False, compare_keys=None  # other must be of the same class
    ):  # if None, use order_matters
        if self.jobs_in_cluster == other.jobs_in_cluster:
            return cWDictFile.DictFile.is_equal(other, compare_dir, compare_fname, compare_keys)
        else:
            return False


################################################
#
# Functions that create default dictionaries
#
################################################


# internal, do not use from outside the module
def get_common_dicts(submit_dir, stage_dir):
    """Return a dictionary with new instances of all the common (on both global and entry) dictionaries

    Args:
        submit_dir:
        stage_dir:

    Returns:
        dict: dictionary with new instances of all the common (in both global and entry) dictionaries
    """
    common_dicts = {
        "attrs": cWDictFile.ReprDictFile(submit_dir, cgWConsts.ATTRS_FILE),
        "description": cWDictFile.DescriptionDictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.DESCRIPTION_FILE), fname_idx=cWConsts.DESCRIPTION_FILE
        ),
        "consts": cWDictFile.StrDictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.CONSTS_FILE), fname_idx=cWConsts.CONSTS_FILE
        ),
        "params": cWDictFile.ReprDictFile(submit_dir, cgWConsts.PARAMS_FILE),
        "submit": cWDictFile.ReprDictFile(submit_dir, cgWConsts.SUBMIT_ATTRS_FILE),
        "vars": cWDictFile.VarsDictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.VARS_FILE), fname_idx=cWConsts.VARS_FILE
        ),
        "untar_cfg": cWDictFile.StrDictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.UNTAR_CFG_FILE), fname_idx=cWConsts.UNTAR_CFG_FILE
        ),
        "file_list": cWDictFile.FileDictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.FILE_LISTFILE), fname_idx=cWConsts.FILE_LISTFILE
        ),
        "signature": cWDictFile.SHA1DictFile(
            stage_dir, cWConsts.insert_timestr(cWConsts.SIGNATURE_FILE), fname_idx=cWConsts.SIGNATURE_FILE
        ),
    }
    refresh_description(common_dicts)
    return common_dicts


def get_main_dicts(submit_dir, stage_dir):
    """Return a dictionary with new instances of all the main (global) only dictionaries

    Args:
        submit_dir:
        stage_dir:

    Returns:
        dict: dictionary with new instances of all the main (global) only dictionaries
    """
    main_dicts = get_common_dicts(submit_dir, stage_dir)
    main_dicts["summary_signature"] = cWDictFile.SummarySHA1DictFile(submit_dir, cWConsts.SUMMARY_SIGNATURE_FILE)
    main_dicts["glidein"] = cWDictFile.StrDictFile(submit_dir, cgWConsts.GLIDEIN_FILE)
    main_dicts["build_cvmfsexec"] = cWDictFile.ReprDictFile(submit_dir, cgWConsts.CVMFSEXEC_BUILD_FILE)
    main_dicts["frontend_descript"] = cWDictFile.ReprDictFile(submit_dir, cgWConsts.FRONTEND_DESCRIPT_FILE)
    main_dicts["gridmap"] = cWDictFile.GridMapDict(
        stage_dir, cWConsts.insert_timestr(cWConsts.GRIDMAP_FILE)
    )  # TODO: versioned but no fname_idx?
    main_dicts["at_file_list"] = cWDictFile.FileDictFile(
        stage_dir, cWConsts.insert_timestr(cgWConsts.AT_FILE_LISTFILE), fname_idx=cgWConsts.AT_FILE_LISTFILE
    )
    main_dicts["after_file_list"] = cWDictFile.FileDictFile(
        stage_dir, cWConsts.insert_timestr(cgWConsts.AFTER_FILE_LISTFILE), fname_idx=cgWConsts.AFTER_FILE_LISTFILE
    )
    return main_dicts


def get_entry_dicts(entry_submit_dir, entry_stage_dir, entry_name):  # TODO: entry_name seems not used
    """Return a dictionary with new instances of all the entry only dictionaries

    Args:
        entry_submit_dir:
        entry_stage_dir:
        entry_name (str): name of the entry

    Returns:
        dict: dictionary with new instances of all the entry only dictionaries
    """
    entry_dicts = get_common_dicts(entry_submit_dir, entry_stage_dir)
    entry_dicts["job_descript"] = cWDictFile.StrDictFile(entry_submit_dir, cgWConsts.JOB_DESCRIPT_FILE)
    entry_dicts["infosys"] = InfoSysDictFile(entry_submit_dir, cgWConsts.INFOSYS_FILE)
    entry_dicts["mongroup"] = MonitorGroupDictFile(entry_submit_dir, cgWConsts.MONITOR_CONFIG_FILE)
    return entry_dicts


################################################
#
# Functions that load dictionaries
#
################################################


# internal, do not use from outside the module
def load_common_dicts(dicts, description_el):  # update in place
    """Load (from file) the common (to global and entry) dictionaries

    Args:
        dicts (dict): dictionary with the common dictionaries updated in place
                      this dictionary may contain also other (global or entry) dictionaries that are not updated
        description_el:
    """
    # first submit dir ones (mutable)
    dicts["submit"].load()
    dicts["params"].load()
    dicts["attrs"].load()
    # now the ones keyed in the description
    dicts["signature"].load(fname=description_el.vals2["signature"])
    dicts["file_list"].load(fname=description_el.vals2["file_list"])
    file_el = dicts["file_list"]
    # all others are keyed in the file_list
    dicts["consts"].load(fname=file_el[cWConsts.CONSTS_FILE][0])
    dicts["vars"].load(fname=file_el[cWConsts.VARS_FILE][0])
    dicts["untar_cfg"].load(fname=file_el[cWConsts.UNTAR_CFG_FILE][0])
    if "gridmap" in dicts and cWConsts.GRIDMAP_FILE in file_el:
        dicts["gridmap"].load(fname=file_el[cWConsts.GRIDMAP_FILE][0])


def load_main_dicts(main_dicts):  # update in place
    """Load (from file) the main dictionaries
    Loads also the common ones, calling load_common_dicts

    Args:
        main_dicts (dict): dictionary with main (global) dictionaries (updated in place)
    """
    main_dicts["glidein"].load()
    main_dicts["frontend_descript"].load()
    # summary_signature has keys for description
    main_dicts["summary_signature"].load()
    # load the cvmfsexec build
    main_dicts["build_cvmfsexec"].load()
    # load the description
    # print "\ndebug %s main_dicts['summary_signature']['main'][1] = %s" % (__file__, main_dicts['summary_signature']['main'][1])
    main_dicts["description"].load(fname=main_dicts["summary_signature"]["main"][1])
    # all others are keyed in the description
    # print "\ndebug %s main_dicts.items() = %s" % (__file__, main_dicts.items())
    # print "\ndebug %s main_dicts['description'].keys2 = %s" % (__file__, main_dicts['description'].keys2)
    # print "\ndebug %s dir(main_dicts['description']) = %s" % (__file__, dir(main_dicts['description']))
    # TODO: To remove if upgrade from older versions is not a problem
    try:
        main_dicts["at_file_list"].load(fname=main_dicts["description"].vals2["at_file_list"])
    except KeyError:
        # when upgrading form older version the new at_file_list may not be in the description
        main_dicts["at_file_list"].load()
    main_dicts["after_file_list"].load(fname=main_dicts["description"].vals2["after_file_list"])
    load_common_dicts(main_dicts, main_dicts["description"])


def load_entry_dicts(entry_dicts, entry_name, summary_signature):  # update in place
    """Load (from file) the entry dictionaries
    Loads also the common ones, calling load_common_dicts

    Args:
        entry_dicts (dict): dictionary with entry dictionaries updated in place
        entry_name (str): entry name
        summary_signature:
    """
    try:
        entry_dicts["infosys"].load()
    except RuntimeError:
        pass  # ignore errors, this is optional
    entry_dicts["job_descript"].load()
    # load the description (name from summary_signature)
    entry_dicts["description"].load(fname=summary_signature[cgWConsts.get_entry_stage_dir("", entry_name)][1])
    # all others are keyed in the description
    load_common_dicts(entry_dicts, entry_dicts["description"])


############################################################
#
# Functions that create data out of the existing dictionary
#
############################################################


def refresh_description(dicts):  # update in place
    description_dict = dicts["description"]
    description_dict.add(dicts["signature"].get_fname(), "signature", allow_overwrite=True)
    for k in ("file_list", "at_file_list", "after_file_list"):
        if k in dicts:
            description_dict.add(dicts[k].get_fname(), k, allow_overwrite=True)


def refresh_file_list(dicts, is_main, files_set_readonly=True, files_reset_changed=True):  # update in place
    """Update in place the file lists dictionaries

    Args:
        dicts:
        is_main (bool): True if this is the file list for main (and not entries or entry lists)
        files_set_readonly (bool): do not set read only if false
        files_reset_changed (bool): do not reset the changed flag if False

    """
    file_dict = dicts["file_list"]  # FileDictFile
    file_dict.add_from_bytes(
        cWConsts.CONSTS_FILE,
        cWDictFile.FileDictFile.make_val_tuple(dicts["consts"].get_fname(), "regular", config_out="CONSTS_FILE"),
        dicts["consts"].save_into_bytes(set_readonly=files_set_readonly, reset_changed=files_reset_changed),
        allow_overwrite=True,
    )
    file_dict.add_from_bytes(
        cWConsts.VARS_FILE,
        cWDictFile.FileDictFile.make_val_tuple(dicts["vars"].get_fname(), "regular", config_out="CONDOR_VARS_FILE"),
        dicts["vars"].save_into_bytes(set_readonly=files_set_readonly, reset_changed=files_reset_changed),
        allow_overwrite=True,
    )
    file_dict.add_from_bytes(
        cWConsts.UNTAR_CFG_FILE,
        cWDictFile.FileDictFile.make_val_tuple(dicts["untar_cfg"].get_fname(), "regular", config_out="UNTAR_CFG_FILE"),
        dicts["untar_cfg"].save_into_bytes(set_readonly=files_set_readonly, reset_changed=files_reset_changed),
        allow_overwrite=True,
    )
    if is_main and "gridmap" in dicts:
        file_dict.add_from_bytes(
            cWConsts.GRIDMAP_FILE,
            cWDictFile.FileDictFile.make_val_tuple(dicts["gridmap"].get_fname(), "regular", config_out="GRIDMAP"),
            dicts["gridmap"].save_into_bytes(set_readonly=files_set_readonly, reset_changed=files_reset_changed),
            allow_overwrite=True,
        )


# dictionaries must have been written to disk before using this
def refresh_signature(dicts):  # update in place
    signature_dict = dicts["signature"]
    for k in ("consts", "vars", "untar_cfg", "gridmap", "file_list", "at_file_list", "after_file_list", "description"):
        if k in dicts:
            signature_dict.add_from_file(dicts[k].get_filepath(), allow_overwrite=True)
    # add signatures of all the files linked in the lists
    for k in ("file_list", "at_file_list", "after_file_list"):
        if k in dicts:
            filedict = dicts[k]
            for fname in filedict.get_immutable_files():
                signature_dict.add_from_file(os.path.join(filedict.dir, fname), allow_overwrite=True)


################################################
#
# Functions that save dictionaries
#
################################################


# internal, do not use from outside the module
def save_common_dicts(dicts, is_main, set_readonly=True):
    """Save the common dictionaries (in both the main and entry dictionaries lists)
    If they are there, they will be updated in place
    This function calls the save method of each individual dictionary in the common list

    Args:
        dicts (dict): dictionary of all dictionaries
        is_main (bool): True if called while saving the main dictionaries (and not entries or entry lists)
        set_readonly (bool): True (default) to also set the dictionary read only
    """
    # make sure decription is up-to-date
    refresh_description(dicts)
    # save the immutable ones
    for k in ("description",):
        dicts[k].save(set_readonly=set_readonly)
    # Load files into the file list
    # 'consts','untar_cfg','vars' will be loaded
    refresh_file_list(dicts, is_main)
    # save files in the file lists
    for k in ("file_list", "at_file_list", "after_file_list"):
        if k in dicts:
            dicts[k].save_files(allow_overwrite=True)
    # then save the lists
    for k in ("file_list", "at_file_list", "after_file_list"):
        if k in dicts:
            dicts[k].save(set_readonly=set_readonly)
    # calc and save the signatures
    refresh_signature(dicts)
    dicts["signature"].save(set_readonly=set_readonly)

    # finally save the mutable one(s)
    dicts["submit"].save(set_readonly=set_readonly)
    dicts["params"].save(set_readonly=set_readonly)
    dicts["attrs"].save(set_readonly=set_readonly)


# must be invoked after all the entries have been saved
def save_main_dicts(main_dicts, set_readonly=True):  # will update in place, too
    """Save the main dictionaries (corresponding to the global configuration)
    If they are there, they will be updated in place
    This function calls the save method of each individual dictionary in the main list,
    including the common ones by calling `save_common_dicts`

    Args:
        main_dicts (dict): dictionary of all dictionaries
        set_readonly (bool): True (default) to also set the dictionary read only
    """
    main_dicts["glidein"].save(set_readonly=set_readonly)
    main_dicts["frontend_descript"].save(set_readonly=set_readonly)
    main_dicts["build_cvmfsexec"].save(set_readonly=set_readonly)
    save_common_dicts(main_dicts, True, set_readonly=set_readonly)
    summary_signature = main_dicts["summary_signature"]
    summary_signature.add_from_file(
        key="main",
        filepath=main_dicts["signature"].get_filepath(),
        fname2=main_dicts["description"].get_fname(),
        allow_overwrite=True,
    )
    summary_signature.save(set_readonly=set_readonly)


def save_entry_dicts(
    entry_dicts, entry_name, summary_signature, set_readonly=True  # will update in place, too  # update in place
):
    """Save the entry dictionaries (corresponding to the entry configuration)
    If they are there, they will be updated in place
    This function calls the save method of each individual dictionary in the entry list,
    including the common ones by calling `save_common_dicts`

    Args:
        entry_dicts (dict): dictionary of all dictionaries
        entry_name (str): name of the Entry
        summary_signature: summary signature dict file, used to insert the entry sifnature dict file
        set_readonly (bool): True (default) to also set the dictionary read only
    """
    entry_dicts["mongroup"].save(set_readonly=set_readonly)
    entry_dicts["infosys"].save(set_readonly=set_readonly)
    entry_dicts["job_descript"].save(set_readonly=set_readonly)
    save_common_dicts(entry_dicts, False, set_readonly=set_readonly)
    summary_signature.add_from_file(
        key=cgWConsts.get_entry_stage_dir("", entry_name),
        filepath=entry_dicts["signature"].get_filepath(),
        fname2=entry_dicts["description"].get_fname(),
        allow_overwrite=True,
    )


################################################
#
# Functions that reuse dictionaries
#
################################################


def reuse_simple_dict(dicts, other_dicts, key, compare_keys=None):
    if dicts[key].is_equal(other_dicts[key], compare_dir=True, compare_fname=False, compare_keys=compare_keys):
        # if equal, just use the old one, and mark it as unchanged and readonly
        dicts[key] = copy.deepcopy(other_dicts[key])
        dicts[key].changed = False
        dicts[key].set_readonly(True)
        return True
    else:
        return False


def reuse_file_dict(dicts, other_dicts, key):
    dicts[key].reuse(other_dicts[key])
    return reuse_simple_dict(dicts, other_dicts, key)


def reuse_common_dicts(dicts, other_dicts, is_main, all_reused):
    # save the immutable ones
    # check simple dictionaries
    for k in ("consts", "untar_cfg", "vars"):
        all_reused = reuse_simple_dict(dicts, other_dicts, k) and all_reused
    # since the file names may have changed, refresh the file_list
    refresh_file_list(dicts, is_main)
    # check file-based dictionaries
    for k in ("file_list", "at_file_list", "after_file_list"):
        if k in dicts:
            all_reused = reuse_file_dict(dicts, other_dicts, k) and all_reused

    if all_reused:
        # description and signature track other files
        # so they change iff the others change
        for k in ("description", "signature"):
            dicts[k] = copy.deepcopy(other_dicts[k])
            dicts[k].changed = False
            dicts[k].set_readonly(True)

    # check the mutable ones
    for k in ("attrs", "params", "submit"):
        reuse_simple_dict(dicts, other_dicts, k)

    return all_reused


def reuse_main_dicts(main_dicts, other_main_dicts):
    reuse_simple_dict(main_dicts, other_main_dicts, "glidein")
    reuse_simple_dict(main_dicts, other_main_dicts, "build_cvmfsexec")
    reuse_simple_dict(main_dicts, other_main_dicts, "frontend_descript")
    reuse_simple_dict(main_dicts, other_main_dicts, "gridmap")
    all_reused = reuse_common_dicts(main_dicts, other_main_dicts, True, True)
    # will not try to reuse the summary_signature... being in submit_dir
    # can be rewritten and it is not worth the pain to try to prevent it
    return all_reused


def reuse_entry_dicts(entry_dicts, other_entry_dicts, entry_name):
    reuse_simple_dict(entry_dicts, other_entry_dicts, "job_descript")
    reuse_simple_dict(entry_dicts, other_entry_dicts, "infosys")
    all_reused = reuse_common_dicts(entry_dicts, other_entry_dicts, False, True)
    return all_reused


################################################
#
# Handle dicts as Classes
#
################################################


################################################
#
# Support classes
#
################################################


class clientDirSupport(cWDictFile.SimpleDirSupport):
    def __init__(self, user, dir, dir_name):
        cWDictFile.SimpleDirSupport.__init__(self, dir, dir_name)
        self.user = user

    def create_dir(self, fail_if_exists=True):
        base_dir = os.path.dirname(self.dir)
        if not os.path.isdir(base_dir):
            raise RuntimeError(f"Missing base {self.dir_name} directory {base_dir}.")

        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError(f"Cannot create {self.dir_name} dir {self.dir}, already exists.")
            else:
                return False  # already exists, nothing to do

        # keep it simple, if possible
        try:
            os.mkdir(self.dir)
            # with condor 7.9.4 a permissions change is required
            chmod(self.dir, 0o755)
        except glideinwms.lib.subprocessSupport.CalledProcessError as e:
            raise RuntimeError(f"Failed to create {self.dir_name} dir (user {self.user}): {e} ")
        return True

    def delete_dir(self):
        base_dir = os.path.dirname(self.dir)
        if not os.path.isdir(base_dir):
            raise RuntimeError(f"Missing base {self.dir_name} directory {base_dir}!")

        try:
            os.rmdir(self.dir)
        except glideinwms.lib.subprocessSupport.CalledProcessError as e:
            raise RuntimeError(f"Failed to remove {self.dir_name} dir (user {self.user}): {e} ")


class chmodClientDirSupport(clientDirSupport):
    def __init__(self, user, dir, chmod, dir_name):
        clientDirSupport.__init__(self, user, dir, dir_name)
        self.chmod = chmod

    def create_dir(self, fail_if_exists=True):
        base_dir = os.path.dirname(self.dir)
        if not os.path.isdir(base_dir):
            raise RuntimeError(f"Missing base {self.dir_name} directory {base_dir}.")

        if os.path.isdir(self.dir):
            if fail_if_exists:
                raise RuntimeError(f"Cannot create {self.dir_name} dir {self.dir}, already exists.")
            else:
                return False  # already exists, nothing to do

        try:
            os.mkdir(self.dir)
            # with condor 7.9.4 a permissions change is required
            chmod(self.dir, self.chmod)
        except glideinwms.lib.subprocessSupport.CalledProcessError as e:
            raise RuntimeError(f"Failed to create {self.dir_name} dir (user {self.user}): {e} ")
        return True


###########################################
# Support classes used my Main


class baseClientDirSupport(cWDictFile.MultiSimpleDirSupport):
    def __init__(self, user, dir, dir_name="client"):
        cWDictFile.MultiSimpleDirSupport.__init__(self, (), dir_name)
        self.user = user

        self.base_dir = os.path.dirname(dir)
        if not os.path.isdir(self.base_dir):
            # Parent does not exist
            # This is the user base directory
            # In order to make life easier for the factory admins, create it automatically when needed
            self.add_dir_obj(clientDirSupport(user, self.base_dir, "base %s" % dir_name))

        self.add_dir_obj(clientDirSupport(user, dir, dir_name))


class clientSymlinksSupport(cWDictFile.MultiSimpleDirSupport):
    def __init__(self, user_dirs, work_dir, symlink_base_subdir, dir_name):
        self.symlink_base_dir = os.path.join(work_dir, symlink_base_subdir)
        cWDictFile.MultiSimpleDirSupport.__init__(self, (self.symlink_base_dir,), dir_name)
        for user in list(user_dirs.keys()):
            self.add_dir_obj(
                cWDictFile.SymlinkSupport(
                    user_dirs[user], os.path.join(self.symlink_base_dir, "user_%s" % user), dir_name
                )
            )


###########################################
# Support classes used my Entry


class clientLogDirSupport(clientDirSupport):
    def __init__(self, user, log_dir, dir_name="clientlog"):
        clientDirSupport.__init__(self, user, log_dir, dir_name)


class clientProxiesDirSupport(chmodClientDirSupport):
    def __init__(self, user, proxies_dir, proxiesdir_name="clientproxies"):
        chmodClientDirSupport.__init__(self, user, proxies_dir, 0o700, proxiesdir_name)


################################################
#
# This Class contains the main dicts
#
################################################


class glideinMainDicts(cWDictFile.FileMainDicts):
    def __init__(self, work_dir, stage_dir, workdir_name, log_dir, client_log_dirs, client_proxies_dirs):
        cWDictFile.FileMainDicts.__init__(
            self, work_dir, stage_dir, workdir_name, False, log_dir  # simple_work_dir=False
        )
        self.client_log_dirs = client_log_dirs
        for user in list(client_log_dirs.keys()):
            self.add_dir_obj(baseClientDirSupport(user, client_log_dirs[user], "clientlog"))

        self.client_proxies_dirs = client_proxies_dirs
        for user in client_proxies_dirs:
            self.add_dir_obj(baseClientDirSupport(user, client_proxies_dirs[user], "clientproxies"))

        # make them easier to find; create symlinks in work/client_proxies
        self.add_dir_obj(clientSymlinksSupport(client_log_dirs, work_dir, "client_log", "clientlog"))
        self.add_dir_obj(clientSymlinksSupport(client_proxies_dirs, work_dir, "client_proxies", "clientproxies"))

    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_main_dicts(self.dicts)

    def save(self, set_readonly=True):
        save_main_dicts(self.dicts, set_readonly=set_readonly)

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        cWDictFile.FileMainDicts.reuse(self, other)
        reuse_main_dicts(self.dicts, other.dicts)

    ####################
    # Internal
    ####################

    def get_daemon_log_dir(self, base_dir):
        return os.path.join(base_dir, "factory")

    # Child must overwrite this
    def get_main_dicts(self):
        return get_main_dicts(self.work_dir, self.stage_dir)


################################################
#
# This Class contains the entry and entry set dicts
#
################################################


class glideinEntryDicts(cWDictFile.FileSubDicts):
    """This Class contains the entry and entry set dicts"""

    def __init__(
        self,
        base_work_dir,
        base_stage_dir,
        sub_name,
        summary_signature,
        workdir_name,
        base_log_dir,
        base_client_log_dirs,
        base_client_proxies_dirs,
    ):
        """Constructor

        Args:
            base_work_dir (str): base (not entry) work directory name
            base_stage_dir (str): base stage directory name
            sub_name (str): Entry name
            summary_signature (_type_): _description_
            workdir_name (str): work directory name
            base_log_dir (str): base log directory name
            base_client_log_dirs (str): base client log directory name
            base_client_proxies_dirs (str): base client credentials directory name
        """
        cWDictFile.FileSubDicts.__init__(
            self,
            base_work_dir,
            base_stage_dir,
            sub_name,
            summary_signature,
            workdir_name,
            False,  # simple_work_dir=False
            base_log_dir,
        )

        for user in list(base_client_log_dirs.keys()):
            self.add_dir_obj(
                clientLogDirSupport(user, cgWConsts.get_entry_userlog_dir(base_client_log_dirs[user], sub_name))
            )

        for user in base_client_proxies_dirs:
            self.add_dir_obj(
                clientProxiesDirSupport(
                    user, cgWConsts.get_entry_userproxies_dir(base_client_proxies_dirs[user], sub_name)
                )
            )

    ######################################
    # Redefine methods needed by parent
    def load(self):
        load_entry_dicts(self.dicts, self.sub_name, self.summary_signature)

    def save(self, set_readonly=True):
        save_entry_dicts(self.dicts, self.sub_name, self.summary_signature, set_readonly=set_readonly)

    def save_final(self, set_readonly=True):
        pass  # nothing to do

    # reuse as much of the other as possible
    def reuse(self, other):  # other must be of the same class
        cWDictFile.FileSubDicts.reuse(self, other)
        reuse_entry_dicts(self.dicts, other.dicts, self.sub_name)

    ####################
    # Internal
    ####################

    def get_sub_work_dir(self, base_dir):
        return cgWConsts.get_entry_submit_dir(base_dir, self.sub_name)

    def get_sub_log_dir(self, base_dir):
        return cgWConsts.get_entry_log_dir(base_dir, self.sub_name)

    def get_sub_stage_dir(self, base_dir):
        return cgWConsts.get_entry_stage_dir(base_dir, self.sub_name)

    def get_sub_dicts(self):
        return get_entry_dicts(self.work_dir, self.stage_dir, self.sub_name)

    def reuse_nocheck(self, other):
        reuse_entry_dicts(self.dicts, other.dicts, self.sub_name)


################################################
#
# This Class contains the main,the entry dicts
# and the entry set dicts
#
################################################


class glideinDicts(cWDictFile.FileDicts):
    def __init__(
        self, work_dir, stage_dir, log_dir, client_log_dirs, client_proxies_dirs, entry_list=[], workdir_name="submit"
    ):
        self.client_log_dirs = client_log_dirs
        self.client_proxies_dirs = client_proxies_dirs
        cWDictFile.FileDicts.__init__(
            self, work_dir, stage_dir, entry_list, workdir_name, False, log_dir  # simple_work_dir=False
        )

    ###########
    # PRIVATE
    ###########

    ######################################
    # Redefine methods needed by parent
    def new_MainDicts(self):
        return glideinMainDicts(
            self.work_dir,
            self.stage_dir,
            self.workdir_name,
            self.log_dir,
            self.client_log_dirs,
            self.client_proxies_dirs,
        )

    def new_SubDicts(self, sub_name):
        return glideinEntryDicts(
            self.work_dir,
            self.stage_dir,
            sub_name,
            self.main_dicts.get_summary_signature(),
            self.workdir_name,
            self.log_dir,
            self.client_log_dirs,
            self.client_proxies_dirs,
        )

    def get_sub_name_from_sub_stage_dir(self, sign_key):
        return cgWConsts.get_entry_name_from_entry_stage_dir(sign_key)
