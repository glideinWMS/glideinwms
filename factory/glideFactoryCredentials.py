"""
Created on Jun 21, 2011

@author: tiradani
"""
import os
import re
import sys
import pwd
import binascii
import traceback

import glideFactoryLib
import condorPrivsep
import condorMonitor


MY_USERNAME = pwd.getpwuid(os.getuid())[0]

# defining new exception so that we can catch only the credential errors here
# and let the "real" errors propagate up
class CredentialError(Exception): pass

class SubmitCredentials:
    """
    Data class containing all information needed to submit a glidein.
    """
    def __init__(self, username, security_class):
        self.username = username # are we using privsep or not
        self.security_class = security_class # is this needed?  why are we passing this?
        self.id = None # id used for tracking the credentials used for submitting in the schedd
        self.cred_dir = ''  # location of credentials
        self.security_credentials = {} # dict of credentials
        self.identity_credentials = {} # identity informatin passed by frontend

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
        output += "username = ", self.username
        output += "security class = ", self.security_class
        output += "id = ", self.id
        output += "cedential dir = ", self.cred_dir
        output += "security credentials: "
        for sc in self.security_credentials.keys():
            output += "    %s : %s" % (sc, self.security_credentials[sc])
        output += "identity credentials: "
        for ic in self.identity_credentials.keys():
            output += "    %s : %s" % (ic, self.identity_credentials[ic])
        return output

def update_credential_file(username, client_id, proxy_data):
    """
    Updates the credential file.
    """
    factoryConfig = glideFactoryLib.FactoryConfig()

    proxy_dir = factoryConfig.get_client_proxies_dir(username)
    fname_short = 'credential_%s' % glideFactoryLib.escapeParam(client_id)
    fname = os.path.join(proxy_dir, fname_short)

    if username != MY_USERNAME:
        # use privsep
        # all args go through the environment, so they are protected
        update_credential_env = ['HEXDATA=%s' % binascii.b2a_hex(proxy_data), 'FNAME=%s' % fname]
        for var in ('PATH', 'LD_LIBRARY_PATH', 'PYTHON_PATH'):
            if os.environ.has_key(var):
                update_credential_env.append('%s=%s' % (var, os.environ[var]))

        try:
            condorPrivsep.execute(username, factoryConfig.submit_dir, os.path.join(factoryConfig.submit_dir, 'update_proxy.py'), ['update_proxy.py'], update_credential_env)
        except condorPrivsep.ExeError, e:
            raise RuntimeError, "Failed to update credential %s in %s (user %s): %s" % (client_id, proxy_dir, username, e)
        except:
            raise RuntimeError, "Failed to update credenital %s in %s (user %s): Unknown privsep error" % (client_id, proxy_dir, username)
        return fname
    else:
        # do it natively when you can
        if not os.path.isfile(fname):
            # new file, create
            fd = os.open(fname, os.O_CREAT | os.O_WRONLY, 0600)
            try:
                os.write(fd, proxy_data)
            finally:
                os.close(fd)
            return fname

        # old file exists, check if same content
        fl = open(fname, 'r')
        try:
            old_data = fl.read()
        finally:
            fl.close()
        if proxy_data == old_data:
            # nothing changed, done
            return fname

        #
        # proxy changed, neeed to update
        #

        # remove any previous backup file
        try:
            os.remove(fname + ".old")
        except:
            pass # just protect

        # create new file
        fd = os.open(fname + ".new", os.O_CREAT | os.O_WRONLY, 0600)
        try:
            os.write(fd, proxy_data)
        finally:
            os.close(fd)

        # move the old file to a tmp and the new one into the official name
        try:
            os.rename(fname, fname + ".old")
        except:
            pass # just protect
        os.rename(fname + ".new", fname)
        return fname

def get_globals_classads():
    status_constraint = '(GlideinMyType=?="glideclientglobal")'

    status = condorMonitor.CondorStatus("any")
    status.require_integrity(True) # important, this dictates what gets submitted

    status.load(status_constraint)

    data = status.fetchStored()
    return data

def process_globals(glidein_descript, frontend_descript):
    # Factory public key must exist for decryption 
    pub_key_obj = glidein_descript.data['PubKeyObj']
    if pub_key_obj == None:
        raise CredentialError("Factory has no public key.  We cannot decrypt.")

    try:
        classads = get_globals_classads()
        for classad in classads:
            # Get the frontend security name so that we can look up the username
            sym_key_obj, frontend_sec_name = validate_frontend(classad, frontend_descript, pub_key_obj)
            
            # get all the credential ids by filtering keys by regex
            # this makes looking up specific values in the dict easier
            r = re.compile("^GlideinEncParamSecurityClass")
            mkeys = filter(r.match, classad.keys())
            for key in mkeys:
                proxy_id = key.lstrip("GlideinEncParamSecurityClass")
                
                proxy_data = sym_key_obj.decrypt_hex(classad["GlideinEncParam%s" % proxy_id])
                security_class = sym_key_obj.decrypt_hex(classad[key])
                username = frontend_descript.get_username(security_class, frontend_sec_name)
                
                update_credential_file(username, proxy_id, proxy_data)
    except:
        tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        error_str = "Error occurred processing the globals classads. \nTraceback: \n%s" % tb
        raise CredentialError(error_str)

def get_key_obj(pub_key_obj, classad):
    if classad.has_key('ReqEncKeyCode'):
        try:
            sym_key_obj = pub_key_obj.extract_sym_key(classad['ReqEncKeyCode'])
            return sym_key_obj
        except:
            tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
            error_str = "Symmetric key extraction failed. \nTraceback: \n%s" % tb
            raise CredentialError(error_str)
    else:
        error_str = "Classad does not contain a key.  We cannot decrypt."
        raise CredentialError(error_str)

def validate_frontend(classad, frontend_descript, pub_key_obj):
    # we can get classads from multiple frontends, each with their own
    # sym keys.  So get the sym_key_obj for each classad
    sym_key_obj = get_key_obj(pub_key_obj, classad)
    authenticated_identity = classad["AuthenticatedIdentity"]
    frontend_sec_name = classad["SecurityName"] 

    # verify that the identity that the client claims to be is the identity that Condor thinks it is 
    try:
        enc_identity = sym_key_obj.decrypt_hex(classad['ReqEncIdentity'])
    except:
        tb = traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        error_str = "Cannot decrypt ReqEncIdentity.  \nTraceback: \n%s" % tb
        raise CredentialError(error_str)
        
    if enc_identity != authenticated_identity:
        error_str = "Client provided invalid ReqEncIdentity(%s!=%s). " \
                    "Skipping for security reasons." % (enc_identity, authenticated_identity)
        raise CredentialError(error_str)
        
    # verify that the frontend is authorized to talk to the factory
    expected_identity = frontend_descript.get_identity(frontend_sec_name)
    if expected_identity == None:
        error_str = "This frontend is not authorized by the factory.  Supplied security name: %s" % frontend_sec_name 
        raise CredentialError(error_str)
    if authenticated_identity != expected_identity:
        error_str = "This frontend Authenticated Identity, does not match the expected identity"   
        raise CredentialError(error_str)
    
    return sym_key_obj, frontend_sec_name
