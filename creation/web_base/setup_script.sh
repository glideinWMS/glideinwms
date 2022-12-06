#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# File Version:
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

# import add_config_line and add_condor_vars_line functions
add_config_line_source=$(grep -m1 '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-)
# shellcheck source=./add_config_line.source
. "$add_config_line_source"

GLIDEIN_WORK_DIR=$(gconfig_get GLIDEIN_WORK_DIR "$glidein_config")
chmod u+x "$GLIDEIN_WORK_DIR/error_gen.sh"

echo "ERROR_GEN_PATH $GLIDEIN_WORK_DIR/error_gen.sh" >> "$glidein_config"
