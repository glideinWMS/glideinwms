# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
GlideFactory Credentials Module.

This module provides functions to retrieve and process the global credentials
ClassAds for the GlideinWMS factory.
"""

import base64
import gzip
import io
import os
import pwd
import re
import shutil

from glideinwms.lib import condorMonitor, logSupport
from glideinwms.lib.defaults import force_bytes

from . import glideFactoryInterface, glideFactoryLib

MY_USERNAME = pwd.getpwuid(os.getuid())[0]
SUPPORTED_AUTH_METHODS = [
    "grid_proxy",
    "cert_pair",
    "key_pair",
    "auth_file",
    "username_password",
    "idtoken",
    "scitoken",
]


class CredentialError(Exception):
    """Exception raised for credential-related errors.

    This exception is defined so that only credential errors are caught here,
    while other errors can propagate up.
    """

    pass


class SubmitCredentials:
    """Data class containing all information needed to submit a glidein.

    Attributes:
        username (str): The username for submission.
        security_class: The security class for submission.
        id: The identifier used for tracking the submit credentials.
        cred_dir (str): The directory location of credentials.
        security_credentials (dict): Dictionary mapping credential types to file paths.
        identity_credentials (dict): Dictionary mapping identity credential types to strings.
    """

    def __init__(self, username, security_class):
        """Initialize a SubmitCredentials instance.

        Args:
            username (str): The username for submission.
            security_class: The security class for submission.
        """
        self.username = username
        self.security_class = security_class  # Seems redundant info
        self.id = None  # id used for tracking the submit credentials
        self.cred_dir = ""  # location of credentials
        self.security_credentials = {}  # dict of credentials
        self.identity_credentials = {}  # identity information passed by frontend

    def add_security_credential(self, cred_type, filename):
        """Add a security credential.

        Args:
            cred_type (str): The type of credential.
            filename (str): The filename of the credential.

        Returns:
            bool: True if the credential was successfully added, False otherwise.
        """
        if not glideFactoryLib.is_str_safe(filename):
            return False

        cred_fname = os.path.join(self.cred_dir, "credential_%s" % filename)
        if not os.path.isfile(cred_fname):
            return False

        self.security_credentials[cred_type] = cred_fname
        return True

    def add_factory_credential(self, cred_type, absfname):
        """Add a factory provided security credential.

        Args:
            cred_type (str): The type of credential.
            absfname (str): The absolute filename of the credential.

        Returns:
            bool: True if the credential was successfully added, False otherwise.
        """
        if not os.path.isfile(absfname):
            return False

        self.security_credentials[cred_type] = absfname
        return True

    def add_identity_credential(self, cred_type, cred_str):
        """Add an identity credential.

        Args:
            cred_type (str): The type of identity credential.
            cred_str (str): The credential string.

        Returns:
            bool: True if the identity credential was successfully added.
        """
        self.identity_credentials[cred_type] = cred_str
        return True

    def __repr__(self):
        """Return a string representation of the SubmitCredentials instance.

        Returns:
            str: The string representation of the instance.
        """
        output = "SubmitCredentials"
        output += "username = %s; " % self.username
        output += "security class = %s; " % str(self.security_class)
        output += "id = %s; " % self.id
        output += "credential dir = %s; " % self.cred_dir
        output += "security credentials: "
        for sck, scv in self.security_credentials.items():
            output += f"    {sck} : {scv}; "
        output += "identity credentials: "
        for ick, icv in self.identity_credentials.items():
            output += f"    {ick} : {icv}; "
        return output


def update_credential_file(username, client_id, credential_data, request_clientname):
    """Update the credential file.

    This function updates the credential files by writing the new credential data in one file and
    a compressed version of the glidein credentials in a second file.

    Args:
        username (str): The credentials' username.
        client_id (str): The id used for tracking the submit credentials.
        credential_data (bytes): The credentials to be advertised.
        request_clientname (str): The client name passed by the frontend.

    Returns:
        tuple: A tuple containing the credential file name and the compressed file name.
    """
    proxy_dir = glideFactoryLib.factoryConfig.get_client_proxies_dir(username)
    fname_short = f"credential_{request_clientname}_{glideFactoryLib.escapeParam(client_id)}"
    fname = os.path.join(proxy_dir, fname_short)
    fname_compressed = "%s_compressed" % fname
    fname_mapped_idtoken = "%s_idtoken" % fname

    msg = "updating credential file %s" % fname
    logSupport.log.debug(msg)

    safe_update(fname, credential_data)
    compressed_credential = compress_credential(credential_data)
    if os.path.exists(fname_mapped_idtoken):
        idtoken_data = ""
        with open(fname_mapped_idtoken) as idtf:
            for line in idtf.readlines():
                idtoken_data += line
        safe_update(
            fname_compressed, b"%s####glidein_credentials=%s" % (force_bytes(idtoken_data), compressed_credential)
        )
    else:
        safe_update(fname_compressed, b"glidein_credentials=%s" % (compressed_credential))

    return fname, fname_compressed


# Comment by Igor:
# This functionality should really be in glideFactoryInterface module
# Making a minimal patch now to get the desired functionality
def get_globals_classads(factory_collector=glideFactoryInterface.DEFAULT_VAL):
    """Retrieve global classads for glidein credentials.

    Args:
        factory_collector (str): The factory collector. If default, it is obtained from the factory configuration.

    Returns:
        dict: A dictionary containing the stored classads.
    """
    if factory_collector == glideFactoryInterface.DEFAULT_VAL:
        factory_collector = glideFactoryInterface.factoryConfig.factory_collector

    status_constraint = '(GlideinMyType=?="glideclientglobal")'

    status = condorMonitor.CondorStatus("any", pool_name=factory_collector)
    status.require_integrity(True)  # important, this dictates what gets submitted

    status.load(status_constraint)

    data = status.fetchStored()
    return data


def process_global(classad, glidein_descript, frontend_descript):
    """Process a global credentials classad.

    This function processes a global classad, updating credential files based on the decrypted
    information contained in the classad.

    Args:
        classad (dict): A dictionary representation of the classad.
        glidein_descript (glideFactoryConfig.GlideinDescript): Factory configuration's Glidein description object.
        frontend_descript (glideFactoryConfig.FrontendDescript): Factory configuration's Frontend description object.

    Raises:
        CredentialError: If the factory has no public key or if any decryption error occurs.
    """
    # Factory public key must exist for decryption
    pub_key_obj = glidein_descript.data["PubKeyObj"]
    if pub_key_obj is None:
        raise CredentialError("Factory has no public key.  We cannot decrypt.")

    try:
        # Get the frontend security name so that we can look up the username
        sym_key_obj, frontend_sec_name = validate_frontend(classad, frontend_descript, pub_key_obj)

        request_clientname = classad["ClientName"]

        # get all the credential ids by filtering keys by regex
        # this makes looking up specific values in the dict easier
        r = re.compile("^GlideinEncParamSecurityClass")
        mkeys = list(filter(r.match, list(classad.keys())))
        for key in mkeys:
            prefix_len = len("GlideinEncParamSecurityClass")
            cred_id = key[prefix_len:]
            cred_data = sym_key_obj.decrypt_hex(classad["GlideinEncParam%s" % cred_id])
            security_class = sym_key_obj.decrypt_hex(classad[key]).decode("utf-8")
            username = frontend_descript.get_username(frontend_sec_name, security_class)
            if username is None:
                logSupport.log.error(
                    (
                        "Cannot find a mapping for credential %s of client %s. Skipping it. The security"
                        "class field is set to %s in the frontend. Please, verify the glideinWMS.xml and"
                        " make sure it is mapped correctly"
                    )
                    % (cred_id, classad["ClientName"], security_class)
                )
                continue

            msg = "updating credential for %s" % username
            logSupport.log.debug(msg)
            update_credential_file(username, cred_id, cred_data, request_clientname)
    except Exception as e:
        logSupport.log.debug(f"\nclassad {classad}\nfrontend_descript {frontend_descript}\npub_key_obj {pub_key_obj})")
        error_str = "Error occurred processing the globals classads."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str) from e


def get_key_obj(pub_key_obj, classad):
    """Get the symmetric key object from the request classad.

    Args:
        pub_key_obj (object): The factory public key object containing encryption and decryption methods.
        classad (dict): A dictionary representation of the classad.

    Returns:
        object: The symmetric key object.

    Raises:
        CredentialError: If symmetric key extraction fails.
    """
    if "ReqEncKeyCode" in classad:
        try:
            sym_key_obj = pub_key_obj.extract_sym_key(classad["ReqEncKeyCode"])
            return sym_key_obj
        except Exception as e:
            logSupport.log.debug(f"\nclassad {classad}\npub_key_obj {pub_key_obj}\n")
            error_str = "Symmetric key extraction failed."
            logSupport.log.exception(error_str)
            raise CredentialError(error_str) from e
    else:
        error_str = "Classad does not contain a key.  We cannot decrypt."
        raise CredentialError(error_str)


def validate_frontend(classad, frontend_descript, pub_key_obj):
    """Validate the frontend advertising the classad.

    This function ensures that the Frontend is allowed to communicate with the Factory by
    verifying that the claimed identity matches the authenticated identity.

    Args:
        classad (dict): A dictionary representation of the classad.
        frontend_descript (glideFactoryConfig.FrontendDescript): Factory configuration's Frontend description object.
        pub_key_obj (object): The Factory public key object with encryption/decryption methods.

    Returns:
        tuple: A tuple containing:
            - sym_key_obj (object): The symmetric key object used for decryption.
            - frontend_sec_name (str): The frontend security name used for determining the username.

    Raises:
        CredentialError: If decryption fails or if the frontend is not authorized.
    """
    # we can get classads from multiple frontends, each with their own
    # sym keys.  So get the sym_key_obj for each classad
    sym_key_obj = get_key_obj(pub_key_obj, classad)
    authenticated_identity = classad["AuthenticatedIdentity"]

    # verify that the identity that the client claims to be is the identity that Condor thinks it is
    try:
        enc_identity = sym_key_obj.decrypt_hex(classad["ReqEncIdentity"]).decode("utf-8")
    except Exception:
        error_str = "Cannot decrypt ReqEncIdentity."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)

    if enc_identity != authenticated_identity:
        error_str = "Client provided invalid ReqEncIdentity(%s!=%s). " "Skipping for security reasons." % (
            enc_identity,
            authenticated_identity,
        )
        raise CredentialError(error_str)
    try:
        frontend_sec_name = sym_key_obj.decrypt_hex(classad["GlideinEncParamSecurityName"]).decode("utf-8")
    except Exception:
        error_str = "Cannot decrypt GlideinEncParamSecurityName."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)

    # verify that the frontend is authorized to talk to the factory
    expected_identity = frontend_descript.get_identity(frontend_sec_name)
    if expected_identity is None:
        error_str = "This frontend is not authorized by the factory.  Supplied security name: %s" % frontend_sec_name
        raise CredentialError(error_str)
    if authenticated_identity != expected_identity:
        error_str = "This frontend Authenticated Identity, does not match the expected identity"
        raise CredentialError(error_str)

    return sym_key_obj, frontend_sec_name


def check_security_credentials(auth_method, params, client_int_name, entry_name, scitoken_passthru=False):
    """Check that only the credentials for the given authentication method are in the parameters list.

    This function verifies that the provided parameters contain only those credentials
    that are required by the specified authentication method.

    Args:
        auth_method (str): This entry authentication method defined in the configuration.
        params (dict): Decrypted parameters from the Frontend (client) request.
        client_int_name (str): The internal client name.
        entry_name (str): The name of the entry.
        scitoken_passthru (bool, optional): If True, allows a scitoken to override checks for the authentication method.
            Defaults to False.

    Raises:
        CredentialError: If the credentials in params do not match what is required for the authentication method.
    """
    auth_method_list = auth_method.split("+")
    if not set(auth_method_list) & set(SUPPORTED_AUTH_METHODS):
        logSupport.log.warning(
            "None of the supported auth methods %s in provided auth methods: %s"
            % (SUPPORTED_AUTH_METHODS, auth_method_list)
        )
        return

    params_keys = set(params.keys())
    relevant_keys = {
        "SubmitProxy",
        "GlideinProxy",
        "Username",
        "Password",
        "PublicCert",
        "PrivateCert",
        "PublicKey",
        "PrivateKey",
        "VMId",
        "VMType",
        "AuthFile",
    }

    if "scitoken" in auth_method_list or "frontend_scitoken" in params and scitoken_passthru:
        # TODO  check validity
        # TODO  Specifically, Add checks that no undesired credentials are
        #       sent also when token is used
        return
    if "grid_proxy" in auth_method_list:
        if not scitoken_passthru:
            if "SubmitProxy" in params:
                # v3+ protocol
                valid_keys = {"SubmitProxy"}
                invalid_keys = relevant_keys.difference(valid_keys)
                if params_keys.intersection(invalid_keys):
                    raise CredentialError(
                        "Request from %s has credentials not required by the entry %s, skipping request"
                        % (client_int_name, entry_name)
                    )
            else:
                # No proxy sent
                raise CredentialError(
                    "Request from client %s did not provide a proxy as required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

    else:
        # Only v3+ protocol supports non grid entries
        # Verify that the glidein proxy was provided for non-proxy auth methods
        if "GlideinProxy" not in params and not scitoken_passthru:
            raise CredentialError("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)

        if "cert_pair" in auth_method_list:
            # Validate both the public and private certs were passed
            if not (("PublicCert" in params) and ("PrivateCert" in params)):
                # if not ('PublicCert' in params and 'PrivateCert' in params):
                # cert pair is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the certificate pair in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "PublicCert", "PrivateCert", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "key_pair" in auth_method_list:
            # Validate both the public and private keys were passed
            if not (("PublicKey" in params) and ("PrivateKey" in params)):
                # key pair is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the key pair in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "PublicKey", "PrivateKey", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "auth_file" in auth_method_list:
            # Validate auth_file is passed
            if "AuthFile" not in params:
                # auth_file is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the auth_file in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "AuthFile", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        elif "username_password" in auth_method_list:
            # Validate username and password keys were passed
            if not (("Username" in params) and ("Password" in params)):
                # username and password is required, cannot service request
                raise CredentialError(
                    "Client '%s' did not specify the username and password in the request, this is required by entry %s, skipping "
                    % (client_int_name, entry_name)
                )
            # Verify no other credentials were passed
            valid_keys = {"GlideinProxy", "Username", "Password", "VMId", "VMType"}
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError(
                    "Request from %s has credentials not required by the entry %s, skipping request"
                    % (client_int_name, entry_name)
                )

        else:
            # should never get here, unsupported main authentication method is checked at the beginning
            raise CredentialError("Inconsistency between SUPPORTED_AUTH_METHODS and check_security_credentials")

    # No invalid credentials found
    return


def compress_credential(credential_data):
    """Compress credential data using gzip and encode it in base64.

    Args:
        credential_data (bytes): The credential data to compress.

    Returns:
        bytes: The compressed and base64-encoded credential data.
    """
    with io.BytesIO() as cfile:
        with gzip.GzipFile(fileobj=cfile, mode="wb") as f:
            # Calling a GzipFile object's close() method does not close fileobj, so cfile is available outside
            f.write(credential_data)
        return base64.b64encode(cfile.getvalue())


def safe_update(fname, credential_data):
    """Safely update a file with the provided credential data.

    If the file does not exist, it is created. If it exists, the file is updated
    only if the content has changed, with a backup created if necessary.

    Args:
        fname (str): The filename of the credential file.
        credential_data (bytes or str): The credential data to write.
    """
    logSupport.log.debug(f"Creating/updating credential file {fname}")
    if not os.path.isfile(fname):
        # new file, create
        with os.open(fname, os.O_CREAT | os.O_WRONLY, 0o600) as fd:
            os.write(fd, credential_data)
    else:
        # old file exists, check if same content
        with open(fname) as fl:
            old_data = fl.read()

        #  if proxy_data == old_data nothing changed, done else
        if not (credential_data == old_data):
            # proxy changed, need to update
            # remove any previous backup file, if it exists
            try:
                os.remove(fname + ".old")
            except OSError:
                pass  # just protect

            # create new file
            with os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0o600) as fd:
                os.write(fd, credential_data)

            # copy the old file to a tmp bck and rename new one to the official name
            try:
                shutil.copy2(fname, fname + ".old")
            except (OSError, shutil.Error):
                # file not found, permission error, same file
                pass  # just protect

            os.rename(fname + ".new", fname)
