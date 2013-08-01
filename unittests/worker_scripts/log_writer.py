#!/usr/bin/env python

import logging
import os
import sys
import yaml

# set the python path to the parent directory so that we can import unittest_utils
module_globals = globals()
this_dir = os.path.dirname(os.path.realpath(module_globals["__file__"]))
sys.path.append(os.path.join(this_dir, "../"))
from unittest_utils import create_random_string  # @UnresolvedImport

# unittest sets python path such that we can import logSupport
import logSupport  # @UnresolvedImport

def main():
    try:
        # read these from config file
        section = "test_size_rotate"
        config_file = "../test_configurations/test_logSupport.yaml"
        config = yaml.load(file(config_file, 'r'))

        log_name = str(config[section]["log_name"])
        extension = str(config[section]["extension"])
        msg_types = str(config[section]["msg_types"])
        max_days = float(config[section]["max_days"])
        min_days = float(config[section]["min_days"])
        max_mbytes = float(config[section]["max_mbytes"])
        backupCount = 5

        log_dir = "/tmp/%s" % log_name

        logSupport.add_processlog_handler(log_name, log_dir, msg_types, 
                    extension, max_days, min_days, max_mbytes, 
                    backupCount=backupCount)

        log = logging.getLogger(log_name)
        log.info("%s\n" % create_random_string(length=2048))

        return 0
    except:
        return 1

if __name__ == "__main__":
    sys.exit(main())