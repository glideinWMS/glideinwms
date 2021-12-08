#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Replacing Mac's utilities with GNU ones
# coreutils and findutils must be installed (e.g. brew install coreutils)

check_os_mac() {
  if ! [[ "$OSTYPE" =~ darwin* ]]; then
      false
  else
      true
  fi
}

# Replacing Mac's commands with functions.
# Aliases do not work correctly in BATS.
# singularity_lib.sh uses env -0
# the BATS test uses xargs

if check_os_mac ; then
    echo "Mac OS X: replacing env and xargs for compatibility"
    if [[ -x /usr/local/bin/genv ]]; then
        env () {
            /usr/local/bin/genv "$@"
        }
    fi
    if [[ -x /usr/local/bin/gxargs ]]; then
        xargs () {
            /usr/local/bin/gxargs "$@"
        }
    fi
fi
