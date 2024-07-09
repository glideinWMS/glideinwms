#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains the RoundRobinGenerator class
"""

from itertools import cycle
from typing import Any

from glideinwms.lib.generators import export_generator, Generator, GeneratorError


class RoundRobinGenerator(Generator[Any]):
    """Round-robin generator"""

    def __init__(self, context: Any = None):
        super().__init__(context)
        if "items" not in self.context:
            raise GeneratorError("items not found in context for RoundRobinGenerator")
        self.items_cycle = cycle(self.context["items"])

    def generate(self, **kwargs) -> Any:
        return next(self.items_cycle)


export_generator(RoundRobinGenerator)
