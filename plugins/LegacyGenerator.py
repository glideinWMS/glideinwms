#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the LegacyGenerator class.
"""

from typing import Any

from glideinwms.lib.generators import export_generator, Generator, GeneratorError
from glideinwms.lib.util import import_module


class LegacyGenerator(Generator[Any]):
    """Generator that implements support to the legacy callout interface."""

    def __init__(self, context: Any = None):
        super().__init__(context)

        if "callout" not in self.context:
            raise GeneratorError("callout not found in context for LegacyGenerator")
        self.callout = import_module(self.context["callout"])

        if not hasattr(self.callout, "get_credential"):
            raise GeneratorError("callout module does not have get_credential method")

    def generate(self, **kwargs) -> Any:
        callout_kwargs = {
            "logger": kwargs["logger"],
            "group": kwargs["group_name"],
            "entry": kwargs["entry"],
            "trust_domain": kwargs["trust_domain"],
        }
        callout_kwargs.update(self.context.get("kwargs", {}))

        try:
            out = self.callout.get_credential(**callout_kwargs)
        except Exception as e:
            raise GeneratorError(f"callout failed to generate credential: {e}") from e
        if not isinstance(out, tuple) or len(out) != 2:
            raise GeneratorError("callout did not return a tuple with (credential, lifetime)")

        return out[0]


export_generator(LegacyGenerator)
