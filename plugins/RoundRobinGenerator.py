#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
This module contains the RoundRobinGenerator class
"""

from itertools import cycle
from typing import Any

from glideinwms.lib.generators import export_generator, Generator


class RoundRobinGenerator(Generator[Any]):
    """Round-robin generator"""

    def _setup(self):
        self.context.validate({"items": (list, None)})
        self.items_cycle = cycle(self.context["items"])

    def _generate(self, **kwargs) -> Any:
        return next(self.items_cycle)


export_generator(RoundRobinGenerator)
