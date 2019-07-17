#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import pprint
import socket
import logging
import argparse

try:
    import htcondor # pylint: disable=import-error
except:
    print("Python bindings not available. Exiting.")
    sys.exit(1)

from glideinwms.factory import glideFactoryConfig as gfc
from glideinwms.factory.glideFactoryLib import ClientWeb
from glideinwms.factory.glideFactoryLib import escapeParam
from glideinwms.factory.glideFactoryLib import FactoryConfig
from glideinwms.factory.glideFactoryLib import submitGlideins
from glideinwms.factory.glideFactoryCredentials import SubmitCredentials
from glideinwms.factory.glideFactoryCredentials import validate_frontend
from glideinwms.factory.glideFactoryLib import set_condor_integrity_checks


def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Submit a test pilot for a particular entry\n\n'

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '--wms-collector', type=str, action='store', dest='wms_collector',
        help='COLLECTOR_HOST for WMS Collector (current hostname is the default)')

    parser.add_argument(
        '--fe-name', type=str, action='store', dest='fe_name',
        help='Name of the frontend client to use (e.g.: frontent, fecmsglobal, ...). Its credential will be used for submission')

    parser.add_argument(
        '--entry-name', type=str, action='store', dest='entry_name',
        help='Name of the entry you want to submit a pilot for')

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        default=False,
        help='Enable debug logging')

    options = parser.parse_args()

    if options.fe_name is None:
        logging.error('Missing required option "--fe-name"')
        sys.exit(1)

    if options.entry_name is None:
        logging.error('Missing required option "--entry-name"')
        sys.exit(1)

    if options.wms_collector is None:
        options.wms_collector = socket.gethostname()
        logging.info('Using %s as collector' % options.wms_collector)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s')
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    return options


def log_debug(msg, header=''):
    """ Simple utility log function to print the glideclient classad
    """
    if header:
        logging.debug('=' * (len(header) + 2))
        logging.debug(' %s ', header)
        logging.debug('=' * (len(header) + 2))
    logging.debug(pprint.pformat(msg))


def get_reqname(collector, fe_name, entry_name):
    constraint = 'MyType=="glideclient" && regexp("^%s@.*$", AuthenticatedIdentity) && regexp("^%s@.*$", ReqName)' % (fe_name, entry_name)
    res = collector.query(htcondor.AdTypes.Any, constraint, ["Name"])

    if len(res) == 0:
        logging.error("Could not find any frontend request for the specified entry/frontend pair using:")
        logging.error("condor_status -any -const '%s' -af Name" % constraint)
        sys.exit(1)

    return res[0]['Name']


