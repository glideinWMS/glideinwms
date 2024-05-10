# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the generic params classes
"""

import copy
import os
import os.path
import string
import sys
import xml.parsers.expat

from collections.abc import Mapping

from glideinwms.lib import xmlFormat, xmlParse
from glideinwms.lib.util import chmod
from glideinwms.lib.xmlParse import OrderedDict


class SubParams(Mapping):
    """Read-only dictionary containing Configuration info"""

    def __init__(self, data):
        """Constructor, only method changing the value"""
        self.data = data

    def __repr__(self):
        return self.data.__repr__()

    # Abstract methods to implement for the Mapping
    def __getitem__(self, key):
        return self.__get_el(key)

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __getattr__(self, name):
        """Make data elements look like class attributes

        This is called if the interpreter failed to reference an attribute

        Args:
            name (str): attribute name

        Returns:
            attribute value

        Returns:
            AttributeError: if looking for 'data' or protected attributes that have not been defined in the class
        """
        if name == "data":
            # needed because copy/deepcopy and pickle call __getattr__ on objects that have not been initialized
            # they will catch and ignore the AttributeError exception
            raise AttributeError("%r has no attribute data: the init method has not been called" % type(self))
        # work around for pickle bug in Python 3.4
        # see http://bugs.python.org/issue16251
        if name == "__getnewargs_ex__" or name == "__getnewargs__":
            raise AttributeError(f"{type(self)!r} has no attribute {name!r}")
        if name == "__deepcopy__" or name == "__copy__":
            raise AttributeError(f"{type(self)!r} has no attribute {name!r}")
        # if not name in self.data:
        if name.startswith("__"):
            raise AttributeError(f"{type(self)!r} has no attribute {name!r}")
        return self.__get_el(name)

    #
    # PROTECTED
    #

    def validate(self, base, path_text):
        """Validate input against base template (i.e. the defaults)

        Args:
            base:
            path_text:

        Returns:

        """
        for k in self.data:
            # TODO: MMBFIX is the next line doing anything? should it be removed? check history?
            self.data
            if k not in base:
                # element not in base, report
                raise RuntimeError(f"Unknown parameter {path_text}.{k}")
            else:
                # verify sub-elements, if any
                defel = base[k]
                if isinstance(defel, OrderedDict):
                    # subdictionary
                    self[k].validate(defel, f"{path_text}.{k}")
                else:
                    # final element
                    defvalue, ktype, txt, subdef = defel

                    if isinstance(defvalue, OrderedDict):
                        # dictionary el elements
                        data_el = self[k]
                        for data_subkey in list(data_el.keys()):
                            data_el[data_subkey].validate(subdef, f"{path_text}.{k}.{data_subkey}")
                    elif isinstance(defvalue, list):
                        # list of elements
                        if isinstance(self.data[k], OrderedDict):
                            if len(list(self.data[k].keys())) == 0:
                                self.data[k] = (
                                    []
                                )  # XML does not know if an empty list is a dictionary or not.. fix this

                        mylist = self[k]
                        if not isinstance(mylist, list):
                            raise RuntimeError(f"Parameter {path_text}.{k} not a list: {type(mylist)} {mylist}")
                        for data_el in mylist:
                            data_el.validate(subdef, f"{path_text}.*.{k}")
                    else:
                        # a simple value
                        pass  # nothing to be done

    def use_defaults(self, defaults):
        """Put default values where there is nothing

        Args:
            defaults:

        Returns:

        """
        for k in list(defaults.keys()):
            defel = defaults[k]
            if isinstance(defel, OrderedDict):
                # subdictionary
                if k not in self.data:
                    self.data[k] = OrderedDict()  # first create empty, if does not exist

                # then, set defaults on all elements of subdictionary
                self[k].use_defaults(defel)
            else:
                # final element
                defvalue, ktype, txt, subdef = defel

                if isinstance(defvalue, OrderedDict):
                    # dictionary el elements
                    if k not in self.data:
                        self.data[k] = OrderedDict()  # no elements yet, set and empty dictionary
                    else:
                        # need to set defaults on all elements in the dictionary
                        data_el = self[k]
                        for data_subkey in list(data_el.keys()):
                            data_el[data_subkey].use_defaults(subdef)
                elif isinstance(defvalue, list):
                    # list of elements
                    if k not in self.data:
                        self.data[k] = []  # no elements yet, set and empty list
                    else:
                        # need to set defaults on all elements in the list
                        for data_el in self[k]:
                            data_el.use_defaults(subdef)
                else:
                    # a simple value
                    if k not in self.data:
                        self.data[k] = copy.deepcopy(defvalue)
                    # else nothing to do, already set

    #
    # PRIVATE
    #
    def __get_el(self, name):
        """Element getter, used by both __getitem__ and __getattr__

        Args:
            name (str): key or attribute name

        Returns:
            value

        Raises:
            KeyError: when the key/attribute name is not in self.data

        """
        try:
            el = self.data[name]
        except KeyError:
            # This function is used also in __getattr__ which is expected to raise AttributeError
            # Some methods with workarounds or defaults for missing attributes (hasattr, getattr, ...)
            # do expect AttributeError and not KeyError
            raise  # AttributeError("%s object has no attribute/key %s" % (type(self), name))
        if isinstance(el, OrderedDict):
            return self.__class__(el)
        elif isinstance(el, list):
            outlst = []
            for k in el:
                if isinstance(k, OrderedDict):
                    outlst.append(self.__class__(k))
                else:
                    outlst.append(k)
            return outlst
        else:
            return el


class Params:
    """abstract class

    Children must define:
        get_top_element(self)
        init_defaults(self)
        derive(self)
        get_xml_format(self)

    """

    def __init__(self, usage_prefix, src_dir, argv):
        """Constructor. Load the default values and override with the config file content

        Args:
            usage_prefix:
            src_dir (str): source directory of the config file(s)
            argv (list): TODO: this way for historical reasons, should probably be refactored
                            [0] is the caller, sys.argv[0] (NOT USED)
                            [1] can be the config file or '-help'
                            it seems the length used is always 2, other elements are NOT USED
        """
        self.usage_prefix = usage_prefix

        # support dir
        self.src_dir = src_dir

        # initialize the defaults
        self.defaults = OrderedDict()
        self.init_defaults()

        try:
            if len(argv) < 2:
                raise RuntimeError("Missing config file")

            if argv[1] == "-help":
                raise RuntimeError(
                    "\nA config file will contain:\n%s\n\nThe config file will be in XML format."
                    % self.get_description("  ")
                )

            self.cfg_name = os.path.abspath(argv[1])
            self.load_file(self.cfg_name)

            self.subparams.validate(self.defaults, self.get_top_element())

            # make a copy of the loaded data, so that I can always tell what was derived and what was not
            self.org_data = copy.deepcopy(self.data)

            self.subparams.use_defaults(self.defaults)

            # create derived values
            self.derive()
        except RuntimeError as e:
            raise RuntimeError("Unexpected error occurred loading the configuration file.\n\n%s" % e) from e

    def derive(self):
        return  # by default nothing... children should overwrite this

    def get_xml(self):
        old_default_ignore_nones = xmlFormat.DEFAULT_IGNORE_NONES
        old_default_lists_params = xmlFormat.DEFAULT_LISTS_PARAMS
        old_default_dicts_params = xmlFormat.DEFAULT_DICTS_PARAMS
        xmlFormat.DEFAULT_IGNORE_NONES = True
        # these are used internally, do not need to be ordered
        xml_format = self.get_xml_format()
        xmlFormat.DEFAULT_LISTS_PARAMS = xml_format["lists_params"]
        xmlFormat.DEFAULT_DICTS_PARAMS = xml_format["dicts_params"]
        # hack needed to make xmlFormat to properly do the formating, using override_dictionary_type
        dict_override = type(OrderedDict())
        out = xmlFormat.class2string(self.data, self.get_top_element(), override_dictionary_type=dict_override)
        xmlFormat.DEFAULT_IGNORE_NONES = old_default_ignore_nones
        xmlFormat.DEFAULT_LISTS_PARAMS = old_default_lists_params
        xmlFormat.DEFAULT_DICTS_PARAMS = old_default_dicts_params
        return out

    def get_description(self, indent="", width=80):
        return defdict2string(self.defaults, indent, width)

    def load_file(self, fname):
        """Load from a file
        one element per line
         -opt val

        Args:
            fname:

        Returns:

        """
        if fname == "-":
            fname = sys.stdin
        try:
            self.data = xmlParse.xmlfile2dict(fname, use_ord_dict=True)
        except xml.parsers.expat.ExpatError as e:
            raise RuntimeError("XML error parsing config file: %s" % e) from e
        except OSError as e:
            raise RuntimeError("Config file error: %s" % e) from e
        self.subparams = self.get_subparams_class()(self.data)
        return

    def __eq__(self, other):
        if other is None:
            return False
        if not isinstance(other, Params):
            return False
        return self.subparams == other.subparams

    def __getattr__(self, name):
        """__getattr__ is called if the object (Params subclass) has not the 'name' attribute
        Return the attribute from the included SubParam objects (self.subparams)

        Args:
            name (str): name of the attribute

        Returns:
            value of the attribute

        Raises:
            AttributeError: when subparams is requested

        """
        if name == "subparams":
            # if there is no subparams, it cannot be used to retrieve values (of itself!)
            # this can happen w/ deepcopy or pickle, where __init__ is not called
            raise AttributeError(f"{type(self)!r} has no attribute {name!r}")
        return self.subparams.__getattr__(name)

    def save_into_file(self, fname, set_ro=False):
        """Save into a file
        The file should be usable for reload

        Args:
            fname:
            set_ro:

        Returns:

        """
        with open(fname, "w") as fd:
            fd.write(self.get_xml())
            fd.write("\n")
        if set_ro:
            chmod(fname, os.stat(fname)[0] & 0o444)
        return

    def save_into_file_wbackup(self, fname, set_ro=False):
        """Save into a file (making a backup)
        The file should be usable for reload

        Args:
            fname:
            set_ro:

        Returns:

        """
        # rewrite config file (write tmp file first)
        tmp_name = "%s.tmp" % fname
        try:
            os.unlink(tmp_name)
        except Exception:
            pass  # just protect
        self.save_into_file(tmp_name)

        # also save old one with backup name
        backup_name = "%s~" % fname
        try:
            os.unlink(backup_name)
        except Exception:
            pass  # just protect
        try:
            os.rename(fname, backup_name)
            # make it user writable
            chmod(backup_name, (os.stat(backup_name)[0] & 0o666) | 0o200)
        except Exception:
            pass  # just protect

        # finally rename to the proper name
        os.rename(tmp_name, fname)
        if set_ro:
            chmod(fname, os.stat(fname)[0] & 0o444)

    # used internally to define subtype class
    def get_subparams_class(self):
        return SubParams


class CommentedOrderedDict(OrderedDict):
    """Ordered dictionary with comment support"""

    def __init__(self, indict=None):
        # TODO: double check restriction, all can be removed?
        #   cannot call directly the parent due to the particular implementation restrictions
        #   self._keys = []
        #   #was: UserDict.__init__(self, dict)
        #   OrderedDict.__init__(self, indict)
        # super().__init__(indict)
        self._keys = []
        xmlParse.UserDict.__init__(self, indict)
        self["comment"] = (None, "string", "Humman comment, not used by the code", None)


####################################################################
# INTERNAL, don't use directly
# Use the class definition instead
#
def extract_attr_val(attr_obj):
    """Return attribute value in the proper python format

    INTERNAL, don't use directly
    Use the class definition instead

    Args:
        attr_obj:

    Returns:

    """
    if attr_obj.type not in ("string", "int", "expr"):
        raise RuntimeError("Wrong attribute type '%s', must be either 'int' or 'string'" % attr_obj.type)

    if attr_obj.type in ("string", "expr"):
        return str(attr_obj.value)
    else:
        return int(attr_obj.value)


######################################################
# Define common defaults
class CommonSubParams(SubParams):
    # return attribute value in the proper python format
    def extract_attr_val(self, attr_obj):
        return extract_attr_val(attr_obj)


class CommonParams(Params):
    # populate self.defaults
    def init_support_defaults(self):
        # attributes are generic, shared between frontend and factory
        self.attr_defaults = CommentedOrderedDict()
        self.attr_defaults["value"] = (None, "Value", "Value of the attribute (string)", None)
        self.attr_defaults["parameter"] = ("True", "Bool", "Should it be passed as a parameter?", None)
        self.attr_defaults["glidein_publish"] = (
            "False",
            "Bool",
            "Should it be published by the glidein? (Used only if parameter is True.)",
            None,
        )
        self.attr_defaults["job_publish"] = (
            "False",
            "Bool",
            "Should the glidein publish it to the job? (Used only if parameter is True.)",
            None,
        )
        self.attr_defaults["type"] = ["string", "string|int", "What kind on data is value.", None]

        # most file attributes are generic, shared between frontend and factory
        self.file_defaults = CommentedOrderedDict()
        self.file_defaults["absfname"] = (None, "fname", "File name on the local disk.", None)
        self.file_defaults["relfname"] = (
            None,
            "fname",
            "Name of the file once it gets to the worker node. (defaults to the last part of absfname)",
            None,
        )
        self.file_defaults["const"] = (
            "True",
            "Bool",
            "Will the file be constant? If True, the file will be signed. If False, it can be modified at any time and will not be cached.",
            None,
        )
        self.file_defaults["executable"] = (
            "False",
            "Bool",
            "Is this an executable that needs to be run in the glidein?",
            None,
        )
        self.file_defaults["wrapper"] = (
            "False",
            "Bool",
            "Is this a wrapper script that needs to be sourced in the glidein job wrapper?",
            None,
        )
        self.file_defaults["untar"] = ("False", "Bool", "Do I need to untar it? ", None)
        self.file_defaults["period"] = (0, "int", 'Re-run the executable every "period" seconds if > 0.', None)
        self.file_defaults["prefix"] = ("GLIDEIN_PS_", "string", "Prefix used for periodic jobs (STARTD_CRON).", None)
        self.file_defaults["type"] = (
            None,
            "string",
            'File type (regular,run,source). Allows modifiers like ":singularity" to run in singularity.',
            None,
        )
        # TODO: consider adding "time" setup, prejob, postjob, cleanup, periodic. setup & cleanup w/ qualifier :bebg-aeag before/after entry + before/after group og na (group positioning does not apply to factory files)
        # to add check scripts around jobs: self.file_defaults["job_wrap"]=("no","pre|post|no",'Run the executable before (pre) or after (post) each job.',None)

        untar_defaults = CommentedOrderedDict()
        untar_defaults["cond_attr"] = (
            "TRUE",
            "attrname",
            "If not the special value TRUE, the attribute name used at runtime to determine if the file should be untarred or not.",
            None,
        )
        untar_defaults["dir"] = (
            None,
            "dirname",
            "Subdirectory in which to untar. (defaults to relname up to first .)",
            None,
        )
        untar_defaults["absdir_outattr"] = (
            None,
            "attrname",
            "Attribute to be set to the abs dir name where the tarball was unpacked. Will be defined only if untar effectively done. (Not defined if None)",
            None,
        )
        self.file_defaults["untar_options"] = untar_defaults

        self.monitor_defaults = CommentedOrderedDict()
        self.monitor_defaults["javascriptRRD_dir"] = (
            os.path.join(self.src_dir, "../../externals/flot"),
            "base_dir",
            "Location of the javascriptRRD library.",
            None,
        )
        self.monitor_defaults["flot_dir"] = (
            os.path.join(self.src_dir, "../../externals/flot"),
            "base_dir",
            "Location of the flot library.",
            None,
        )
        self.monitor_defaults["jquery_dir"] = (
            os.path.join(self.src_dir, "../../externals/jquery"),
            "base_dir",
            "Location of the jquery library.",
            None,
        )
        return

    def get_subparams_class(self):
        return CommonSubParams

    # return attribute value in the proper python format
    def extract_attr_val(self, attr_obj):
        return extract_attr_val(attr_obj)


################################################
# only allow ascii characters, the numbers and a few punctuations
# no spaces, not special characters or other punctuation
VALID_NAME_CHARS = string.ascii_letters + string.digits + "._-"


def is_valid_name(name):
    """Check if a string can be used as a valid name

    Whitelist based:
        only allow ascii characters, numbers and a few punctuations
        no spaces, no special characters or other punctuation

    Args:
        name (str): name to validate

    Returns:
        bool: True if the name is not empty and has only valid characters, False otherwise
    """
    # empty name is not valid
    if name is None:
        return False
    if name == "":
        return False
    for c in name:
        if c not in VALID_NAME_CHARS:
            return False
    return True


############################################################
#
# P R I V A T E - Do not use
#
############################################################


def col_wrap(text, width, indent):
    """Wrap a text string to a fixed length

    Args:
        text (str): string to wrap
        width (int): length
        indent (str): indentation string

    Returns:

    """
    short_text, next_char = shorten_text(text, width)
    if len(short_text) != len(text):  # was shortened
        # print short_text
        org_short_text = short_text[0:]
        # make sure you are not breaking words.
        while next_char not in ("", " ", "\t"):
            if len(short_text) == 0:
                # could not break on word boundary, leave as is
                short_text = org_short_text
                break
            next_char = short_text[-1]
            short_text = short_text[:-1]

        if len(short_text) <= len(indent):
            # too short, just split as it was
            short_text = org_short_text

        # calc next lines
        subtext = col_wrap(indent + text[len(short_text) :].lstrip(" \t"), width, indent)
        # glue
        return short_text + "\n" + subtext
    else:
        return text


def shorten_text(text, width):
    """Shorten text, make sure you properly account tabs

    Tabs are every 8 spaces (counted as number of chars to the next tab stop)

    Args:
        text (str): text to shorten
        width (int): length

    Returns (tuple):
        shorten text (str): shortened text
        next char (str): remainder
    """
    count = 0
    idx = 0
    for c in text:
        if count >= width:
            return (text[:idx], c)
        if c == "\t":
            count = ((count + 8) // 8) * 8  # round to neares mult of 8
            if count > width:
                return (text[:idx], c)
            idx = idx + 1
        else:
            count = count + 1
            idx = idx + 1

    return (text[:idx], "")


def defdict2string(defaults, indent, width=80):
    """Convert defaults to a string

    Args:
        defaults:
        indent:
        width:

    Returns:

    """
    outstrarr = []

    keys = sorted(defaults.keys())

    final_keys = []
    # put simple elements first
    for k in keys:
        el = defaults[k]
        if not isinstance(el, OrderedDict):
            defvalue, ktype, txt, subdef = el
            if subdef is None:
                final_keys.append(k)
    # put simple elements first
    for k in keys:
        el = defaults[k]
        if isinstance(el, OrderedDict):
            final_keys.append(k)
        else:
            defvalue, ktype, txt, subdef = el
            if subdef is not None:
                final_keys.append(k)

    for k in final_keys:
        el = defaults[k]
        if isinstance(el, OrderedDict):  # sub-dictionary
            outstrarr.append(f"{indent}{k}:" + "\n" + defdict2string(el, indent + "\t", width))
        else:
            # print el
            defvalue, ktype, txt, subdef = el
            wrap_indent = indent + " " * len(f"{k}({ktype}) - ")
            if subdef is not None:
                if isinstance(defvalue, OrderedDict):
                    dict_subdef = copy.deepcopy(subdef)
                    dict_subdef["name"] = (None, "name", "Name", None)
                    outstrarr.append(
                        col_wrap(f"{indent}{k}({ktype}) - {txt}:", width, wrap_indent)
                        + "\n"
                        + defdict2string(dict_subdef, indent + "\t", width)
                    )
                else:
                    outstrarr.append(
                        col_wrap(f"{indent}{k}({ktype}) - {txt}:", width, wrap_indent)
                        + "\n"
                        + defdict2string(subdef, indent + "\t", width)
                    )
            else:
                outstrarr.append(col_wrap(f"{indent}{k}({ktype}) - {txt} [{defvalue}]", width, wrap_indent))
    return "\n".join(outstrarr)
