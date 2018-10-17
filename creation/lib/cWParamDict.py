from __future__ import absolute_import
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
import string
from . import cWConsts
from . import cWDictFile


def is_true(s):
    """Case insensitive string parsing helper. Return True for true (case insensitive matching), False otherwise."""
    return s.lower() == 'true'


def has_file_wrapper(dicts):
    for file_dict in ['preentry_file_list', 'file_list', 'aftergroup_preentry_file_list', 'aftergroup_file_list']:
        if file_dict in dicts:
            # dicts[file_dict] contains information about status, ..., vals are the tuples w/ files info and content
            # tuples are (fname, type, ...)
            for file_info in dicts[file_dict].vals.values():
                if file_info[1] == 'wrapper':
                    return True
    return False


def has_file_wrapper_params(file_params):
    # file_params is the list in a files section (global o group): each one is a file specification
    # If there is one wrapper return true
    for user_file in file_params:
        if is_true(user_file.wrapper):
            return True
    return False


def add_file_unparsed(user_file, dicts, is_factory):
    """Add a user file residing in the stage area
    file as described by Params.file_defaults
    :param user_file: file from the config files "files" sections
    :param dicts: parameters dctionaries
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
    is_executable = is_true(user_file.executable)
    is_wrapper = is_true(user_file.wrapper)
    do_untar = is_true(user_file.untar)
    try:
        period_value = int(user_file.period)
    except (AttributeError, KeyError, ValueError):
        period_value = 0

    if is_factory:
        # Factory (file_list, after_file_list)
        file_list_idx = 'file_list'
        if 'after_entry' in user_file:
            if is_true(user_file.after_entry):  # eval(user_file.after_entry,{},{}):
                file_list_idx = 'after_file_list'
    else:
        # Frontend (preentry_file_list, file_list, aftergroup_preentry_file_list, aftergroup_file_list)
        file_list_idx = 'preentry_file_list'
        if 'after_entry' in user_file:
            if is_true(user_file.after_entry):
                file_list_idx = 'file_list'

        if 'after_group' in user_file:
            if is_true(user_file.after_group):
                file_list_idx = 'aftergroup_%s' % file_list_idx

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
        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), 'exec',
                                                                                  user_file.period, user_file.prefix),
                                           absfname)

    elif is_wrapper:  # a sourceable script for the wrapper
        if not is_const:
            raise RuntimeError("A file cannot be a wrapper if it is not constant: %s" % user_file)
        if do_untar:
            raise RuntimeError("A tar file cannot be a wrapper: %s" % user_file)
        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), 'wrapper'),
                                           absfname)
    elif do_untar:  # a tarball
        if not is_const:
            raise RuntimeError("A file cannot be untarred if it is not constant: %s" % user_file)

        wnsubdir = user_file.untar_options.dir
        if wnsubdir is None:
            wnsubdir = string.split(relfname, '.', 1)[0]  # default is relfname up to the first .

        config_out = user_file.untar_options.absdir_outattr
        if config_out is None:
            config_out = "FALSE"
        cond_attr = user_file.untar_options.cond_attr

        dicts[file_list_idx].add_from_file(relfname,
                                           cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname),
                                                                                  'untar',
                                                                                  cond_download=cond_attr,
                                                                                  config_out=config_out),
                                           absfname)
        dicts['untar_cfg'].add(relfname, wnsubdir)

    else:  # not executable nor tarball => simple file
        if is_const:
            val = 'regular'
            dicts[file_list_idx].add_from_file(relfname,
                                               cWDictFile.FileDictFile.make_val_tuple(cWConsts.insert_timestr(relfname), val),
                                               absfname)
        else:
            val = 'nocache'
            dicts[file_list_idx].add_from_file(relfname, cWDictFile.FileDictFile.make_val_tuple(relfname, val),
                                               absfname)  # no timestamp in the name if it can be modified
