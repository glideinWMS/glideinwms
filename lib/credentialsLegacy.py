#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module holds deprecated credential functions.
NOTE: This will likely be removed in the future.
"""

import os
import sys

from glideinwms.lib import logSupport
from glideinwms.lib.generators import import_module

sys.path.append("/etc/gwms-frontend/plugin.d")
plugins = {}


def generate_credential(elementDescript, glidein_el, group_name, trust_domain):
    """Generates a credential with a credential generator plugin provided for the trust domain.

    Args:
        elementDescript (ElementMergedDescript): element descript
        glidein_el (dict): glidein element
        group_name (string): group name
        trust_domain (string): trust domain for the element

    Returns:
        string, None: Credential or None if not generated
    """

    ### The credential generator plugin should define the following function:
    # def get_credential(log:logger, group:str, entry:dict{name:str, gatekeeper:str}, trust_domain:str):
    # Generates a credential given the parameter

    # Args:
    # log:logger
    # group:str,
    # entry:dict{
    #     name:str,
    #     gatekeeper:str},
    # trust_domain:str,
    # Return
    # tuple
    #     token:str
    #     lifetime:int seconds of remaining lifetime
    # Exception
    # KeyError - miss some information to generate
    # ValueError - could not generate the token

    generator = None
    generators = elementDescript.element_data.get("CredentialGenerators")
    trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
    if not generators:
        generators = elementDescript.frontend_data.get("CredentialGenerators")
    if not trust_domain_data:
        trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
    if trust_domain_data and generators:
        generators_map = eval(generators)
        trust_domain_map = eval(trust_domain_data)
        for cfname in generators_map:
            if trust_domain_map[cfname] == trust_domain:
                generator = generators_map[cfname]
                logSupport.log.debug(f"found credential generator plugin {generator}")
                try:
                    if generator not in plugins:
                        plugins[generator] = import_module(generator)
                    entry = {
                        "name": glidein_el["attrs"].get("EntryName"),
                        "gatekeeper": glidein_el["attrs"].get("GLIDEIN_Gatekeeper"),
                        "factory": glidein_el["attrs"].get("AuthenticatedIdentity"),
                    }
                    stkn, _ = plugins[generator].get_credential(logSupport, group_name, entry, trust_domain)
                    return cfname, stkn
                except ModuleNotFoundError:
                    logSupport.log.warning(f"Failed to load credential generator plugin {generator}")
                except Exception as e:  # catch any exception from the plugin to prevent the frontend from crashing
                    logSupport.log.warning(f"Failed to generate credential: {e}.")

    return None, None


def get_scitoken(elementDescript, trust_domain):
    """Look for a local SciToken specified for the trust domain.

    Args:
        elementDescript (ElementMergedDescript): element descript
        trust_domain (string): trust domain for the element

    Returns:
        string, None: SciToken or None if not found
    """

    scitoken_fullpath = ""
    cred_type_data = elementDescript.element_data.get("ProxyTypes")
    trust_domain_data = elementDescript.element_data.get("ProxyTrustDomains")
    if not cred_type_data:
        cred_type_data = elementDescript.frontend_data.get("ProxyTypes")
    if not trust_domain_data:
        trust_domain_data = elementDescript.frontend_data.get("ProxyTrustDomains")
    if trust_domain_data and cred_type_data:
        cred_type_map = eval(cred_type_data)
        trust_domain_map = eval(trust_domain_data)
        for cfname in cred_type_map:
            if cred_type_map[cfname] == "scitoken":
                if trust_domain_map[cfname] == trust_domain:
                    scitoken_fullpath = cfname

    if os.path.exists(scitoken_fullpath):
        try:
            logSupport.log.debug(f"found scitoken {scitoken_fullpath}")
            stkn = ""
            with open(scitoken_fullpath) as fbuf:
                for line in fbuf:
                    stkn += line
            stkn = stkn.strip()
            return stkn
        except Exception as err:
            logSupport.log.exception(f"failed to read scitoken: {err}")

    return None