def main():
    """ The main module
    """
    # Move to the working direcotry
    try:
        if "GLIDEIN_FACTORY_DIR" in os.environ:
            os.chdir(os.environ["GLIDEIN_FACTORY_DIR"])
        else:
            os.chdir("/var/lib/gwms-factory/work-dir/")
    except OSError as ose:
        logging.error("Cannot chdir to /var/lib/gwms-factory/work-dir/: %s", ose)
        return 1

    # Parse command line options
    options = parse_opts()
    entry_name = options.entry_name
    wms_collector = options.wms_collector

    # Set some variables needed later on
    params = {}
    status_sf = {}
    nr_glideins = 1
    idle_lifetime = 3600 * 24
    factory_config = FactoryConfig()
    glidein_descript = gfc.GlideinDescript()
    frontend_descript = gfc.FrontendDescript()
    collector = htcondor.Collector(wms_collector)

    req_name = get_reqname(collector, options.fe_name, entry_name)
    logging.debug("Using reques name %s" % req_name)

    factory_config.submit_dir = '/var/lib/gwms-factory/work-dir'
    constraint_gc = '(MyType=="glideclient") && (Name=="%s")' % (req_name)

    ads_gc = collector.query(htcondor.AdTypes.Any, constraint_gc)
    if not ads_gc:
        logging.error("Cannot find glideclient classad using constraint %s",
                      constraint_gc)
        return 1
    else:
        ad_gc = ads_gc[0]
        log_debug(ad_gc, header='glideclient classad')

        # Load factory config and get some info that will go in the pilot classad
        glidein_descript.load_pub_key()
        sym_key_obj, frontend_sec_name = validate_frontend(
            ad_gc, frontend_descript, glidein_descript.data['PubKeyObj'])
        security_class = sym_key_obj.decrypt_hex(
            ad_gc['GlideinEncParamSecurityClass']) # GlideinSecurityClass
        proxyid = sym_key_obj.decrypt_hex(ad_gc['GlideinEncParamSubmitProxy'])
        user_name = frontend_descript.get_username(
            frontend_sec_name, security_class)

        # Prepare some values that ends up in the Arguments classad
        # of the pilot, i.e., the ClientWeb instance
        client_web_url = ad_gc['WebURL'] # -clientweb
        client_signtype = ad_gc['WebSignType'] # -signtype
        client_descript = ad_gc['WebDescriptFile'] # -clientdescript
        client_sign = ad_gc['WebDescriptSign'] # -clientsign
        client_group = ad_gc['GroupName'] # -clientgroup
        client_group_web_url = ad_gc['WebGroupURL'] # -clientwebgroup
        # -clientdescriptgroup
        client_group_descript = ad_gc['WebGroupDescriptFile']
        client_group_sign = ad_gc['WebGroupDescriptSign'] # -clientsigngroup
        client_web = ClientWeb(
            client_web_url, client_signtype, client_descript, client_sign,
            client_group, client_group_web_url, client_group_descript,
            client_group_sign)

        # Create the submit_credentials object
        credentials = SubmitCredentials(user_name, security_class)
        credentials.id = proxyid
        credentials.cred_dir = '/var/lib/gwms-factory/client-proxies/user_%s/glidein_gfactory_instance' % user_name
        credfname = '%s_%s' % (ad_gc['ClientName'], proxyid)
        if not credentials.add_security_credential('SubmitProxy', credfname):
            fname = os.path.join(credentials.cred_dir,
                                 'credential_%s' % credfname)
            logging.info(("Problems getting credential file using credentials.add_security_credential."
                         " Check file %s permissions"), fname)

        # Set the arguments
        params['CONDOR_VERSION'] = 'default'
        params['CONDOR_OS'] = 'default'
        params['CONDOR_ARCH'] = 'default'
        params['GLIDECLIENT_ReqNode'] = escapeParam(ad_gc['GlideinParamGLIDECLIENT_ReqNode'])
        params['GLIDECLIENT_ReqNode'] = ad_gc['GlideinParamGLIDECLIENT_ReqNode']
        params['GLIDECLIENT_Rank'] = ad_gc.get('GlideinParamGLIDECLIENT_Rank', "1")
        params['GLIDEIN_Collector'] = escapeParam(ad_gc['GlideinParamGLIDEIN_Collector'])
        params['GLIDEIN_Collector'] = ad_gc['GlideinParamGLIDEIN_Collector']
        params['USE_MATCH_AUTH'] = ad_gc['GlideinParamUSE_MATCH_AUTH']
        params['Report_Failed'] = 'NEVER'

        # Now that we have everything submit the pilot!
        logging.getLogger().setLevel(logging.DEBUG)
        res = submitGlideins(entry_name, "test.test", int(nr_glideins), idle_lifetime,
                       "test:test", credentials, client_web, params,
                       status_sf, log=logging.getLogger(), factoryConfig=factory_config)

        return 0

if __name__ == '__main__':
    set_condor_integrity_checks()
    try:
        sys.exit(main())
    except IOError as ioe:
        if ioe.errno==13: # Permission denied when accessing the credential
            logging.error("Try to run the command as gfactory. Error: %s" % ioe)
        else:
            raise
