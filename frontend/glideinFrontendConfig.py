# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""Frontend config related classes
"""

import os.path
import urllib.error
import urllib.parse
import urllib.request

from glideinwms.creation.lib.matchPolicy import MatchPolicy
from glideinwms.lib import hashCrypto, util

############################################################
#
# Configuration
#
############################################################


class FrontendConfig:
    def __init__(self):
        # set default values
        # user should modify if needed

        self.frontend_descript_file = "frontend.descript"
        self.group_descript_file = "group.descript"
        self.params_descript_file = "params.cfg"
        self.attrs_descript_file = "attrs.cfg"
        self.signature_descript_file = "signatures.sha1"
        self.signature_type = "sha1"
        self.history_file = "history.pk"
        self.cache_dir = "schedd_ads_cache"


# global configuration of the module
frontendConfig = FrontendConfig()


############################################################
#
# Helper function
#
############################################################
def get_group_dir(base_dir, group_name):
    return os.path.join(base_dir, "group_" + group_name)


############################################################
#
# Generic Class
# You most probably don't want to use these
#
############################################################


# loads a file or URL composed of
#   NAME VAL
# and creates
#   self.data[NAME]=VAL
# It also defines:
#   self.config_file="name of file"
# If validate is defined, also defines
#   self.hash_value
class ConfigFile:
    """Load a file or URL composed of NAME VAL lines
    and create the data dictionary
        self.data[NAME]=VAL
    Also define:
        self.config_file="name of file"
    If validate is defined, also define a variable with the file hash:
        self.hash_value
    """

    def __init__(self, config_dir, config_file, convert_function=repr, validate=None):
        """Define, load and derive a config file

        Args:
            config_dir (str|bytes): directory of the config file
            config_file (str|bytes): config file name/URI
            convert_function: function converting each line value
            validate (None|tuple): hash algorithm, value tuple  (hash_algo,value)
        """
        self.config_dir = config_dir
        self.config_file = config_file
        self.data = {}
        self.load(os.path.join(config_dir, config_file), convert_function, validate)
        self.derive()

    def open(self, fname):
        """Open the config file/URI. Used in self.load()

        Args:
            fname (str|bytes): URL or file path

        Returns:

        """
        if (fname[:5] == "http:") or (fname[:6] == "https:") or (fname[:4] == "ftp:"):
            # one of the supported URLs
            return urllib.request.urlopen(fname)
        else:
            # local file
            return open(fname)

    def validate_func(self, data, validate, fname):
        """Validate the data

        Args:
            data (str): data to validate
            validate (None|tuple): hash algorithm, value tuple
            fname (str): file/URI, used only in the error message

        Raises:
            OSError: if the hash calculated is different from the provided one
        """
        if validate is not None:
            vhash = hashCrypto.get_hash(validate[0], data)
            self.hash_value = vhash
            if (validate[1] is not None) and (vhash != validate[1]):
                raise OSError(
                    "Failed validation of '%s'. Hash %s computed to '%s', expected '%s'"
                    % (fname, validate[0], vhash, validate[1])
                )

    def load(self, fname, convert_function, validate=None):
        """Load the config file/URI.
        The file/URI is a series of NAME VALUE lines or comment lines (starting with #)
        The hash algorithm and value are used to validate the file content.
        The convert_function is used to convert the value of each line

        Args:
            fname (str|bytes): URL or file path
            convert_function: function converting the line value
            validate (None|tuple): if defined, must be (hash_algo,value)
        """
        self.data = {}
        with self.open(fname) as fd:
            data = fd.read()
            self.validate_func(data, validate, fname)
            lines = data.splitlines()
            del data
            for line in lines:
                if line[0] == "#":
                    continue  # comment
                if len(line.strip()) == 0:
                    continue  # empty line
                self.split_func(line, convert_function)

    def split_func(self, line, convert_function):
        """Loads the file line in the data dictionary
        The first word is the key, the rest of the line the value, converted by the convert_function

        Args:
            line (str): line to load
            convert_function: function converting the line value
        """
        larr = line.split(None, 1)
        lname = larr[0]
        if len(larr) == 1:
            lval = ""
        else:
            lval = larr[1]
        exec(f"self.data['{lname}']={convert_function(lval)}")

    def derive(self):
        return  # by default, do nothing

    def __str__(self):
        output = "\n"
        for key in list(self.data.keys()):
            output += f"{key} = {str(self.data[key])}, ({type(self.data[key])})\n"
        return output


# load from the group subdir
class GroupConfigFile(ConfigFile):
    """Config file from the group subdirectory"""

    def __init__(self, base_dir, group_name, config_file, convert_function=repr, validate=None):
        """Define, load and derive a config file from the group subdirectory

        Args:
            base_dir (str|bytes): directory of the config file
            group_name (str): group name
            config_file (str|bytes): config file name/URI
            convert_function: function converting each line value
            validate (None|tuple): hash algorithm, value tuple  (hash_algo,value)
        """
        ConfigFile.__init__(self, get_group_dir(base_dir, group_name), config_file, convert_function, validate)
        self.group_name = group_name


# load both the main and group subdir config file
# and join the results
# Also defines:
#   self.group_hash_value, if group_validate defined
class JoinConfigFile(ConfigFile):
    """Joint main and group configuration"""

    def __init__(
        self, base_dir, group_name, config_file, convert_function=repr, main_validate=None, group_validate=None
    ):
        """Define, load and derive both the main and group subdir config file and join the results
        Also define:
            self.group_hash_value, if group_validate defined


        Args:
            base_dir (str|bytes): directory of the config file
            group_name (str): group name
            config_file (str|bytes): config file name/URI
            convert_function: function converting each line value
            main_validate (None|tuple): hash algorithm, value tuple  (hash_algo,value)
            group_validate (None|tuple): hash algorithm, value tuple  (hash_algo,value)
        """
        ConfigFile.__init__(self, base_dir, config_file, convert_function, main_validate)
        self.group_name = group_name
        group_obj = GroupConfigFile(base_dir, group_name, config_file, convert_function, group_validate)
        if group_validate is not None:
            self.group_hash_value = group_obj.hash_value
        # merge by overriding whatever is found in the subdir
        for k in list(group_obj.data.keys()):
            self.data[k] = group_obj.data[k]


############################################################
#
# Configuration
#
############################################################


class FrontendDescript(ConfigFile):
    """Description of the Frontand

    Only one
    Content comes from the global configuration
    File name: frontend.descript
    cWDictFile.StrDictFile defined in cvWDictFile.get_main_dicts()
    """

    def __init__(self, config_dir):
        global frontendConfig
        ConfigFile.__init__(
            self, config_dir, frontendConfig.frontend_descript_file, repr
        )  # convert everything in strings


class ElementDescript(GroupConfigFile):
    """Description of a Frontend group

    One per group/element
    Content comes from the group configuration
    File name: group.descript (in the group subdirectory - group_GROUPNAME)
    cWDictFile.StrDictFile defined in cvWDictFile.get_group_dicts()
    """

    def __init__(self, base_dir, group_name):
        global frontendConfig
        GroupConfigFile.__init__(
            self, base_dir, group_name, frontendConfig.group_descript_file, repr
        )  # convert everything in strings


class ParamsDescript(JoinConfigFile):
    """Global and grup parameters in a Frontend

    One per group/element
    Content has `parameter="True"` in the <attrs> sections in the global and group configuration
    Files: params.cfg in the main directory and group subdirectory
    cvWDictFile.ParamsDictFile defined in cvWDictFile.get_common_dicts()
    """

    def __init__(self, base_dir, group_name):
        global frontendConfig
        JoinConfigFile.__init__(
            self,
            base_dir,
            group_name,
            frontendConfig.params_descript_file,
            lambda s: "('%s',%s)" % tuple(s.split(None, 1)),
        )  # split the array
        self.const_data = {}
        self.expr_data = {}  # original string
        self.expr_objs = {}  # compiled object
        for k in list(self.data.keys()):
            type_str, val = self.data[k]
            if type_str == "EXPR":
                try:
                    self.expr_objs[k] = compile(val, "<string>", "eval")
                except SyntaxError:
                    self.expr_objs[k] = '""'
                    raise RuntimeError("Syntax error in parameter %s" % k)
                self.expr_data[k] = val
            elif type_str == "CONST":
                self.const_data[k] = val
            else:
                raise RuntimeError(f"Unknown parameter type '{type_str}' for '{k}'!")


class AttrsDescript(JoinConfigFile):
    """Global and grup attributes in a Frontend

    One per group/element
    Content comes from the <attrs> sections in the global and group configuration
    Files: attrs.cfg in the main directory and group subdirectory
    cWDictFile.ReprDictFile defined in cvWDictFile.get_common_dicts()
    """

    def __init__(self, base_dir, group_name):
        global frontendConfig
        JoinConfigFile.__init__(
            self, base_dir, group_name, frontendConfig.attrs_descript_file, str
        )  # they are already in python form


# this one is the special frontend work dir signature file
class SignatureDescript(ConfigFile):
    def __init__(self, config_dir):
        global frontendConfig
        ConfigFile.__init__(
            self, config_dir, frontendConfig.signature_descript_file, None
        )  # Not used, redefining split_func
        self.signature_type = frontendConfig.signature_type

    def split_func(self, line, convert_function):
        larr = line.split(None)
        if len(larr) != 3:
            raise RuntimeError("Invalid line (expected 3 elements, found %i)" % len(larr))
        self.data[larr[2]] = (larr[0], larr[1])


# this one is the generic hash descript file
class BaseSignatureDescript(ConfigFile):
    def __init__(self, config_dir, signature_fname, signature_type, validate=None):
        ConfigFile.__init__(self, config_dir, signature_fname, None, validate)  # Not used, redefining split_func
        self.signature_type = signature_type

    def split_func(self, line, convert_function):
        larr = line.split(None, 1)
        if len(larr) != 2:
            raise RuntimeError("Invalid line (expected 2 elements, found %i)" % len(larr))
        lval = larr[1]
        self.data[lval] = larr[0]


############################################################
#
# Processed configuration
#
############################################################


class ElementMergedDescript:
    """Selective merge of global and group configuration

    not everything is merged
    the old element in the global configuration can still be accessed
    """

    def __init__(self, base_dir, group_name):
        self.frontend_data = FrontendDescript(base_dir).data
        if group_name not in self.frontend_data["Groups"].split(","):
            raise RuntimeError("Group '{}' not supported: {}".format(group_name, self.frontend_data["Groups"]))

        self.element_data = ElementDescript(base_dir, group_name).data
        self.group_name = group_name

        self._merge()

    #################
    # Private
    def _merge(self):
        self.merged_data = {}

        for t in ("JobSchedds",):
            self.merged_data[t] = self._split_list(self.frontend_data[t]) + self._split_list(self.element_data[t])
            if len(self.merged_data[t]) == 0:
                raise RuntimeError("Found empty %s!" % t)

        for t in ("FactoryCollectors",):
            self.merged_data[t] = eval(self.frontend_data[t]) + eval(self.element_data[t])
            if len(self.merged_data[t]) == 0:
                raise RuntimeError("Found empty %s!" % t)

        for t in ("FactoryQueryExpr", "JobQueryExpr"):
            self.merged_data[t] = f"({self.frontend_data[t]}) && ({self.element_data[t]})"
            for data in (self.frontend_data, self.element_data):
                if "MatchPolicyModule%s" % t in data:
                    self.merged_data[t] = "({}) && ({})".format(self.merged_data[t], data["MatchPolicyModule%s" % t])

        # PM: TODO: Not sure why FactoryMatchAttrs was not in the list below
        #     To get complete list of FactoryMatchAttrs you need to merge it
        for t in ("JobMatchAttrs", "FactoryMatchAttrs"):
            attributes = []
            names = []
            match_attrs_list = eval(self.frontend_data[t]) + eval(self.element_data[t])

            for data in (self.frontend_data, self.element_data):
                if "MatchPolicyModule%s" % t in data:
                    match_attrs_list += eval(data["MatchPolicyModule%s" % t])

            for el in match_attrs_list:
                el_name = el[0]
                if el_name not in names:
                    attributes.append(el)
                    names.append(el_name)
            self.merged_data[t] = attributes

        for t in ("MatchExpr",):
            self.merged_data[t] = f"({self.frontend_data[t]}) and ({self.element_data[t]})"
            self.merged_data[t + "CompiledObj"] = compile(self.merged_data[t], "<string>", "eval")

        self.merged_data["MatchPolicyModules"] = []
        if "MatchPolicyFile" in self.frontend_data:
            self.merged_data["MatchPolicyModules"].append(MatchPolicy(self.frontend_data["MatchPolicyFile"]))
        if "MatchPolicyFile" in self.element_data:
            self.merged_data["MatchPolicyModules"].append(MatchPolicy(self.element_data["MatchPolicyFile"]))

        # We use default ProxySelectionPlugin
        self.merged_data["ProxySelectionPlugin"] = "ProxyAll"

        for t in ("ProxySelectionPlugin", "SecurityName", "IDTokenLifetime", "IDTokenKeyname"):
            for data in (self.frontend_data, self.element_data):
                if t in data:
                    self.merged_data[t] = data[t]

        proxies = []  # TODO: Investigate how to merge global and group credentials.
        parameters = {}
        # switching the order, so that the group credential will
        # be chosen before the global credential when ProxyFirst is used.
        for data in (self.element_data, self.frontend_data):
            if "Proxies" in data:
                proxies += eval(data["Proxies"])
            if "Parameters" in data:
                parameters.update(eval(data["Parameters"]))
        self.merged_data["Proxies"] = proxies
        self.merged_data["Parameters"] = parameters

        proxy_descript_attrs = [
            "ProxySecurityClasses",
            "ProxyTrustDomains",
            "ProxyTypes",
            "CredentialPurposes",
            "CredentialContexts",
            "CredentialGenerators",
            "ProxyKeyFiles",
            "ProxyPilotFiles",
            "ProxyVMIds",
            "ProxyVMTypes",
            "ProxyCreationScripts",
            "ProxyUpdateFrequency",
            "ProxyVMIdFname",
            "ProxyVMTypeFname",
            "ProxyRemoteUsernames",
            "ProxyProjectIds",
        ]

        for attr in proxy_descript_attrs:
            proxy_descript_data = {}
            for data in (self.frontend_data, self.element_data):
                if attr in data:  # was data.has_key(attr):
                    dprs = eval(data[attr])
                    for k in list(dprs.keys()):
                        proxy_descript_data[k] = dprs[k]
            self.merged_data[attr] = proxy_descript_data

        return

    @staticmethod
    def _split_list(val):
        if val == "None":
            return []
        elif val == "":
            return []
        else:
            return val.split(",")


class GroupSignatureDescript:
    def __init__(self, base_dir, group_name):
        self.group_name = group_name

        sd = SignatureDescript(base_dir)
        self.signature_data = sd.data
        self.signature_type = sd.signature_type

        fd = sd.data["main"]
        self.frontend_descript_fname = fd[1]
        self.frontend_descript_signature = fd[0]

        gd = sd.data["group_%s" % group_name]
        self.group_descript_fname = gd[1]
        self.group_descript_signature = gd[0]


class StageFiles:
    def __init__(self, base_URL, descript_fname, validate_algo, signature_hash):
        self.base_URL = base_URL
        self.validate_algo = validate_algo
        self.stage_descript = ConfigFile(
            base_URL, descript_fname, repr, (validate_algo, None)
        )  # just get the hash value... will validate later

        self.signature_descript = BaseSignatureDescript(
            base_URL, self.stage_descript.data["signature"], validate_algo, (validate_algo, signature_hash)
        )
        if self.stage_descript.hash_value != self.signature_descript.data[descript_fname]:
            raise OSError(
                "Descript file %s signature invalid, expected'%s' got '%s'"
                % (descript_fname, self.signature_descript.data[descript_fname], self.stage_descript.hash_value)
            )

    def get_stage_file(self, fname, repr):
        return ConfigFile(self.base_URL, fname, repr, (self.validate_algo, self.signature_descript.data[fname]))

    def get_file_list(self, list_type):  # example list_type == 'preentry_file_list'
        if list_type not in self.stage_descript.data:
            raise KeyError(f"Unknown list type '{list_type}'; valid typtes are {list(self.stage_descript.data.keys())}")

        list_fname = self.stage_descript.data[list_type]
        return self.get_stage_file(list_fname, lambda x: x.split(None, 4))


# this class knows how to interpret some of the files in the Stage area
class ExtStageFiles(StageFiles):
    def __init__(self, base_URL, descript_fname, validate_algo, signature_hash):
        StageFiles.__init__(self, base_URL, descript_fname, validate_algo, signature_hash)
        self.preentry_file_list = None

    def get_constants(self):
        self.load_preentry_file_list()
        return self.get_stage_file(self.preentry_file_list.data["constants.cfg"][0], repr)

    def get_condor_vars(self):
        self.load_preentry_file_list()
        return self.get_stage_file(self.preentry_file_list.data["condor_vars.lst"][0], lambda x: x.split(None, 6))

    # internal
    def load_preentry_file_list(self):
        if self.preentry_file_list is None:
            self.preentry_file_list = self.get_file_list("preentry_file_list")
        # else, nothing to do


# this class knows how to interpret some of the files in the Stage area
# Will parrpopriately merge the main and the group ones
class MergeStageFiles:
    def __init__(
        self,
        base_URL,
        validate_algo,
        main_descript_fname,
        main_signature_hash,
        group_name,
        group_descript_fname,
        group_signature_hash,
    ):
        self.group_name = group_name
        self.main_stage = ExtStageFiles(base_URL, main_descript_fname, validate_algo, main_signature_hash)
        self.group_stage = ExtStageFiles(
            get_group_dir(base_URL, group_name), group_descript_fname, validate_algo, group_signature_hash
        )

    def get_constants(self):
        main_consts = self.main_stage.get_constants()
        group_consts = self.group_stage.get_constants()
        # group constants override the main ones
        for k in list(group_consts.data.keys()):
            main_consts.data[k] = group_consts.data[k]
        main_consts.group_name = self.group_name
        main_consts.group_hash_value = group_consts.hash_value

        return main_consts

    def get_condor_vars(self):
        main_cv = self.main_stage.get_condor_vars()
        group_cv = self.group_stage.get_condor_vars()
        # group condor_vars override the main ones
        for k in list(group_cv.data.keys()):
            main_cv.data[k] = group_cv.data[k]
        main_cv.group_name = self.group_name
        main_cv.group_hash_value = group_cv.hash_value

        return main_cv


############################################################
#
# The FrontendGroups may want to preserve some state between
# iterations/invocations. The HistoryFile class provides
# the needed support for this.
#
# There is no fixed schema in the class itself;
# the FrontedGroup is free to store any arbitrary dictionary
# in it.
#
############################################################


class HistoryFile:
    def __init__(self, base_dir, group_name, load_on_init=True, default_factory=None):
        """
        The default_factory semantics is the same as the one in
        collections.defaultdict
        """
        self.base_dir = base_dir
        self.group_name = group_name
        self.fname = os.path.join(get_group_dir(base_dir, group_name), frontendConfig.history_file)
        self.default_factory = default_factory

        # cannot use collections.defaultdict directly
        # since it is only supported starting python 2.5
        self.data = {}

        if load_on_init:
            self.load()

    def load(self, raise_on_error=False):
        try:
            # using it only for convenience (expiration, ... not used)
            data = util.file_pickle_load(self.fname)
        except Exception:
            if raise_on_error:
                raise
            else:
                # default to empty history on error
                data = {}

        if not isinstance(data, dict):
            if raise_on_error:
                raise TypeError("History object not a dictionary: %s" % str(type(data)))
            else:
                # default to empty history on error
                data = {}

        self.data = data

    def save(self, raise_on_error=False):
        # There is no concurrency, so does not need to be done atomically
        # Anyway we want to avoid to write an empty file on top of a
        # saved state because of an exception
        try:
            util.file_pickle_dump(self.fname, self.data)
        except Exception:
            if raise_on_error:
                raise
            # else, just ignore

    def has_key(self, keyid):
        return keyid in self.data

    def __contains__(self, keyid):
        return keyid in self.data

    def __getitem__(self, keyid):
        try:
            return self.data[keyid]
        except KeyError:
            if self.default_factory is None:
                raise  # no default initialization, just fail
            # i have the initialization function, use it
            self.data[keyid] = self.default_factory()
            return self.data[keyid]

    def __setitem__(self, keyid, val):
        self.data[keyid] = val

    def __delitem__(self, keyid):
        del self.data[keyid]

    def empty(self):
        self.data = {}

    def get(self, keyid, defaultval=None):
        return self.data.get(keyid, defaultval)
