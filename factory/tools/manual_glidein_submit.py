#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""manual_glidein_submit

Submit a test pilot for a particular entry.
The pilot will be submitted from the Factory without the need for a Frontend request.
"""

import argparse
import logging  # This script is using straight logging instead of logSupport or structlog
import os
import pprint
import socket
import sys

from glideinwms.creation.lib.factoryXmlConfig import parse
from glideinwms.factory import glideFactoryConfig as gfc
from glideinwms.factory.glideFactoryCredentials import SubmitCredentials, validate_frontend
from glideinwms.factory.glideFactoryLib import ClientWeb, FactoryConfig, set_condor_integrity_checks, submitGlideins

try:
    import htcondor  # pylint: disable=import-error
except ImportError:
    print("Python bindings not available. Exiting.")
    sys.exit(1)


def parse_opts():
    """Parse the command line options for this command.

    Returns:
        argparse.Namespace: An object containing all parsed command-line options.
    """
    description = "Submit a test pilot for a particular entry\n\n"

    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument(
        "--wms-collector",
        type=str,
        action="store",
        dest="wms_collector",
        help="COLLECTOR_HOST for WMS Collector (current hostname is the default)",
    )

    parser.add_argument(
        "--fe-name",
        type=str,
        action="store",
        dest="fe_name",
        help="Name of the frontend client to use (e.g.: frontend, fecmsglobal, ...). Its credential will be used for submission",
    )

    parser.add_argument(
        "--group-name",
        type=str,
        action="store",
        dest="group_name",
        default="main",
        help="Name of the frontend group to use (e.g.: frontend, fecmsglobal, ...). Its credential will be used for submission",
    )

    parser.add_argument(
        "--entry-name",
        type=str,
        action="store",
        dest="entry_name",
        help="Name of the entry you want to submit a pilot for",
    )

    parser.add_argument("--debug", action="store_true", dest="debug", default=False, help="Enable debug logging")

    options = parser.parse_args()

    if options.fe_name is None:
        logging.error('Missing required option "--fe-name"')
        sys.exit(1)

    if options.entry_name is None:
        logging.error('Missing required option "--entry-name"')
        sys.exit(1)

    if options.wms_collector is None:
        options.wms_collector = socket.gethostname()
        logging.info("Using %s as collector" % options.wms_collector)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format="%(levelname)s: %(message)s")
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        logging.getLogger().setLevel(logging.INFO)

    return options


def log_debug(msg, header=""):
    """Log a debug message with an optional header.

    Used to print the glideclient classad.

    Args:
        msg: The message to log (can be any object; it will be pretty-printed).
        header (str, optional): An optional header to prepend to the log message.
            If provided, it will be printed between separator lines. Defaults to an empty string.
    """
    """Simple utility log function to print the glideclient classad"""
    if header:
        logging.debug("=" * (len(header) + 2))
        logging.debug(" %s ", header)
        logging.debug("=" * (len(header) + 2))
    logging.debug(pprint.pformat(msg))


def get_reqname(collector, fe_name, group_name, entry_name):
    """Retrieve the request name from the collector for the specified frontend and entry.

    Args:
        collector (htcondor.Collector): The HTCondor collector object.
        fe_name (str): The name of the frontend client.
        group_name (str): The name of the frontend group.
        entry_name (str): The name of the entry.

    Returns:
        str: The request name for the specified parameters.

    Raises:
        SystemExit: If no matching frontend request is found.
    """
    constraint = 'MyType=="glideclient" && regexp("^{}@.*$", AuthenticatedIdentity) && regexp("^{}@.*$", ReqName) && GroupName=="{}" && GlideinEncParamSubmitProxy isnt undefined'.format(
        fe_name,
        entry_name,
        group_name,
    )
    res = collector.query(htcondor.AdTypes.Any, constraint, ["Name"])

    if len(res) == 0:
        logging.error("Could not find any frontend request for the specified entry/frontend pair using:")
        logging.error("condor_status -any -const '%s' -af Name" % constraint)
        sys.exit(1)

    return res[0]["Name"]


def main():
    """Main function to submit a test pilot for a specified entry.

    This function performs the following steps:
      1. Changes the working directory to the factory directory.
      2. Parses the configuration file.
      3. Parses command-line options.
      4. Retrieves the necessary credentials and configuration information.
      5. Submits the pilot using the submitGlideins function.

    Returns:
        int: 0 if successful, or a non-zero error code otherwise.
    """
    # Move to the working directory
    try:
        if "GLIDEIN_FACTORY_DIR" in os.environ:
            os.chdir(os.environ["GLIDEIN_FACTORY_DIR"])
        else:
            os.chdir("/var/lib/gwms-factory/work-dir/")
    except OSError as ose:
        logging.error("Cannot chdir to /var/lib/gwms-factory/work-dir/: %s", ose)
        return 1

    # Parse the configuration
    conf = parse("/etc/gwms-factory/glideinWMS.xml")

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

    req_name = get_reqname(collector, options.fe_name, options.group_name, entry_name)
    logging.debug("Using request name %s" % req_name)

    factory_config.submit_dir = conf.get_submit_dir()
    constraint_gc = '(MyType=="glideclient") && (Name=="%s")' % (req_name)

    ads_gc = collector.query(htcondor.AdTypes.Any, constraint_gc)
    if not ads_gc:
        logging.error("Cannot find glideclient classad using constraint %s", constraint_gc)
        return 1
    else:
        ad_gc = ads_gc[0]
        log_debug(ad_gc, header="glideclient classad")

        # Load factory config and get some info that will go in the pilot classad
        glidein_descript.load_pub_key()
        sym_key_obj, frontend_sec_name = validate_frontend(ad_gc, frontend_descript, glidein_descript.data["PubKeyObj"])
        security_class = sym_key_obj.decrypt_hex(ad_gc["GlideinEncParamSecurityClass"]).decode(
            "utf8"
        )  # GlideinSecurityClass
        proxyid = sym_key_obj.decrypt_hex(ad_gc["GlideinEncParamSubmitProxy"]).decode("utf8")
        user_name = frontend_descript.get_username(frontend_sec_name, security_class)

        # Prepare some values that ends up in the Arguments classad
        # of the pilot, i.e., the ClientWeb instance
        client_web_url = ad_gc["WebURL"]  # -clientweb
        client_signtype = ad_gc["WebSignType"]  # -signtype
        client_descript = ad_gc["WebDescriptFile"]  # -clientdescript
        client_sign = ad_gc["WebDescriptSign"]  # -clientsign
        client_group = ad_gc["GroupName"]  # -clientgroup
        client_group_web_url = ad_gc["WebGroupURL"]  # -clientwebgroup
        # -clientdescriptgroup
        client_group_descript = ad_gc["WebGroupDescriptFile"]
        client_group_sign = ad_gc["WebGroupDescriptSign"]  # -clientsigngroup
        client_web = ClientWeb(
            client_web_url,
            client_signtype,
            client_descript,
            client_sign,
            client_group,
            client_group_web_url,
            client_group_descript,
            client_group_sign,
        )

        # Create the submit_credentials object
        credentials = SubmitCredentials(user_name, security_class)
        credentials.id = proxyid
        credentials.cred_dir = conf.get_client_proxy_dirs()[user_name]
        credfname = "{}_{}".format(ad_gc["ClientName"], proxyid)
        if not credentials.add_security_credential("SubmitProxy", credfname):
            fname = os.path.join(credentials.cred_dir, "credential_%s" % credfname)
            logging.info(
                (
                    "Problems getting credential file using credentials.add_security_credential."
                    " Check file %s permissions"
                ),
                fname,
            )
        scitoken = "credential_{}_{}.scitoken".format(ad_gc["ClientName"], entry_name)
        scitoken_file = os.path.join(credentials.cred_dir, scitoken)
        if not os.path.exists(scitoken_file):
            logging.warning("Cannot find scitoken file %s" % scitoken_file)
        elif not credentials.add_identity_credential("frontend_scitoken", scitoken_file):
            logging.warning(
                "failed to add frontend_scitoken %s to identity credentials %s"
                % (scitoken_file, str(credentials.identity_credentials))
            )

        condortoken = "credential_{}_{}.idtoken".format(ad_gc["ClientName"], entry_name)
        condortoken_file = os.path.join(credentials.cred_dir, condortoken)
        if not os.path.exists(condortoken_file):
            logging.warning("Cannot find idtoken file %s" % condortoken_file)
        elif not credentials.add_identity_credential("frontend_condortoken", condortoken_file):
            logging.warning(
                "failed to add frontend_condortoken %s to the identity credentials %s"
                % (condortoken_file, str(credentials.identity_credentials))
            )

        # Set the arguments
        # I was using escapeParam for GLIDECLIENT_ReqNode and GLIDECLIENT_Collector but turned out it's not necessary
        params["CONDOR_VERSION"] = "default"
        params["CONDOR_OS"] = "auto"
        params["CONDOR_ARCH"] = "default"
        params["GLIDECLIENT_ReqNode"] = ad_gc["GlideinParamGLIDECLIENT_ReqNode"]
        params["GLIDECLIENT_Rank"] = ad_gc.get("GlideinParamGLIDECLIENT_Rank", "1")
        params["GLIDEIN_Collector"] = ad_gc["GlideinParamGLIDEIN_Collector"]
        params["USE_MATCH_AUTH"] = ad_gc["GlideinParamUSE_MATCH_AUTH"]
        params["Report_Failed"] = "NEVER"

        # Now that we have everything submit the pilot!
        logging.getLogger().setLevel(logging.DEBUG)
        submitGlideins(
            entry_name,
            "test.test",
            int(nr_glideins),
            idle_lifetime,
            "test:test",
            credentials,
            client_web,
            params,
            status_sf,
            log=logging.getLogger(),
            factoryConfig=factory_config,
        )

        return 0


if __name__ == "__main__":
    set_condor_integrity_checks()
    try:
        sys.exit(main())
    except OSError as ioe:
        if ioe.errno == 13:  # Permission denied when accessing the credential
            logging.error("Try to run the command as gfactory. Error: %s" % ioe)
        else:
            raise
