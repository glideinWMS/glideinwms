#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

import os
import sys

import yaml

# this should be not needed #was-pylint: disable=import-error
import glideinwms.lib.logSupport as logSupport

from glideinwms.unittests.unittest_utils import create_random_string

# this should be not needed #was-pylint: enable=import-error

module_globals = globals()
this_dir = os.path.dirname(os.path.realpath(module_globals["__file__"]))
sys.path.append(os.path.join(this_dir, "../"))


def main():
    try:
        # read these from config file
        section = "test_size_rotate"
        config_file = "../test_configurations/test_logSupport.yaml"
        config = yaml.load(open(config_file), Loader=yaml.FullLoader)

        log_name = str(config[section]["log_name"])
        extension = str(config[section]["extension"])
        msg_types = str(config[section]["msg_types"])
        max_days = int(float(config[section]["max_days"]))
        min_days = int(float(config[section]["min_days"]))
        max_mbytes = int(float(config[section]["max_mbytes"]))
        backupCount = 5
        compression = ""
        structured = False

        log_dir = os.path.join("/tmp", log_name)

        handler = logSupport.get_processlog_handler(
            log_name,
            log_dir,
            msg_types,
            extension,
            max_days,
            min_days,
            max_mbytes,
            backupCount=backupCount,
            compression=compression,
        )
        if structured:
            log = logSupport.get_structlog_logger(log_name)
        else:
            log = logSupport.get_logging_logger(log_name)
        log.addHandler(handler)

        log.info(f"{create_random_string(length=2048)}\n")

        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
