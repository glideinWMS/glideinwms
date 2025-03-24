#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains the IdTokenGenerator class
"""

import getpass
import os
import socket

from glideinwms.lib.credentials import create_credential, credential_type_from_string
from glideinwms.lib.defaults import PWD_DIR
from glideinwms.lib.generators import export_generator
from glideinwms.lib.generators.credentialGenerator import CredentialGenerator
from glideinwms.lib.token_util import create_and_sign_token


class IdTokenGenerator(CredentialGenerator):
    """IDTOKEN generator"""

    def setup(self):
        self.context["type"] = "idtoken"

    def generate(self, **kwargs):
        default_password = os.path.join(
            PWD_DIR, kwargs["elementDescript"].merged_data.get("IDTokenKeyname", getpass.getuser().upper())
        )

        default_scope = "condor:/READ condor:/ADVERTISE_STARTD condor:/ADVERTISE_MASTER"

        default_duration = int(kwargs["elementDescript"].merged_data.get("IDTokenLifetime", 24)) * 3600

        default_minimum_lifetime = 0

        default_identity = f"{kwargs['glidein_el']['attrs']['GLIDEIN_Site']}@{socket.gethostname()}"

        self.context.validate(
            {
                "password": (str, default_password),
                "scope": (str, default_scope),
                "duration": (int, default_duration),
                "minimum_lifetime": (int, default_minimum_lifetime),
                "identity": (str, default_identity),
            }
        )

        idtoken_str = create_and_sign_token(
            pwd_file=self.context["password"],
            scope=self.context["scope"],
            duration=self.context["duration"],
            identity=self.context["identity"],
        )

        minimum_lifetime = self.context["minimum_lifetime"]
        if minimum_lifetime <= 0:
            minimum_lifetime = None

        return create_credential(
            string=idtoken_str,
            minimum_lifetime=minimum_lifetime,
            cred_type=credential_type_from_string(self.context["type"]),
        )


export_generator(IdTokenGenerator)
