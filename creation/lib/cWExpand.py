# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#
# Description:
#   Contains the algorithms needed for attribute expansion
#
# Author: Igor Sfiligoi
#

import re
import string

######################
# expand $$(attribute)
# quote, if needed
EDD_RE = re.compile(r"\$\$\((?P<attrname>[^\)]*)\)")


def expand_DD(qstr, attr_dict):
    while 1:
        m = EDD_RE.search(qstr)
        if m is None:
            break  # no more substitutions to do
        attr_name = m.group("attrname")
        if not attr_dict.has_key(attr_name):
            raise KeyError("Missing attribute %s" % attr_name)
        attr_val = attr_dict[attr_name]
        if type(attr_val) == int:
            attr_str = str(attr_val)
        else:  # assume it is a string for all other purposes... quote and escape existing quotes
            attr_str = '"%s"' % attr_val.replace('"', '\\"')
        qstr = f"{qstr[: m.start()]}{attr_str}{qstr[m.end() :]}"
    return qstr


######################
# expand $(attr) and $$(attr)
# $(attr) can be recursive
EDLR_RE = re.compile(r"\$\((?P<attrname>[^\)]*)\)")


def expand_DLR(qstr, attr_dict):
    # get $$ out of the way first, since it is not recursive
    # and may get in the way of single $ regexp matching
    org_qstr = qstr
    qstr = expand_DD(org_qstr, attr_dict)

    # now look for single $ expressions
    while 1:
        m = EDLR_RE.search(qstr)
        if m is None:
            break  # no more substitutions to do

        attr_name = m.group("attrname")
        if attr_name == "DOLLAR":
            # $(DOLLAR) is special
            qstr = f"{qstr[: m.start()]}${qstr[m.end() :]}"
            continue

        if not attr_dict.has_key(attr_name):
            raise KeyError(
                "Missing attribute %s (or loop detected). If you do not intend to use the attribute expansion feature and just want to use a dollar, please use $(DOLLAR) instead of $. You can also turn off attribute expansion by setting 'enable_attribute_expansion=\"False\"'."
                % attr_name
            )

        t_attr_dict = attr_dict.copy()  # simple copy is enough, since we only modify the keys
        del t_attr_dict[attr_name]  # remove myself, so there cannot be loops
        # recursevely expand any $ and $$ contained in the referenced attribute
        attr_str = expand_DLR(str(attr_dict[attr_name]), t_attr_dict)
        del t_attr_dict

        qstr = f"{qstr[: m.start()]}{attr_str}{qstr[m.end() :]}"
    return qstr
