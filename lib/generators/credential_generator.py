#!/usr/bin/env python3

"""
This module contains the CredentialGenerator base class
"""

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os

from typing import Mapping, Optional

from glideinwms.lib.credentials import create_credential, Credential, credential_type_from_string

from .generators import CachedGenerator, GeneratorError


class CredentialGenerator(CachedGenerator[Credential]):
    """Base class for credential generators"""

    DISCRIMINATOR_VALUES = ["name", "gatekeeper", "factory", "factory.name", "trust_domain"]
    ENTRY_MAPPING = {
        "name": "EntryName",
        "gatekeeper": "GLIDEIN_Gatekeeper",
        "factory": "AuthenticatedIdentity",
        "trust_domain": "GLIDEIN_TrustDomain",
    }

    def __init__(self, context: Optional[Mapping] = None, instance_id: Optional[str] = None):
        super().__init__(context, instance_id)
        self.context.validate(
            {
                "cache_discriminator": (str, ""),
            }
        )

        self.cache_discriminator = self.context["cache_discriminator"] or None
        if self.cache_discriminator and self.cache_discriminator not in self.DISCRIMINATOR_VALUES:
            raise GeneratorError(
                "invalid discriminator in context for CredentialGenerator." f" Must be in {self.DISCRIMINATOR_VALUES}"
            )

    def dynamic_cache_file(self, **kwargs):
        if not self.cache_discriminator:
            return

        glidein_el = kwargs["glidein_el"]
        if self.cache_discriminator == "factory.name":
            entry_name = glidein_el["attrs"].get("EntryName")
            entry_factory = glidein_el["attrs"].get("AuthenticatedIdentity")
            discriminator = f"{entry_factory}.{entry_name}"
        elif self.cache_discriminator == "trust_domain":
            if "trust_domain" in kwargs:
                discriminator = kwargs["trust_domain"]
            else:
                discriminator = glidein_el["attrs"].get("GLIDEIN_TrustDomain", "Grid")
        else:
            # self.cache_discriminator was validated, can be only one of "name", "gatekeeper", "factory"
            discriminator = glidein_el["attrs"].get(self.ENTRY_MAPPING[self.cache_discriminator])

        file_name, file_ext = os.path.splitext(self.context["cache_file"])
        return f"{file_name}_{discriminator}{file_ext}"

    def save_to_cache(self, cache_file: str, generated_value: Credential):
        generated_value.save_to_file(path=cache_file)

    def load_from_cache(self, cache_file: str) -> Optional[Credential]:
        if not os.path.exists(cache_file):
            return None

        cred_type = None
        if "type" in self.context:
            cred_type = credential_type_from_string(self.context["type"])

        return create_credential(path=cache_file, cred_type=cred_type)

    def validate_cache(self, cached_value) -> bool:
        return cached_value.valid
