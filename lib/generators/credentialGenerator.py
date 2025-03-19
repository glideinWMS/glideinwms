#!/usr/bin/env python3

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
                "type": (str, None),
            }
        )

    def save_to_cache(self, generated_value):
        generated_value.save_to_file(path=self.cache_file)

    def load_from_cache(self) -> Optional[Credential]:
        if not os.path.exists(self.cache_file):
            return None
        return create_credential(path=self.cache_file, cred_type=credential_type_from_string(self.context["type"]))

    def validate_cache(self, cached_value) -> bool:
        return cached_value.valid
