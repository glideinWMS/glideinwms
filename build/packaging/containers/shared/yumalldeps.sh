#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

help_msg() {
  cat << EOF
${filename} [options] package1 [ package2 [...]]
get all the yum dependencies that are not in GlideinWMS packages (or in the FAMILY)
 Options:
  -h          print this message
  -v          verbose
  -y OPTS     yum options (remember to quote)
  -i          do also yum install
  -f FAMILY   Package family, i.e. packages searched for deps and excluded from results (default: $PKG_FAMILY)
EOF
}

parse_options() {
    # Parse and validate options to the runtest command
    # OPTS=$(getopt --options $SHORT --long $LONG --name "$0" -- "$@")
    # The man page mentions optional options' arguments for getopts but they are not handled correctly
    # Defaults
    VERBOSE=
    PKG_FAMILY=glideinwms
    YUM_OPTIONS=
    YUM_INSTALL=
    while getopts ":hvy:if:" option
    do
        case "${option}"
        in
        h) help_msg; exit 0;;
        v) VERBOSE=yes;;
        f) PKG_FAMILY="$OPTARG";;
        y) YUM_OPTIONS="$OPTARG";;
        i) YUM_INSTALL=yes;;
        : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; exit 1;;
        \?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
        *) logerror "illegal long option: -$OPTARG"; help_msg 1>&2; exit 1;;
        esac
    done

}

mylog() {
  [[ -n "$VERBOSE" ]] && echo "$1" >&2
}

getdep() {
    tmp_all="$(yum deplist $YUM_OPTIONS $* | awk '/provider/ {print $2}' | sort -u )"
    # Printing all packages that can provide the requirement may result in including in the list multiple providers
    # incompatible with one another. An install command will result in error unless "--skip-broken" is added
    remaining="$(echo "$tmp_all" | grep "$PKG_FAMILY" | sed ':a;N;$!ba;s/\n/ /g' )"
    if [[ -n "$remaining" ]]; then
        mylog "- recurse $remaining"
        retv="$(getdep $remaining )"
    else
        mylog "- end"
        retv=""
    fi
    echo "$retv"
    echo "$tmp_all" | grep -v $PKG_FAMILY
}

_main() {
    parse_options "$@"
    # This needs to be outside to shift the general arglist
    shift $((OPTIND-1))
    echo "Is verbose : $VERBOSE"

    export VERBOSE=$VERBOSE
    export PKG_FAMILY="$PKG_FAMILY"
    export YUM_OPTIONS="$YUM_OPTIONS"

    mylog "Start: $*"

    all="$(getdep $*)"
    mylog "One per line: $( echo "$all" | wc )"
    mylog "$(echo "$all" | sort -u )"
    mylog "Result:"
    if [[ -n "$YUM_INSTALL" ]]; then
        # --skip-broken is needed. The list may contain conflicting dependencies, e.g. coreutils and coreutils-single
        yum install -y --skip-broken $YUM_OPTIONS $(echo "$all" | sort -u | sed ':a;N;$!ba;s/\n/ /g' )
    else
        echo "$(echo "$all" | sort -u | sed ':a;N;$!ba;s/\n/ /g' )"
    fi
}

# https://stackoverflow.com/questions/29966449/what-is-the-bash-equivalent-to-pythons-if-name-main
# Alt: [[ "$(caller)" != "0 "* ]] || _main "$@"
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi
