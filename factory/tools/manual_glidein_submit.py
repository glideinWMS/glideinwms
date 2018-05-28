#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import pprint
import logging
import argparse

import htcondor

from glideinwms.factory import glideFactoryConfig as gfc
from glideinwms.factory.glideFactoryLib import ClientWeb
from glideinwms.factory.glideFactoryLib import escapeParam
from glideinwms.factory.glideFactoryLib import FactoryConfig
from glideinwms.factory.glideFactoryLib import submitGlideins
from glideinwms.factory.glideFactoryCredentials import SubmitCredentials
from glideinwms.factory.glideFactoryCredentials import validate_frontend


def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Submit a test pilot for a particular entry\n\n'

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        '--wms-collector', type=str, action='store', dest='wms_collector',
        default='gfactory-1.t2.ucsd.edu',
        help='COLLECTOR_HOST for WMS Collector (default: gfactory-1.t2.ucsd.edu)')

    parser.add_argument(
        '--req-name', type=str, action='store', dest='req_name',
        help='Factory submission info: Name of the glideclient classad')

    parser.add_argument(
        '--entry-name', type=str, action='store', dest='entry_name',
        help='Factory entry info: Name of the glideclient classad')

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        default=False,
        help='Enable debug logging')

    options = parser.parse_args()

    if options.req_name is None:
        logging.error('Missing required option "--req-name"')
        sys.exit(1)

    if options.entry_name is None:
        logging.error('Missing required option "--entry-name"')
        sys.exit(1)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)

    return options


def log_debug(msg, header=''):
    """ Simpleutility log function to print the glideclient classad
    """
    if header:
        logging.debug('=' * (len(header) + 2))
        logging.debug(' %s ', header)
        logging.debug('=' * (len(header) + 2))
    logging.debug(pprint.pformat(msg))


def main():
    """ The main module
    """
    # Move to the working direcotry
    try:
        os.chdir("/var/lib/gwms-factory/work-dir/")
    except OSError as ose:
        logging.error("Cannot chdir to /var/lib/gwms-factory/work-dir/: %s", ose)
        return 1

    # Parse command line options
    options = parse_opts()
    req_name = options.req_name
    entry_name = options.entry_name
    wms_collector = options.wms_collector

    # Set some variables needed later on
    params = {}
    status_sf = {}
    nr_glideins = 1
    idle_lifetime = 3600
    factory_config = FactoryConfig()
    glidein_descript = gfc.GlideinDescript()
    frontend_descript = gfc.FrontendDescript()
    collector = htcondor.Collector(wms_collector)
    factory_config.submit_dir = '/var/lib/gwms-factory/work-dir'
    constraint_gc = '(MyType=="glideclient") && (Name=="%s")' % (req_name)

    ads_gc = collector.query(htcondor.AdTypes.Master, constraint_gc)
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
        client_name = ad_gc['ClientName'] # GlideinClient
        # GlideinFrontendName
        frontend_name = "%s:%s" % (frontend_sec_name, security_class)

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
            logging.info("Problems getting credential file using credentials.add_security_credential. Check file %s permissions", fname)

        # Set the arguments
        params['CONDOR_VERSION'] = 'default'
        params['CONDOR_OS'] = 'default'
        params['CONDOR_ARCH'] = 'default'
        params['GLIDECLIENT_ReqNode'] = escapeParam(ad_gc['GlideinParamGLIDECLIENT_ReqNode'])
        params['GLIDECLIENT_Rank'] = ad_gc['GlideinParamGLIDECLIENT_Rank']
        params['GLIDEIN_Collector'] = escapeParam(ad_gc['GlideinParamGLIDEIN_Collector'])
        params['USE_MATCH_AUTH'] = ad_gc['GlideinParamUSE_MATCH_AUTH']
        params['Report_Failed'] = 'NEVER'

        # Now that we have everything submit the pilot!
        submitGlideins(entry_name, client_name, int(nr_glideins), idle_lifetime,
                       frontend_name, credentials, client_web, params,
                       status_sf, log=logging, factoryConfig=factory_config)

        return 0

if __name__ == '__main__':
    sys.exit(main())
