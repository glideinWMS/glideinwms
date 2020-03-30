"""
Created on Jun 21, 2011

@author: tiradani
"""
from __future__ import absolute_import
import os
import re
import sys
import pwd
import binascii
import traceback
import gzip
import cStringIO
import base64

from . import glideFactoryLib
from . import glideFactoryInterface

from glideinwms.lib import condorMonitor
from glideinwms.lib import logSupport

MY_USERNAME = pwd.getpwuid(os.getuid())[0]
SUPPORTED_AUTH_METHODS = ['grid_proxy',
                          'cert_pair',
                          'key_pair',
                          'auth_file',
                          'username_password',
                          'condor_token',
                          'sci_token' ]

# defining new exception so that we can catch only the credential errors here
# and let the "real" errors propagate up
class CredentialError(Exception):
    pass


class SubmitCredentials:
    """
    Data class containing all information needed to submit a glidein.
    """
    def __init__(self, username, security_class):
        self.username = username
        self.security_class = security_class  # Seems redundant info
        self.id = None  # id used for tracking the submit credentials
        self.cred_dir = ''  # location of credentials
        self.security_credentials = {}  # dict of credentials
        self.identity_credentials = {}  # identity information passed by frontend

    def add_security_credential(self, cred_type, filename):
        """
        Adds a security credential.
        """
        if not glideFactoryLib.is_str_safe(filename):
            return False

        cred_fname = os.path.join(self.cred_dir, 'credential_%s' % filename)
        if not os.path.isfile(cred_fname):
            return False

        self.security_credentials[cred_type] = cred_fname
        return True

    def add_factory_credential(self, cred_type, absfname):
        """
        Adds a factory provided security credential.
        """
        if not os.path.isfile(absfname):
            return False

        self.security_credentials[cred_type] = absfname
        return True

    def add_identity_credential(self, cred_type, cred_str):
        """
        Adds an identity credential.
        """
        self.identity_credentials[cred_type] = cred_str
        return True

    def __repr__(self):
        output = "SubmitCredentials"
        output += "username = %s; " % self.username
        output += "security class = %s; " % str(self.security_class)
        output += "id = %s; " % self.id
        output += "cedential dir = %s; " % self.cred_dir
        output += "security credentials: "
        for sck, scv in self.security_credentials.iteritems():
            output += "    %s : %s; " % (sck, scv)
        output += "identity credentials: "
        for ick, icv in self.identity_credentials.iteritems():
            output += "    %s : %s; " % (ick, icv)
        return output


def update_credential_file(username, client_id, credential_data, request_clientname):
    """
    Updates the credential file

    :param username: credentials' username
    :param client_id: id used for tracking the submit credentials
    :param credential_data: the credentials to be advertised
    :param request_clientname: client name passed by frontend
    :return:the credential file updated
    """

    proxy_dir = glideFactoryLib.factoryConfig.get_client_proxies_dir(username)
    fname_short = 'credential_%s_%s' % (request_clientname, glideFactoryLib.escapeParam(client_id))
    fname = os.path.join(proxy_dir, fname_short)
    fname_compressed = "%s_compressed" % fname

    msg = "updating credential file %s" % fname
    logSupport.log.debug(msg)

    safe_update(fname, credential_data)
    compressed_credential = compress_credential(credential_data)
    safe_update(fname_compressed, compressed_credential)

    return fname, fname_compressed


# Comment by Igor:
# This functionality should really be in glideFactoryInterface module
# Making a minimal patch now to get the desired functionality
def get_globals_classads(factory_collector=glideFactoryInterface.DEFAULT_VAL):
    if factory_collector==glideFactoryInterface.DEFAULT_VAL:
        factory_collector=glideFactoryInterface.factoryConfig.factory_collector

    status_constraint = '(GlideinMyType=?="glideclientglobal")'

    status = condorMonitor.CondorStatus("any", pool_name=factory_collector)
    status.require_integrity(True) # important, this dictates what gets submitted

    status.load(status_constraint)

    data = status.fetchStored()
    return data

