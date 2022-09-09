# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Frontend creation module
#   Classes and functions needed to handle dictionary files
#   created out of the parameter object
#
#   Common functions for cvWParamDict and cgWParamDict
#

import os.path

from . import cWConsts, cWDictFile


def is_true(s):
    """Case insensitive string parsing helper. Return True for true (case insensitive matching), False otherwise."""
    return type(s) == str and s.lower() == "true"


def has_file_wrapper(dicts):
    for file_dict in ["preentry_file_list", "file_list", "aftergroup_preentry_file_list", "aftergroup_file_list"]:
        if file_dict in dicts:
            # dicts[file_dict] contains information about status, ..., vals are the tuples w/ files info and content
            # tuples are (fname, type, ...)
            for file_info in list(dicts[file_dict].vals.values()):
                if file_info[1] == "wrapper":
                    return True
    return False


def has_file_wrapper_params(file_params):
    # file_params is the list in a files section (global o group): each one is a file specification
    # If there is one wrapper return true
    for user_file in file_params:
        if user_file.type == "wrapper":
            return True
    return False


def add_file_unparsed(user_file, dicts, is_factory):
    """Add a user file residing in the stage area
    file as described by Params.file_defaults
    :param user_file: file from the config files "files" sections
    :param dicts: parameters dictionaries
    :param is_factory: True if invoked for the factory (cgWParamDict.py), false for the frontend (cvWParamDict.py)
    :return: None (dictionaries are modified)
    """

    absfname = user_file.absfname
    if absfname is None:
        raise RuntimeError("Found a file element without an absname: %s" % user_file)
    relfname = user_file.relfname
    if relfname is None:
        relfname = os.path.basename(absfname)  # default is the final part of absfname
    if len(relfname) < 1:
        raise RuntimeError("Found a file element with an empty relfname: %s" % user_file)

    is_const = is_true(user_file.const)
    is_executable = user_file.type.startswith("exec") or user_file.type.startswith("run")
    is_wrapper = user_file.type == "wrapper"
    is_source = user_file.type.startswith("source")
    is_library = user_file.type.startswith("library")
    is_periodic = user_file.time.startswith("periodic")
    do_untar = user_file.type.startswith("untar")

    time = user_file.time
    if is_executable or is_source or is_library:
        if (
            not time.startswith("startup")
            and not time.startswith("cleanup")
            and not time.startswith("after_job")
            and not time.startswith("before_job")
            and not time.startswith("periodic:")
            and not time.startswith("milestone:")
            and not time.startswith("failure:")
            and not time.startswith("no_time")
        ):
            # we use startswith since we may have combination of time phases (e.g. startup, cleanup)
            raise RuntimeError("The file does not have a valid time phase value: %s" % user_file)

    try:
        if user_file.is_periodic:
            period = int(user_file.time.split(":")[1])
        else:
            period = 0
    except (AttributeError, KeyError, ValueError, TypeError):
        period = 1000  # default 1000ms

    if is_periodic and not is_executable:
        raise RuntimeError("A file cannot have an execution period if it is not executable: %s" % user_file)

    priority = int(user_file.priority)
    if priority < 0 or priority > 99:
        raise RuntimeError("Priority value out of the range [0,99]: %s" % user_file)

    prefix = user_file.prefix

    cond_download = user_file.cond_download

    tar_source = user_file.tar_source
    if tar_source is None:
        tar_source = "NULL"

    try:
        config_out = user_file.config_out
        if config_out is None:
            config_out = "FALSE"     
    except (AttributeError, KeyError, ValueError, TypeError):
        config_out = "FALSE"

    cond_attr = user_file.cond_attr

    absdir_outattr = user_file.absdir_outattr

    if is_factory:
        # Factory (file_list, after_file_list)
        file_list_idx = "file_list"
        if "priority" in user_file:
            if priority >= 60:
                file_list_idx = "after_file_list"
    else:
        # Frontend (preentry_file_list, file_list, aftergroup_preentry_file_list, aftergroup_file_list)
        file_list_idx = "preentry_file_list"
        if "priority" in user_file:
            if priority >= 80:
                file_list_idx = "aftergroup_%s" % file_list_idx
            elif priority >= 60:
                file_list_idx = "file_list"

    if is_executable:  # a script
        if not is_const:
            raise RuntimeError("A file cannot be executable if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be executable: %s" % user_file)
        if is_wrapper:
            raise RuntimeError("A wrapper file cannot be an executable: %s" % user_file)

        file_type = "exec"
        if user_file.type:
            if (
                user_file.type == "exec:s"
                or user_file.type == "exec:singularity"
                or user_file.type == "run:s"
                or user_file.type == "run:singularity"
            ):
                if file_list_idx.endswith("preentry_file_list"):
                    raise RuntimeError("An executable cannot use singularity before the entry setup: %s" % user_file)
                file_type = "exec:s"
            else:
                if not user_file.type.startswith("run") and not user_file.type.startswith("exec"):
                    raise RuntimeError("An executable file type must start with 'run' or 'exec': $s" % user_file)
        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname),
                file_type,
                prefix,
                time,
                period,
                priority,
                cond_download,
                tar_source,
                config_out,
                cond_attr,
                absdir_outattr,
            ),
            absfname,
        )
    elif is_wrapper:  # a source-able script for the wrapper
        if not is_const:
            raise RuntimeError("A file cannot be a wrapper if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be a wrapper: %s" % user_file)
        if is_source:
            raise RuntimeError("A source file cannot be a wrapper: %s" % user_file)
        if is_library:
            raise RuntimeError("A library file cannot be a wrapper: %s" % user_file)
        if is_periodic:
            raise RuntimeError("A wrapper file cannot be periodic: %s" % user_file)
        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname),
                "wrapper",
                tar_source=user_file.tar_source,
                cond_download=cond_download,
                config_out=config_out,
                cond_attr=cond_attr,
                absdir_outattr=absdir_outattr,
            ),
            absfname,
        )

    elif do_untar:  # a tarball
        if not is_const:
            raise RuntimeError("A file cannot be untarred if it is not constant: %s" % user_file)
        if is_periodic:
            raise RuntimeError("A tar file cannot be periodic: %s" % user_file)
        if is_library:
            raise RuntimeError("A tar file cannot be a library: %s" % user_file)
        if is_executable:
            raise RuntimeError("A tar file cannot be executable: %s" % user_file)
        if is_wrapper:
            raise RuntimeError("A tar file cannot be a wrapper: %s" % user_file)

        wnsubdir = user_file.type.split(":")[1]
        if wnsubdir is None:
            wnsubdir = relfname  # default is relfname up to the first

        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname),
                "untar",
                cond_download=cond_download,
                config_out=config_out,
                cond_attr=cond_attr,
                absdir_outattr=absdir_outattr,
            ),
            absfname,
        )
        # dicts["untar_cfg"].add(relfname, wnsubdir)
    elif is_source:
        if not is_const:
            raise RuntimeError("A file cannot be sourced if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be sourced: %s" % user_file)
        if is_wrapper:
            raise RuntimeError("A wrapper file cannot be an sourced: %s" % user_file)
        if is_periodic:
            raise RuntimeError("A source file cannot be periodic: %s" % user_file)
        if is_library:
            raise RuntimeError("A source file cannot be a library: %s" % user_file)

        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname),
                "source",
                tar_source=tar_source,
                time=time,
                priority=priority,
                cond_download=cond_download,
                config_out=config_out,
                cond_attr=cond_attr,
                absdir_outattr=absdir_outattr,
            ),
            absfname,
        )

    elif is_library:
        if not is_const:
            raise RuntimeError("A file cannot be a library if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be a library: %s" % user_file)
        if is_wrapper:
            raise RuntimeError("A wrapper file cannot be an a library: %s" % user_file)
        if is_periodic:
            raise RuntimeError("A library file cannot be periodic: %s" % user_file)

        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname),
                user_file.type,
                tar_source=tar_source,
                time=time,
                priority=priority,
                cond_download=cond_download,
                config_out=config_out,
                cond_attr=cond_attr,
                absdir_outattr=absdir_outattr,
            ),
            absfname,
        )
        # user_file.type can be library:x

    else:
        # not executable nor tarball => simple file
        if is_const:
            val = "regular"
            dicts[file_list_idx].add_from_file(
                relfname, cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), val), absfname
            )
        else:
            val = "nocache"
            dicts[file_list_idx].add_from_file(
                relfname, cWDictFile.FileDictFile.make_val_tuple(relfname, val), absfname
            )  # no timestamp in the name if it can be modified
