#!/usr/bin/python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import json
import os

from glideinwms.factory.globus_compute.globus_compute_helpers import GLOBUS_COMPUTE_ALL_SCOPE, mint_access_token
from glideinwms.lib import defaults
from glideinwms.lib.credentials import create_credential, CredentialType
from glideinwms.lib.generators import export_generator, GeneratorError
from glideinwms.lib.generators.credential_generator import CredentialGenerator


class GlobusComputeTokenGenerator(CredentialGenerator):
    """Globus Compute access-token generator.

    Mints a Globus Compute access token on demand with the OAuth2 client
    credentials grant of a confidential client. The token is cached and reused
    until it expires, then regenerated. The context supports:
        - client_id: Confidential client id (mandatory)
        - client_secret_file: Path to the file holding the client secret (mandatory)
        - scope: Requested scope (default: Globus Compute "all" scope)
        - resource_server: Resource server to extract the token for (default: funcx_service)
        - tkn_dir: Directory to store the generated tokens (default: defaults.token_dir)
    """

    CONTEXT_VALIDATION = {
        "client_id": (str,),
        "client_secret_file": (str,),
        "scope": (str, GLOBUS_COMPUTE_ALL_SCOPE),
        "resource_server": (str, "funcx_service"),
        "tkn_dir": (str, defaults.token_dir),
    }

    def _setup(self):
        self.context.validate(self.CONTEXT_VALIDATION)
        self.context["type"] = "globus_compute_token"
        if not os.path.exists(self.context["tkn_dir"]):
            os.mkdir(self.context["tkn_dir"], 0o700)
        self.context["cache_dir"] = self.context["tkn_dir"]

    def _generate(self, **kwargs):
        logger = kwargs["logger"]
        try:
            with open(self.context["client_secret_file"]) as secret_file:
                client_secret = secret_file.read().strip()

            token_doc = mint_access_token(
                client_id=self.context["client_id"],
                client_secret=client_secret,
                scope=self.context["scope"],
                resource_server=self.context["resource_server"],
            )
        except Exception as e:
            logger.error(f"Error generating Globus Compute token: {e}")
            raise GeneratorError(f"Error generating Globus Compute token: {e}") from e

        return create_credential(json.dumps(token_doc), cred_type=CredentialType.GLOBUS_COMPUTE_TOKEN)


export_generator(GlobusComputeTokenGenerator)
