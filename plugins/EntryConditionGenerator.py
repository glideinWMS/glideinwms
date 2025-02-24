#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module contains the EntryConditionGenerator class.
It is a Generator that can be used by credentials or parameters depending on Entry elements.
"""

from typing import Any

from glideinwms.lib.generators import export_generator, Generator, GeneratorError


# TODO: Add CHANGELOG and documentation once the 3.11 documentation is updated
class EntryConditionGenerator(Generator[Any]):
    """Generator with output depending on an Entry parameter (discriminator) value.

    If the discriminator is in the dictionary, the corresponding value is returned.
    Else, if the discriminator is in the list, the list_output is returned.
    Otherwise, the default is returned.

    The context for this generator must have:
      - discriminator: The entry attribute used to choose the output. Possible values are name, gatekeeper, factory,
        factory.name, trust_domain. Defaults to name
      - dict: Dictionary where keys are discriminator attribute values and values are output to generate. Defaults to {}
      - list: List of attribute values that will result in true_value as output. Defaults to []
      - list_output: Output when the attribute is in the list (and not in the dictionary). Defaults to None
      - default: Output when the attribute is not in the dictionary or list. Defaults to None

    Attributes:
        DISCRIMINATOR_VALUES (list): valid values for the discriminator in the context
        ENTRY_MAPPING (dict):
    """

    DISCRIMINATOR_VALUES = ["name", "gatekeeper", "factory", "factory.name", "trust_domain"]
    ENTRY_MAPPING = {
        "name": "EntryName",
        "gatekeeper": "GLIDEIN_Gatekeeper",
        "factory": "AuthenticatedIdentity",
        "trust_domain": "GLIDEIN_TrustDomain",
    }

    def __init__(self, context: Any = None):
        super().__init__(context)
        if "list" not in self.context and "dict" not in self.context:
            raise GeneratorError(
                "list and dict not found in context for EntryConditionGenerator. At least one is required"
            )
        # Assigning defaults and updating with context
        self.discriminator = self.context.get("discriminator", "name")
        self.discriminator_list = self.context.get("list", [])
        self.discriminator_dict = self.context.get("dict", {})
        self.true_value = self.context.get("list_output")
        self.false_value = self.context.get("default")
        if self.discriminator not in self.DISCRIMINATOR_VALUES:
            raise GeneratorError(
                "invalid discriminator in context for EntryConditionGenerator."
                f" Must be in {self.DISCRIMINATOR_VALUES}"
            )
        if not isinstance(self.discriminator_list, list):
            raise GeneratorError("invalid list in context for EntryConditionGenerator.")
        if self.discriminator_list and self.true_value is None:
            raise GeneratorError(
                "invalid context for EntryConditionGenerator. You must specify list_output if you have a list."
            )
        if not isinstance(self.discriminator_dict, dict):
            raise GeneratorError("invalid dict in context for EntryConditionGenerator.")

    def generate(self, **kwargs) -> Any:
        """Generate the Entry-determined value.

        This function is by choice not using "entry" from kwargs. All values are in "glidein_el".
        "trust_domain" is used if there, falling back to the trust_domain in "glidein_el".

        Args:
            **kwargs: dictionary of arguments. "glidein_el" is a required key.

        Returns:
            Any: the desired output
        """
        glidein_el = kwargs["glidein_el"]
        if self.discriminator == "factory.name":
            entry_name = glidein_el["attrs"].get("EntryName")
            entry_factory = glidein_el["attrs"].get("AuthenticatedIdentity")
            discriminator = f"{entry_factory}.{entry_name}"
        elif self.discriminator == "trust_domain":
            if "trust_domain" in kwargs:
                discriminator = kwargs["trust_domain"]
            else:
                discriminator = glidein_el["attrs"].get("GLIDEIN_TrustDomain", "Grid")
        else:
            # self.discriminator was validated, can be only one of "name", "gatekeeper", "factory"
            discriminator = glidein_el["attrs"].get(self.ENTRY_MAPPING[self.discriminator])
        if discriminator in self.discriminator_dict:
            return self.discriminator_dict[discriminator]
        if discriminator in self.discriminator_list:
            return self.true_value
        return self.false_value


export_generator(EntryConditionGenerator)
