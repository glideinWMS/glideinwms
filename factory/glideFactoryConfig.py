# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""GlideinWMS Factory Configuration Module.

This module provides classes to load, parse, and manage configuration
files used by the GlideinWMS Factory. It includes support for both the
main configuration and per-entry configuration files (located in Entry
subdirectories), as well as handling of cryptographic keys and frontend
descriptions.


Typical usage example is by using directly the global variable factoryConfig:

glideFactoryConfig.factoryConfig.glidein_descript_file = PATH_OF_FILE
glideinDescript = glideFactoryConfig.GlideinDescript()
frontendDescript = glideFactoryConfig.FrontendDescript()
"""

import os
import os.path
import shutil

from glideinwms.lib import pubCrypto, symCrypto

############################################################
#
# Configuration
#
############################################################


class FactoryConfig:
    """Holds default configuration file names for the factory.

    The attributes defined in this class are used to locate and load the
    various configuration files required by the factory.
    """

    def __init__(self):
        """Initialize FactoryConfig with default file names.

        Users should modify these values if needed so that they are consistent
        with the creation/lib/c?WConst.py files content.
        """
        self.glidein_descript_file = "glidein.descript"
        self.job_descript_file = "job.descript"
        self.job_attrs_file = "attributes.cfg"
        self.job_params_file = "params.cfg"
        self.job_submit_attrs_file = "submit_attrs.cfg"
        self.frontend_descript_file = "frontend.descript"
        self.signatures_file = "signatures.sha1"
        self.aggregated_stats_file = "aggregated_stats_dict.data"


# global configuration of the module
factoryConfig = FactoryConfig()


############################################################
#
# Generic Class
# You most probably don't want to use these
#
############################################################


class ConfigFile:
    """In-memory dictionary-like representation of key-value configuration files.

    Loads a file composed of
        NAME VAL
    lines and creates a dictionary where each key is assigned the value produced
    by applying the conversion function to the corresponding value string. The default
    conversion is repr, but a custom conversion function can be provided:
        self.data[NAME]=convert_function(VAL)
    It also defines:
        self.config_file="name of file"

    This is used only to load into memory and access the dictionary, not to update the
    on-disk persistent values.

    Attributes:
        config_file (str): The filename of the configuration file.
        data (dict): The dictionary holding configuration key-value pairs.
    """

    def __init__(self, config_file, convert_function=repr):
        """Initialize a ConfigFile instance and load its data.

        Args:
            config_file (str): The path to the configuration file.
            convert_function (Callable, optional): Function to convert value strings.
                Defaults to repr.
        """
        self.config_file = config_file
        self.load(config_file, convert_function)

    def load(self, fname, convert_function):
        """Load and parse the configuration file.

        Args:
            fname (str): The filename to load.
            convert_function (Callable): Function used to convert value strings.
        """
        self.data = {}
        with open(fname) as fd:
            lines = fd.readlines()
            for line in lines:
                if line[0] == "#":
                    continue  # comment
                if len(line.strip()) == 0:
                    continue  # empty line
                larr = line.split(None, 1)
                lname = larr[0]
                if len(larr) == 1:
                    lval = ""
                else:
                    lval = larr[1][:-1]  # strip newline
                exec(f"self.data['{lname}']={convert_function(lval)}")

    def has_key(self, key_name):
        """Check if the configuration contains a given key.

        Args:
            key_name (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key_name in self.data

    def __contains__(self, key_name):
        """Determine if a key is in the configuration.

        Args:
            key_name (str): The key to check.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return key_name in self.data

    def __str__(self):
        """Return a string representation of the configuration data.

        Returns:
            str: Formatted string with keys, values, and their types.
        """
        output = "\n"
        for key in list(self.data.keys()):
            output += f"{key} = {str(self.data[key])}, ({type(self.data[key])})\n"
        return output


class EntryConfigFile(ConfigFile):
    """Configuration file loader for an Entry subdirectory.

    Loads a configuration file located in a subdirectory named "entry_<entry_name>".
    In addition to the data loaded by the parent ConfigFile, it sets the entry name
    and a short version of the configuration file name.

    Attributes:
        config_file (str): Name of file with entry directory (from parent ConfigFile)
        entry_name (str): Entry name
        config_file_short (str): Name of file (just the file name since the other had the directory)
    """

    def __init__(self, entry_name, config_file, convert_function=repr):
        """Initialize EntryConfigFile with an entry name and config file.

        Args:
            entry_name (str): The name of the Entry.
            config_file (str): The configuration file name.
            convert_function (Callable, optional): Function to convert string values.
                Defaults to repr.
        """
        ConfigFile.__init__(self, os.path.join("entry_" + entry_name, config_file), convert_function)
        self.entry_name = entry_name
        self.config_file_short = config_file


class JoinConfigFile(ConfigFile):
    """Loads and joins configuration files from the main directory and an entry subdirectory.

    The resulting configuration dictionary is initially populated with values from the
    main configuration file and then updated with values from the entry-specific file.
    This class does not support saving changes to disk.

    Attributes:
        config_file (str): Name of both files, with and without entry directory, with " AND " in the middle.
            It is not an actual file. (from parent ConfigFile, different value)
        data (dict): Will contain the joint items (initially the common one, then is updated using
            the content of `entry_obj.data`) (from parent ConfigFile, different value)
        entry_name (str): The name of the Entry.
        config_file_short (str): The short name of the configuration file (without the directory).

    """

    def __init__(self, entry_name, config_file, convert_function=repr):
        """Initialize JoinConfigFile by joining main and entry subdirectory configurations.

        Args:
            entry_name (str): The name of the entry.
            config_file (str): The configuration file name.
            convert_function (Callable, optional): Function to convert string values.
                Defaults to repr.
        """
        ConfigFile.__init__(self, config_file, convert_function)
        self.entry_name = entry_name
        entry_obj = EntryConfigFile(entry_name, config_file, convert_function)
        # merge by overriding whatever is found in the subdir (Entry)
        for k in list(entry_obj.data.keys()):
            self.data[k] = entry_obj.data[k]
        self.config_file = f"{config_file} AND {entry_obj.config_file}"
        self.config_file_short = config_file


############################################################
#
# Configuration
#
############################################################


class GlideinKey:
    """Handles public key operations for the GlideinWMS factory.

    Supports creation, loading, and retrieval of RSA keys.
    """

    def __init__(self, pub_key_type, key_fname=None, recreate=False):
        """Initialize a GlideinKey instance.

        Args:
            pub_key_type (str): The type of public key (only "RSA" is supported).
            key_fname (str, optional): Filename of the key. Defaults to None.
            recreate (bool, optional): If True, create a new key even if one exists.
                Defaults to False.
        """
        self.pub_key_type = pub_key_type
        self.load(key_fname, recreate)

    def load(self, key_fname=None, recreate=False):
        """Create the key if required and initialize it.

        Args:
            key_fname (str, optional): Filename of the key. Defaults to None.
            recreate (bool, optional): Create a new key if True, otherwise load existing key.
                Defaults to False.

        Raises:
            RuntimeError: If a key type other than RSA is specified.
        """
        if self.pub_key_type == "RSA":
            # hashlib methods are called dynamically
            from hashlib import md5

            if key_fname is None:
                key_fname = "rsa.key"

            self.rsa_key = pubCrypto.RSAKey(key_fname=key_fname)

            if recreate:
                # recreate it
                self.rsa_key.new()
                self.rsa_key.save(key_fname)

            self.pub_rsa_key = self.rsa_key.PubRSAKey()
            self.pub_key_id = md5(b" ".join((self.pub_key_type.encode("utf-8"), self.pub_rsa_key.get()))).hexdigest()
            self.sym_class = symCrypto.AutoSymKey
        else:
            raise RuntimeError("Invalid pub key type value(%s), only RSA supported" % self.pub_key_type)

    def get_pub_key_type(self):
        """Get a copy of the public key type string.

        Returns:
            str: The public key type.
        """
        return self.pub_key_type[0:]

    def get_pub_key_value(self):
        """Retrieve the public key value.

        Returns:
            bytes: The RSA public key.

        Raises:
            RuntimeError: If the key type is not RSA.
        """
        if self.pub_key_type == "RSA":
            return self.pub_rsa_key.get()
        else:
            raise RuntimeError("Invalid pub key type value(%s), only RSA supported" % self.pub_key_type)

    def get_pub_key_id(self):
        """Retrieve the identifier of the public key.

        Returns:
            str: The public key identifier.
        """
        return self.pub_key_id[0:]

    def extract_sym_key(self, enc_sym_key):
        """Extract the symmetric key from an encrypted value (Frontend attribute).

        Args:
            enc_sym_key (str): Encrypted symmetric key as an ASCII string (AnyStrASCII).

        Returns:
            SymKey: An instance of the symmetric key (SymKey child object).

        Raises:
            RuntimeError: If the key type is not RSA.
        """
        if self.pub_key_type == "RSA":
            sym_key_code = self.rsa_key.decrypt_hex(enc_sym_key)
            return self.sym_class(sym_key_code)
        else:
            raise RuntimeError("Invalid pub key type value(%s), only RSA supported" % self.pub_key_type)


class GlideinDescript(ConfigFile):
    """Represents the Glidein description configuration file.

    This class loads the glidein.descript file and processes its content,
    including handling of public key type values.
    """

    def __init__(self):
        """Initialize GlideinDescript and process default public key fields."""
        global factoryConfig
        ConfigFile.__init__(self, factoryConfig.glidein_descript_file, repr)  # convert everything in strings
        if ("FactoryCollector" not in self.data) or (self.data["FactoryCollector"] == "None"):
            self.data["FactoryCollector"] = None
        if self.data["PubKeyType"] == "None":
            self.data["PubKeyType"] = None
        self.default_rsakey_fname = "rsa.key"
        self.backup_rsakey_fname = "rsa.key.bak"

    def backup_and_load_old_key(self):
        """Backup the existing key and load the old key object.

        If a public key type is defined, the current key is backed up and the old
        key is loaded for potential use.
        """
        if self.data["PubKeyType"] is not None:
            self.backup_rsa_key()
        self.load_old_rsa_key()

    def backup_rsa_key(self):
        """Backup the existing RSA key.

        Attempts to copy the default RSA key file to a backup file. On failure,
        the backup values are set to None.
        """
        if self.data["PubKeyType"] == "RSA":
            try:
                shutil.copy(self.default_rsakey_fname, self.backup_rsakey_fname)
                self.data["OldPubKeyType"] = self.data["PubKeyType"]
                return
            except Exception:
                # In case of failure, the requests from frontend get
                # delayed. So it is not critical enough to fail.
                pass

        self.data["OldPubKeyType"] = None
        self.data["OldPubKeyObj"] = None
        return

    def load_old_rsa_key(self):
        """Load the old RSA key object, if available.

        Assumes that the old key, if it exists, is of the same type as the current key.
        """
        # Assume that old key if exists is of same type
        self.data["OldPubKeyType"] = self.data["PubKeyType"]
        self.data["OldPubKeyObj"] = None

        if self.data["OldPubKeyType"] is not None:
            try:
                self.data["OldPubKeyObj"] = GlideinKey(self.data["OldPubKeyType"], key_fname=self.backup_rsakey_fname)
            except Exception:
                self.data["OldPubKeyType"] = None
                self.data["OldPubKeyObj"] = None
        return

    def remove_old_key(self):
        """Remove the backup RSA key file and clear associated data."""
        try:
            os.remove(self.backup_rsakey_fname)
        except:
            self.data["OldPubKeyType"] = None
            self.data["OldPubKeyObj"] = None
            raise
        self.data["OldPubKeyType"] = None
        self.data["OldPubKeyObj"] = None
        return

    def load_pub_key(self, recreate=False):
        """Load the public key object, creating a new key if required.

        Args:
            recreate (bool, optional): If True, create a new key overwriting the old one.
                Defaults to False.
        """
        if self.data["PubKeyType"] is not None:
            self.data["PubKeyObj"] = GlideinKey(
                self.data["PubKeyType"], key_fname=self.default_rsakey_fname, recreate=recreate
            )
        else:
            self.data["PubKeyObj"] = None
        return


class JobDescript(EntryConfigFile):
    """Loads the job description configuration for a specific Entry."""

    def __init__(self, entry_name):
        """Initialize JobDescript for the given Entry.

        Args:
            entry_name (str): The name of the Entry.
        """
        global factoryConfig
        EntryConfigFile.__init__(
            self, entry_name, factoryConfig.job_descript_file, repr
        )  # convert everything in strings


class JobAttributes(JoinConfigFile):
    """Loads and joins the job attributes configuration for a specific Entry."""

    def __init__(self, entry_name):
        """Initialize JobAttributes for the given Entry.

        Args:
            entry_name (str): The name of the Entry.
        """
        global factoryConfig
        JoinConfigFile.__init__(
            self, entry_name, factoryConfig.job_attrs_file, lambda s: s
        )  # values are in python format


class JobParams(JoinConfigFile):
    """Loads and joins the job parameters configuration for a specific entry."""

    def __init__(self, entry_name):
        """Initialize JobParams for the given Entry.

        Args:
            entry_name (str): The name of the Entry.
        """
        global factoryConfig
        JoinConfigFile.__init__(
            self, entry_name, factoryConfig.job_params_file, lambda s: s
        )  # values are in python format


class JobSubmitAttrs(JoinConfigFile):
    """Loads and joins the job submit attributes configuration for a specific Entry."""

    def __init__(self, entry_name):
        """Initialize JobSubmitAttrs for the given Entry.

        Args:
            entry_name (str): The name of the Entry.
        """
        global factoryConfig
        JoinConfigFile.__init__(
            # Using repr instead of identity (convert into strings) would keep the quotes in the values
            self,
            entry_name,
            factoryConfig.job_submit_attrs_file,
            lambda s: s,
        )  # values are in python format


class FrontendDescript(ConfigFile):
    """Handles the Frontend description configuration file.

    This configuration contains the security identity and username mappings
    for the Frontends that are authorized to use the Factory.

    The configuration (in `self.data`) is structured as a dictionary of dictionaries. E.g.:
        obj.data[frontend]['ident']=identity
        obj.data[frontend]['usermap'][sec_class]=username
    """

    def __init__(self):
        """Initialize FrontendDescript by loading the frontend description file."""
        global factoryConfig
        ConfigFile.__init__(self, factoryConfig.frontend_descript_file, lambda s: s)  # values are in python format

    def get_identity(self, frontend):
        """Retrieve the identity for a given Frontend.

        Args:
            frontend (str): The name of the Frontend.

        Returns:
            str or None: The identity if available, otherwise None.
        """
        if frontend in self.data:
            fe = self.data[frontend]
            return fe["ident"]
        else:
            return None

    def get_username(self, frontend, sec_class):
        """Retrieve the username (security name mapping) for a given Frontend and security class.

        Args:
            frontend (str): The name of the Frontend.
            sec_class (str): The security class name.

        Returns:
            str or None: The username if available and authorized, otherwise None.
        """
        if frontend in self.data:
            fe = self.data[frontend]["usermap"]
            if sec_class in fe:
                return fe[sec_class]
        return None

    def get_all_usernames(self):
        """Get a list of all usernames assigned to all the Frontends.

        Returns:
            list: A list of unique usernames.
        """
        usernames = {}
        for frontend in list(self.data.keys()):
            fe = self.data[frontend]["usermap"]
            for sec_class in list(fe.keys()):
                username = fe[sec_class]
                usernames[username] = True
        return list(usernames.keys())

    def get_all_frontend_sec_classes(self):
        """Get a list of all security classes in each Frontend, combined as "frontend:sec_class".

        Returns:
            list: A list of strings in the format "frontend:sec_class".
        """
        frontend_sec_classes = []
        for fe_name in list(self.data.keys()):
            fe = self.data[fe_name]["usermap"]
            for sec_class in list(fe.keys()):
                frontend_sec_classes.append(f"{fe_name}:{sec_class}")
        return frontend_sec_classes

    def get_frontend_name(self, identity):
        """Retrieve the Frontend corresponding to a given identity.

        Args:
            identity (str): The identity to look up.

        Returns:
            str or None: The Frontend name if found, otherwise None.
        """
        for fe_name in list(self.data.keys()):
            if self.data[fe_name]["ident"] == identity:
                return fe_name


# Signatures File format:
## File: signatures.sha1
##
# 6e3565a9a0f39e0641d7e3e777b8f22d7ebc8b0f  description.a92arS.cfg  entry_AmazonEC2
# 51b01a3c38589a41fb7a44936e12b31fe506ec7b  description.a92aqM.cfg  main
class SignatureFile(ConfigFile):
    """Representation of a signatures file as a dictionary.

    Loads the signatures.sha1 file, parsing each line into signature and
    description entries keyed by the file name.
    """

    def __init__(self):
        """Initialize SignatureFile by loading the signatures file."""
        global factoryConfig
        ConfigFile.__init__(self, factoryConfig.signatures_file, lambda s: s)  # values are in python format

    def load(self, fname, convert_function):
        """Load the signatures file into a dictionary.

        The convert_function is ignored because the file has a different
        format from all other configuration classes.
        Each line in the file is expected to have three components:
          - The signature
          - The description file
          - The key (used as the dictionary key)
        For each line, the following dictionary entries are created in the `data` dictionary:
          - "<key>_sign": the signature
          - "<key>_descript": the description file
        All keys and values are strings.

        Args:
            fname (str): The filename of the signatures file.
            convert_function (Callable): Ignored in this implementation.
        """
        self.data = {}
        with open(fname) as fd:
            lines = fd.readlines()
            for line in lines:
                if line[0] == "#":
                    continue  # comment
                if len(line.strip()) == 0:
                    continue  # empty line
                larr = line.split(None)
                lsign = larr[0]
                ldescript = larr[1]
                lname = larr[2]
                self.data["%s_sign" % str(lname)] = str(lsign)
                self.data["%s_descript" % str(lname)] = str(ldescript)
