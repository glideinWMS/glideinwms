#!/usr/bin/python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os

from typing import List

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from scitokens import SciToken

from glideinwms.lib.credentials import create_credential, CredentialType
from glideinwms.lib.defaults import TOKEN_DIR
from glideinwms.lib.generators import export_generator, GeneratorError
from glideinwms.lib.generators.credential_generator import CredentialGenerator


class SciTokenGenerator(CredentialGenerator):
    """SciTokens Generator

    This generator creates a SciToken based on the provided context.
    The context supports the following parameters:
        - key_file: Path to the private key file to sign the token (mandatory)
        - key_id: Identifier for the key, `kid` in the JWT
        - issuer: Issuer of the token, `iss` in the JWT (mandatory). This is used to retrieve the key for token verification.
        - scope: Scope of the token, `scope` in the JWT (mandatory)
        - key_pass: Password for the private key (if encrypted)
        - algorithm: Signing algorithm to use (default: RS256)
        - wlcg_ver: WLCG version (default: 1.0)
        - tkn_lifetime: Lifetime of the token in seconds (default: 7200)
        - tkn_dir: Directory to store the generated tokens (default: defaults.TOKEN_DIR = $HOME/cred.d/tokens.d)
    """

    CONTEXT_VALIDATION = {
        "key_file": (str,),
        "key_id": (str, None),
        "issuer": (str,),
        "scope": (str,),
        "key_pass": (str, ""),
        "algorithm": (str, "RS256"),
        "wlcg_ver": (str, "1.0"),
        "tkn_lifetime": (int, 7200),
        "tkn_dir": (str, TOKEN_DIR),
    }

    @staticmethod
    def context_checks(context: dict) -> List[str]:
        """Checks that the context is valid.

        Args:
            context (dict): scitoken context

        Returns:
            list: list of errors encountered. Empty if all OK.
        """
        try:
            if context["issuer"].startswith("http://"):
                return [f'Issuer URL must use https. http will fail token verification: {context["issuer"]}']
        except (TypeError, KeyError):
            return [f"'issuer' is required in the context: {context}"]
        return []

    def _setup(self):
        self.context.validate(self.CONTEXT_VALIDATION, self.context_checks)

        self.context["type"] = "scitoken"

        self.key_pass = self.context["key_pass"].encode() or None

        if not os.path.exists(self.context["tkn_dir"]):
            os.mkdir(self.context["tkn_dir"], 0o700)
        self.context["cache_dir"] = self.context["tkn_dir"]

    def _generate(self, **kwargs):
        logger = kwargs["logger"]
        entry_name = kwargs["glidein_el"]["attrs"].get("EntryName")
        gatekeeper = kwargs["glidein_el"]["attrs"].get("GLIDEIN_Gatekeeper")

        audience = gatekeeper.split()[-1]
        subject = f"vofrontend-{entry_name}"

        try:
            with open(self.context["key_file"], "rb") as key_file:
                private_key_contents = key_file.read()
            loaded_private_key = serialization.load_pem_private_key(
                private_key_contents, password=self.key_pass, backend=default_backend()
            )

            token = SciToken(key=loaded_private_key, key_id=self.context["key_id"], algorithm=self.context["algorithm"])
            token.update_claims(
                {"sub": subject, "aud": audience, "scope": self.context["scope"], "wlcg.ver": self.context["wlcg_ver"]}
            )

            tkn_str = token.serialize(issuer=self.context["issuer"], lifetime=self.context["tkn_lifetime"])
        except Exception as e:
            logger.error(f"Error generating SciToken: {e}")
            raise GeneratorError(f"Error generating SciToken: {e}") from e

        return create_credential(tkn_str, cred_type=CredentialType.SCITOKEN)


export_generator(SciTokenGenerator)
