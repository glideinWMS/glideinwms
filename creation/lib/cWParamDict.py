# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Classes and functions needed to handle dictionary files created out of the parameter object

Common functions for cvWParamDict (Frontend/client) and cgWParamDict (Factory)
"""


import os.path

from glideinwms.lib.util import is_true

from . import cWConsts, cWDictFile


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
        if is_true(user_file.wrapper):
            return True
    return False


def validate_wrapper_file(file_path):
    """Verifies that a wrapper file exists, is readable, and prints warnings to stdout
    if the shebang line requires bash or the file includes an exec() command.

    Glidein job wrappers should be segments of code compatible with 'sh' (bash presence is not guaranteed),
    and they should not include an exec() command, because multiple segments are possible. The Glidein infrastructure
    takes care of exec-ing the user job after all Glidein wrappers.

    This code is invoked during the reconfig or upgrade commands, so the warnings are printed to stdout.
    These are warnings, not severe enough to block the reconfig/upgrade with a RuntimeError

    Args:
        file_path (str): Path to the file to be verified

    Returns:
        bool: False if the file does not exist, is not readable, has a shebang requiring something different from sh,
            or contains an exec statement, True otherwise.

    """
    if not file_path or not os.path.isfile(file_path):
        return False
    retval = True
    try:
        with open(file_path) as f:
            shebang = f.readline().strip()
            if shebang.startswith("#!"):
                if not shebang.endswith("/sh") and not shebang.endswith(" sh"):
                    print(
                        f"WARNING: the shebang line in the Glidein job wrapper '{file_path}' requires a shell different from sh."
                        "You may have trouble with some containers."
                    )
                    retval = False
            for line in f:
                if line.startswith("exec "):
                    print(
                        f"WARNING: the Glidein job wrapper '{file_path}' contains an exec statement."
                        "This will interfere with the execution of other wrappers and override the final exec statement."
                        "Use GLIDEIN_WRAPPER_EXEC for customizations."
                    )
                    retval = False
    except (FileNotFoundError, PermissionError):
        return False
    return retval


def add_file_unparsed(user_file, dicts, is_factory):
    """Adds a user file residing in the staging area to the appropriate internal dictionary.

    This function processes a file element defined in the configuration, categorizes it
    (e.g., executable, wrapper, untar, regular), and inserts it into the correct section of
    the parameter dictionaries. It handles both Factory and Frontend (client) contexts.

    Args:
        user_file (object): A file configuration object from the "files" section of the XML config.
        dicts (dict): A set of internal parameter dictionaries that will be modified by this function.
        is_factory (bool): True if invoked in the Factory context (e.g., `cgWParamDict.py`),
            False if invoked in the Frontend (client) context (e.g., `cvWParamDict.py`).

    Returns:
        None: The function modifies the provided `dicts` in place.

    Raises:
        RuntimeError: If the file configuration is invalid (e.g., missing paths, conflicting flags, or
            incompatible type combinations such as an executable tar file or a wrapper marked non-constant).
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
    is_executable = is_true(user_file.executable)
    is_config = False
    if user_file.type:
        is_config = user_file.type.startswith("config")
    is_wrapper = is_true(user_file.wrapper)
    do_untar = is_true(user_file.untar)
    try:
        period_value = int(user_file.period)
    except (AttributeError, KeyError, ValueError, TypeError):
        period_value = 0

    if is_factory:
        # Factory (file_list, after_file_list)
        file_list_idx = "file_list"
        if "after_entry" in user_file:
            if is_true(user_file.after_entry):  # eval(user_file.after_entry,{},{}):
                file_list_idx = "after_file_list"
    else:
        # Frontend (preentry_file_list, file_list, aftergroup_preentry_file_list, aftergroup_file_list)
        file_list_idx = "preentry_file_list"
        if "after_entry" in user_file:
            if is_true(user_file.after_entry):
                file_list_idx = "file_list"

        if "after_group" in user_file:
            if is_true(user_file.after_group):
                file_list_idx = "aftergroup_%s" % file_list_idx

    # period has 0 as default (in dictionary definition). Should I still protect against it not being defined?
    if period_value > 0:
        if not is_executable:
            raise RuntimeError("A file cannot have an execution period if it is not executable: %s" % user_file)

    if is_executable:  # a script
        if not is_const:
            raise RuntimeError("A file cannot be executable if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be executable: %s" % user_file)
        if is_wrapper:
            raise RuntimeError("A wrapper file cannot be an executable: %s" % user_file)
        file_type = "exec"
        if user_file.type:
            if user_file.type == "run:s" or user_file.type == "run:singularity":
                if file_list_idx.endswith("preentry_file_list"):
                    raise RuntimeError("An executable cannot use singularity before the entry setup: %s" % user_file)
                file_type = "exec:s"
            else:
                if not user_file.type.startswith("run"):
                    raise RuntimeError("An executable file type must start with 'run': $s" % user_file)
        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname), file_type, user_file.period, user_file.prefix
            ),
            absfname,
        )
    elif is_config:  # a configuration file (e.g. HTCondor config)
        file_type = user_file.type
        if file_type == "config:condor" or file_type == "config":
            file_type = "config:c"
        dicts[file_list_idx].add_from_file(
            relfname, cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), file_type), absfname
        )
    elif is_wrapper:  # a source-able script for the wrapper
        if not is_const:
            raise RuntimeError("A file cannot be a wrapper if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be a wrapper: %s" % user_file)
        # The wrapper file is checked for shebang and exec commands. Warnings are printed to stdout.
        validate_wrapper_file(absfname)
        dicts[file_list_idx].add_from_file(
            relfname, cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), "wrapper"), absfname
        )
    elif do_untar:  # a tarball
        if not is_const:
            raise RuntimeError("A file cannot be untarred if it is not constant: %s" % user_file)

        wnsubdir = user_file.untar_options.dir
        if wnsubdir is None:
            wnsubdir = relfname.split(".", 1)[0]  # default is relfname up to the first .

        config_out = user_file.untar_options.absdir_outattr
        if config_out is None:
            config_out = "FALSE"
        cond_attr = user_file.untar_options.cond_attr

        dicts[file_list_idx].add_from_file(
            relfname,
            cWDictFile.FileDictFile.make_val_tuple(
                cWConsts.insert_timestr(relfname), "untar", cond_download=cond_attr, config_out=config_out
            ),
            absfname,
        )
        dicts["untar_cfg"].add(relfname, wnsubdir)

    else:  # not executable nor tarball => simple file
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
