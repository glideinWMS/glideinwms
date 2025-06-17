#!/usr/bin/env python3

"""
This module contains the CredentialGenerator base class
"""

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os

from typing import Mapping, Optional

from glideinwms.lib.credentials import create_credential, Credential, credential_type_from_string

from .generators import CachedGenerator


class CredentialGenerator(CachedGenerator[Credential]):
    """Base class for credential generators"""

    def __init__(self, context: Optional[Mapping] = None, instance_id: Optional[str] = None):
        super().__init__(context, instance_id)
        self.context.validate(
            {
                "cache_discriminator": (str, ""),
            }
        )

        if self.context["cache_discriminator"] == "":
            self.discriminator_list = []
        else:
            self.discriminator_list = [d.strip() for d in self.context["cache_discriminator"].split(",")]

    def dynamic_cache_file(self, **kwargs):
        if not self.discriminator_list:
            return None

        file_name, file_ext = os.path.splitext(self.context["cache_file"])
        return f"{file_name}.{self.cache_discriminator(self.discriminator_list, **kwargs)}{file_ext}"

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
