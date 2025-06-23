#!/usr/bin/env python3

"""
This module contains the CredentialGenerator base class
"""

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os

from typing import Optional

from glideinwms.lib.credentials import create_credential, Credential, credential_type_from_string

from .generators import CachedGenerator


class CredentialGenerator(CachedGenerator[Credential]):
    """Base class for credential generators"""

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
