#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Example custom script using the Glidein logging utility
#
# Use: logging_test.sh glidein_config
# Test the logging utils: correct setup, writing, upload of the logs
# Enable logging, e.g. in the Factory with:
#       <attr name="GLIDEIN_LOG_RECIPIENTS_FACTORY" const="False" glidein_publish="True" job_publish="True"
#       parameter="True" publish="True" type="string"
#       value="https://factory-workspace.glideinwms.org/logserver/put.php"/>

# Get the Glidein configuration file name to access the global variables
glidein_config=$1

# import add_config_line/glidein_config functions
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | awk '{print $2}')
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

# find error reporting helper script
#error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`
error_gen=$(gconfig_get ERROR_GEN_PATH "$glidein_config")

# shellcheck source=./logging_utils.source
. "$(gconfig_get LOGGING_UTILS_SOURCE)"

# add an attribute
gconfig_add custom_log_test "run_$(date)"

# read an attributes (set by you or some other script)
#myvar=$(gconfig_get myattribute)

fn_exists() {
    # Test if $1 is a valid function (true if it is)
    # LC_ALL=C type $1 | grep -q 'shell function'
    LC_ALL=C type $1 | grep -q 'function'
}

log_defined=no
if fn_exists glog_write; then
  log_defined=OK
fi

log_did_setup=no
if glog_setup "$glidein_config"; then
  log_did_setup=OK
fi

log_written=no
if glog_write logging_test.sh text "Message 1 from logging_test.sh" info; then
  log_written=OK
fi

log_sent=no
if glog_send; then
  log_sent=OK
fi

# Everything worked out fine
"$error_gen" -ok use_log.sh log_defined "$log_defined" log_did_setup "$log_did_setup" log_written "$log_written" log_sent "$log_sent" ended OK
