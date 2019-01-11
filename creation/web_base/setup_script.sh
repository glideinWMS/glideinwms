#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

GLIDEIN_WORK_DIR="`grep '^GLIDEIN_WORK_DIR ' "$glidein_config" | cut -d ' ' -f 2-`"
chmod u+x "$GLIDEIN_WORK_DIR/error_gen.sh"

echo "ERROR_GEN_PATH $GLIDEIN_WORK_DIR/error_gen.sh" >> "$glidein_config"