#!/usr/bin/python3

import os
import shutil
import sys
import tempfile
import time

from glideinwms.lib import (
    subprocessSupport,
    token_util,
)

# This is a generic implementation of the the Scitoken plugin interface.
# VOs would implement their own version of this to interact with the 
# token issuer for that VO. 

def get_credential(logger, group, entry, trust_domain):
    """
    Generates a credential given the parameters. This is called once
    per group, per entry. It is a good idea for the VO to do some
    caching here so that new tokens are only generated when required.
    """

    tkn_file = ''
    tkn_str = ''
    tkn_max_lifetime = 3600
    tkn_lifetime = tkn_max_lifetime
    tmpnm = ''

    script_name = '/usr/sbin/frontend_scitoken'

    audience = None
    if 'gatekeeper' in entry:
        audience = entry['gatekeeper'].split()[-1]

    tkn_dir = '/var/lib/gwms-frontend/tokens.d'
    if not os.path.exists(tkn_dir):
        os.mkdir(tkn_dir,0o700)
    tkn_file = tkn_dir + '/' + group + "." +  entry['name'] + ".scitoken"

    try:
        # only generate a new token if the file is expired
        tkn_age = sys.maxsize
        if os.path.exists(tkn_file):
            tkn_age = time.time() - os.stat(tkn_file).st_mtime
        if tkn_age > tkn_max_lifetime - 600: # renew slightly before token expires
            (fd, tmpnm) = tempfile.mkstemp()
            cmd = "%s %s %s %s" % (script_name, audience, entry['name'], group)
            tkn_str = subprocessSupport.iexe_cmd(cmd)
            os.write(fd, tkn_str.encode('utf-8'))
            os.close(fd)
            shutil.move(tmpnm, tkn_file)
            os.chmod(tkn_file, 0o600)
            logger.debug("created token %s" % tkn_file)
        elif os.path.exists(tkn_file):
            with open(tkn_file, 'r') as fbuf:
                for line in fbuf:
                    tkn_str += line
            tkn_str = tkn_str.strip()
            tkn_lifetime = tkn_max_lifetime - tkn_age
    except Exception as err:        
        logger.warning('failed to create %s' % tkn_file)
    finally:
        if os.path.exists(tmpnm):
            os.remove(tmpnm)
    
    return tkn_str, tkn_lifetime