def process_global(classad, glidein_descript, frontend_descript):
    # Factory public key must exist for decryption
    pub_key_obj = glidein_descript.data['PubKeyObj']
    if pub_key_obj is None:
        raise CredentialError("Factory has no public key.  We cannot decrypt.")

    try:
        # Get the frontend security name so that we can look up the username
        sym_key_obj, frontend_sec_name = validate_frontend(classad, frontend_descript, pub_key_obj)

        request_clientname = classad['ClientName']

        # get all the credential ids by filtering keys by regex
        # this makes looking up specific values in the dict easier
        r = re.compile("^GlideinEncParamSecurityClass")
        mkeys = filter(r.match, classad.keys())
        for key in mkeys:
            prefix_len = len("GlideinEncParamSecurityClass")
            cred_id = key[prefix_len:]

            cred_data = sym_key_obj.decrypt_hex(classad["GlideinEncParam%s" % cred_id])
            security_class = sym_key_obj.decrypt_hex(classad[key])
            username = frontend_descript.get_username(frontend_sec_name, security_class)

            msg = "updating credential for %s" % username
            logSupport.log.debug(msg)

            update_credential_file(username, cred_id, cred_data, request_clientname)
    except:
        logSupport.log.debug("\nclassad %s\nfrontend_descript %s\npub_key_obj %s)" % (classad, frontend_descript, pub_key_obj))
        error_str = "Error occurred processing the globals classads."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)


def get_key_obj(pub_key_obj, classad):
    """
    Gets the symmetric key object from the request classad

    @type pub_key_obj: object
    @param pub_key_obj: The factory public key object.  This contains all the encryption and decryption methods
    @type classad: dictionary
    @param classad: a dictionary representation of the classad
    """
    if 'ReqEncKeyCode' in classad:
        try:
            sym_key_obj = pub_key_obj.extract_sym_key(classad['ReqEncKeyCode'])
            return sym_key_obj
        except:
            logSupport.log.debug("\nclassad %s\npub_key_obj %s\n" % (classad, pub_key_obj))
            error_str = "Symmetric key extraction failed."
            logSupport.log.exception(error_str)
            raise CredentialError(error_str)
    else:
        error_str = "Classad does not contain a key.  We cannot decrypt."
        raise CredentialError(error_str)


def validate_frontend(classad, frontend_descript, pub_key_obj):
    """
    Validates that the frontend advertising the classad is allowed and that it
    claims to have the same identity that Condor thinks it has.

    @type classad: dictionary
    @param classad: a dictionary representation of the classad
    @type frontend_descript: class object
    @param frontend_descript: class object containing all the frontend information
    @type pub_key_obj: object
    @param pub_key_obj: The factory public key object.  This contains all the encryption and decryption methods

    @return: sym_key_obj - the object containing the symmetric key used for decryption
    @return: frontend_sec_name - the frontend security name, used for determining
    the username to use.
    """

    # we can get classads from multiple frontends, each with their own
    # sym keys.  So get the sym_key_obj for each classad
    sym_key_obj = get_key_obj(pub_key_obj, classad)
    authenticated_identity = classad["AuthenticatedIdentity"]

    # verify that the identity that the client claims to be is the identity that Condor thinks it is
    try:
        enc_identity = sym_key_obj.decrypt_hex(classad['ReqEncIdentity'])
    except:
        error_str = "Cannot decrypt ReqEncIdentity."
        logSupport.log.exception(error_str)
        raise CredentialError(error_str)

    if enc_identity != authenticated_identity:
        error_str = "Client provided invalid ReqEncIdentity(%s!=%s). " \
                    "Skipping for security reasons." % (enc_identity, authenticated_identity)
        raise CredentialError(error_str)
    try:
        frontend_sec_name = sym_key_obj.decrypt_hex(classad['GlideinEncParamSecurityName'])
    except:
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


