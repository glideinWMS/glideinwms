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
    """IDTOKEN generator"""

    def _setup(self):
        self.context.validate(
            {
                "password": (str, ""),
                "scope": (str, ""),
                "duration": (int, 0),
                "minimum_lifetime": (int, 0),
                "identity": (str, ""),
            }
        )
        self.context["type"] = "idtoken"

    def _generate(self, **kwargs):
        password = self.context["password"] or os.path.join(
            defaults.pwd_dir, kwargs["elementDescript"].merged_data.get("IDTokenKeyname", getpass.getuser().upper())
        )

        scope = self.context["scope"] or "condor:/READ condor:/ADVERTISE_STARTD condor:/ADVERTISE_MASTER"

        duration = (
            self.context["duration"] or int(kwargs["elementDescript"].merged_data.get("IDTokenLifetime", 24)) * 3600
        )

        identity = self.context["identity"] or f"{kwargs['glidein_el']['attrs']['GLIDEIN_Site']}@{socket.gethostname()}"

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
