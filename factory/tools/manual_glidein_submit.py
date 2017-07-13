#!/usr/bin/env python

from __future__ import print_function
from future import standard_library
standard_library.install_aliases()
import os
import sys
import configparser

STARTUP_DIR = sys.path[0]
sys.path.append(os.path.join(STARTUP_DIR, ".."))
sys.path.append(os.path.join(STARTUP_DIR, "../../lib"))

from glideinwms.factory.glideFactoryCredentials import SubmitCredentials
from glideinwms.factory.glideFactoryLib import submitGlideins
from glideinwms.factory.glideFactoryLib import ClientWeb
from glideinwms.lib.iniSupport import IniError
from glideinwms.lib.iniSupport import load_ini
from glideinwms.lib.iniSupport import cp_get

class ArgumentError(Exception): pass

def usage():
    msg = """
Usage: manual_glidein_submit <ini_file> 

  ini_file: (REQUIRED) This file contains all the required information for a 
            glidein to be submitted and run on a remote site.
"""
    print(sys.stderr, msg)

def check_args():
    if len(sys.argv) > 1:
        raise ArgumentError("Too many arguments!")
    if len(sys.argv) < 1:
        raise ArgumentError("You must specify an ini file!")

def main():
    try:
        check_args()
    except ArgumentError as ae:
        print(sys.stderr, ae)
        usage()

    try:
        ini_path = sys.argv[1]
        cp = load_ini(ini_path)

        # get all the required elements and create the required objects
        entry_name = cp_get(cp, "entry", "entry_name", "", throw_exception=True)
        client_name = cp_get(cp, "entry", "client_name", "", throw_exception=True)
        nr_glideins = cp_get(cp, "entry", "nr_glideins", "", throw_exception=True)
        frontend_name = cp_get(cp, "entry", "frontend_name", "", throw_exception=True)
        user_name = cp_get(cp, "submit_credentials", "UserName", "", throw_exception=True)
        security_class = cp_get(cp, "submit_credentials", "SecurityClass", "", throw_exception=True)

        # create the params object
        params = {}
        for option in cp.options("params"):
            params[option] = cp_get(cp, "params", option, "", throw_exception=True)

        # create the client_web object
        client_web_url = cp_get(cp, "client_web", "clientweb", "", throw_exception=True)
        client_signtype = cp_get(cp, "client_web", "clientsigntype", "", throw_exception=True)
        client_descript = cp_get(cp, "client_web", "clientdescript", "", throw_exception=True)
        client_sign = cp_get(cp, "client_web", "clientsign", "", throw_exception=True)
        client_group = cp_get(cp, "client_web", "clientgroup", "", throw_exception=True)
        client_group_web_url = cp_get(cp, "client_web", "clientwebgroup", "", throw_exception=True)
        client_group_descript = cp_get(cp, "client_web", "clientdescriptgroup", "", throw_exception=True)
        client_group_sign = cp_get(cp, "client_web", "clientsigngroup", "", throw_exception=True)

        client_web = ClientWeb(client_web_url, client_signtype, client_descript, client_sign,
                               client_group, client_group_web_url, client_group_descript, client_group_sign)

        # create the submit_credentials object
        credentials = SubmitCredentials(user_name, security_class)
        for option in cp.options("security_credentials"):
            credentials.add_security_credential(option, cp_get(cp, "security_credentials", option, "", throw_exception=True))

        for option in cp.options("identity_credentials"):
            credentials.add_identity_credential(option, cp_get(cp, "identity_credentials", option, "", throw_exception=True))

        # call the submit
        submitGlideins(entry_name, client_name, nr_glideins, frontend_name, credentials, client_web, params)

    except IniError as ie:
        print(sys.stderr, "ini file error make this message better")
    except Exception as ex:
        print(sys.stderr, "general error make this message better")

if __name__ == "__main__":
    sys.exit(main())