def check_security_credentials(auth_method, params, client_int_name, entry_name):
    """
    Verify taht only credentials for the given auth method are in the params

    @type auth_method: string
    @param auth_method: authentication method of an entry, defined in the config
    @type params: dictionary
    @param params: decrypted params passed in a frontend (client) request
    @type client_int_name: string
    @param client_int_name: internal client name
    @type entry_name: string
    @param entry_name: name of the entry

    @raise CredentialError: if the credentials in params don't match what is defined for the auth method
    """

    auth_method_list = auth_method.split('+')
    if not set(auth_method_list) & set(SUPPORTED_AUTH_METHODS):
        logSupport.log.warning("None of the supported auth methods %s in provided auth methods: %s" %
                               (SUPPORTED_AUTH_METHODS, auth_method_list))
        return

    params_keys = set(params.keys())
    relevant_keys = set(['SubmitProxy', 'GlideinProxy', 'Username', 'Password',
                         'PublicCert', 'PrivateCert', 'PublicKey', 'PrivateKey',
                         'VMId', 'VMType', 'AuthFile'])

    if 'grid_proxy' in auth_method_list:
        if 'SubmitProxy' in params:
            # v3+ protocol
            valid_keys = set(['SubmitProxy'])
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError("Request from %s has credentials not required by the entry %s, skipping request" %
                                      (client_int_name, entry_name))
        else:
            # No proxy sent
            raise CredentialError("Request from client %s did not provide a proxy as required by the entry %s, skipping request" %
                                  (client_int_name, entry_name))

    else:
        # Only v3+ protocol supports non grid entries
        # Verify that the glidein proxy was provided for non-proxy auth methods
        if 'GlideinProxy' not in params:
            raise CredentialError("Glidein proxy cannot be found for client %s, skipping request" % client_int_name)

        if 'cert_pair' in auth_method_list:
            # Validate both the public and private certs were passed
            if not (('PublicCert' in params) and ('PrivateCert' in params)):
                # if not ('PublicCert' in params and 'PrivateCert' in params):
                # cert pair is required, cannot service request
                raise CredentialError("Client '%s' did not specify the certificate pair in the request, this is required by entry %s, skipping " %
                                      (client_int_name, entry_name))
            # Verify no other credentials were passed
            valid_keys = set(['GlideinProxy', 'PublicCert', 'PrivateCert', 'VMId', 'VMType'])
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError("Request from %s has credentials not required by the entry %s, skipping request" %
                                      (client_int_name, entry_name))

        elif 'key_pair' in auth_method_list:
            # Validate both the public and private keys were passed
            if not (('PublicKey' in params) and ('PrivateKey' in params)):
                # key pair is required, cannot service request
                raise CredentialError("Client '%s' did not specify the key pair in the request, this is required by entry %s, skipping " %
                                      (client_int_name, entry_name))
            # Verify no other credentials were passed
            valid_keys = set(['GlideinProxy', 'PublicKey', 'PrivateKey', 'VMId', 'VMType'])
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError("Request from %s has credentials not required by the entry %s, skipping request" %
                                      (client_int_name, entry_name))

        elif 'auth_file' in auth_method_list:
            # Validate auth_file is passed
            if not ('AuthFile' in params):
                # auth_file is required, cannot service request
                raise CredentialError("Client '%s' did not specify the auth_file in the request, this is required by entry %s, skipping " %
                                      (client_int_name, entry_name))
            # Verify no other credentials were passed
            valid_keys = set(['GlideinProxy', 'AuthFile', 'VMId', 'VMType'])
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError("Request from %s has credentials not required by the entry %s, skipping request" %
                                      (client_int_name, entry_name))

        elif 'username_password' in auth_method_list:
            # Validate username and password keys were passed
            if not (('Username' in params) and ('Password' in params)):
                # username and password is required, cannot service request
                raise CredentialError("Client '%s' did not specify the username and password in the request, this is required by entry %s, skipping " %
                                      (client_int_name, entry_name))
            # Verify no other credentials were passed
            valid_keys = set(['GlideinProxy', 'Username', 'Password', 'VMId', 'VMType'])
            invalid_keys = relevant_keys.difference(valid_keys)
            if params_keys.intersection(invalid_keys):
                raise CredentialError("Request from %s has credentials not required by the entry %s, skipping request" %
                                      (client_int_name, entry_name))

        else:
            # should never get here, unsupported main authentication method is checked at the beginning
            raise CredentialError("Inconsistency between SUPPORTED_AUTH_METHODS and check_security_credentials")

    # No invalid credentials found
    return


def compress_credential(credential_data):
    cfile = cStringIO.StringIO()
    f = gzip.GzipFile(fileobj=cfile, mode='wb')
    f.write(credential_data)
    f.close()
    return base64.b64encode(cfile.getvalue())


def safe_update(fname, credential_data):
    if not os.path.isfile(fname):
        # new file, create
        fd = os.open(fname, os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            os.write(fd, credential_data)
        finally:
            os.close(fd)
    else:
        # old file exists, check if same content
        fl = open(fname, 'r')
        try:
            old_data = fl.read()
        finally:
            fl.close()

        #  if proxy_data == old_data nothing changed, done else
        if not (credential_data == old_data):
            # proxy changed, neeed to update
            # remove any previous backup file, if it exists
            if os.path.isfile(fname + ".old"):
                os.remove(fname + ".old")

            # create new file
            fd = os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, credential_data)
            finally:
                os.close(fd)

            # move the old file to a tmp and the new one into the official name
            try:
                os.rename(fname, fname + ".old")
            except:
                pass  # just protect

            os.rename(fname + ".new", fname)
