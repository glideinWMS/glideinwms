#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains the IdTokenGenerator class
"""

import getpass
import os
import socket

from glideinwms.lib import defaults
from glideinwms.lib.credentials import create_credential, credential_type_from_string
from glideinwms.lib.generators import export_generator
from glideinwms.lib.generators.credential_generator import CredentialGenerator
from glideinwms.lib.token_util import create_and_sign_token


class IdTokenGenerator(CredentialGenerator):
    """IDTOKEN generator

    This generator creates an IDTOKEN using the provided context or information from the configuration file
    (IDTokenKeyname, IDTokenLifetime).

    The token identity (sub) is the `identity` from the context, if provided, or NAME@HOSTNAME, where
    HOSTNAME is the fully qualified domain name of the host where the token is generated, and
    NAME is the GLIDEIN_Site attribute form the resource/entry classad and configuration in the Factory, or
    the name of the resource/entry from the classad and configuration in the Factory if GLIDEIN_Site is not specified.
    This aims to create different subjects for different resources/entries to avoid the reuse of tokes from potentially
    compromised resources.

    The issuer defaults to the HTCondor TRUST_DOMAIN when not specified in the context.

    A duration of 0 seconds means that the token will never expire. A negative value will generate expired tokens.
    The default duration (if not in the context or IDTokenLifetime) is 24 hours.

    The default password file name is the username (if not in the context or IDTokenKeyname), all uppercase.
    """

    def _setup(self):
        self.context.validate(
            {
                "password": (str, ""),
                "scope": (str, ""),
                "duration": (int, 0),
                "minimum_lifetime": (int, 0),
                "identity": (str, ""),
                "issuer": (str, None),
            }
        )
        self.context["type"] = "idtoken"

    def _generate(self, **kwargs):
        """Generate an IDTOKEN token.

        Args:
            **kwargs: expected arguments:
                glidein_el: the attributes of the glidefactory classad form the Factory (from the configuration and stats).
                    Required unless `identity` is specified in the context
                elementDescript: the client/Frontend group configuration attributes
                    Required unless `password` and `duration` are specified in the context

        Returns:
            An IDTOKEN token.
        """
        password = self.context["password"] or os.path.join(
            defaults.pwd_dir, kwargs["elementDescript"].merged_data.get("IDTokenKeyname", getpass.getuser().upper())
        )

        scope = self.context["scope"] or "condor:/READ condor:/ADVERTISE_STARTD condor:/ADVERTISE_MASTER"

        duration = (
            self.context["duration"] or int(kwargs["elementDescript"].merged_data.get("IDTokenLifetime", 24)) * 3600
        )

        identity = self.context["identity"]
        if not identity:
            try:
                identity = f"{kwargs['glidein_el']['attrs']['GLIDEIN_Site']}@{socket.gethostname()}"
            except KeyError:
                # GLIDEIN_Site is not mandatory, the name is
                identity = f"{kwargs['glidein_el']['name']}@{socket.gethostname()}"

        minimum_lifetime = self.context["minimum_lifetime"] or 0

        idtoken_str = create_and_sign_token(
            pwd_file=password,
            scope=scope,
            duration=duration,
            identity=identity,
        )

        if minimum_lifetime <= 0:
            minimum_lifetime = None

        return create_credential(
            string=idtoken_str,
            minimum_lifetime=minimum_lifetime,
            cred_type=credential_type_from_string(self.context["type"]),
        )


export_generator(IdTokenGenerator)
