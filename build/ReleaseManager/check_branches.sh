#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Script to check if all the local branches have been pushed to the remote repository
# See help_msh for more information

REMOTE=origin

filename="$(basename $0)"

# TODO: Query github for branch and merge information.
#  Use the local repository optionally to check if local branches have been merged
help_msg() {
    cat << EOF
$filename [REMOTE]
Check if all the local branches have been pushed to the REMOTE repo.
Assumes BRANCH is tracking REMOTE/BRANCH
Options
-h      Print this help
-v      Verbose mode
REMOTE  Remote repo name (default: origin)
This command must be run inside the Git repository. It checks the local repository.
EOF
}

loginfo() {
    $VERBOSE && echo "$@"
}

VERBOSE=false
while getopts ":hv" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  v) VERBOSE=true;;
  : ) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done
shift $((OPTIND-1))

LOCAL_BRANCHES="$(git branch --format "%(refname:short)" -l)"
REMOTE_BRANCHES="$(git branch --no-color --format "%(refname:lstrip=1)" -al | egrep "^remotes/$REMOTE")"
MISSING_BRANCHES=

for i in $LOCAL_BRANCHES; do
    i_current_commit=$(git rev-parse $i 2> /dev/null)
    [[ -z "$i_current_commit" ]] && echo "ERROR: branch $i is empty!"
    branch_not_pushed=true
    possible_matches=$(echo "$REMOTE_BRANCHES" | egrep "$i$")
    [[ -z "$possible_matches" ]] && loginfo "No matches in $REMOTE for branch $i"
    for j in $possible_matches; do
        merge_base=$(git merge-base $i $j 2> /dev/null)
        if [[ -z "$merge_base" ]]; then
            loginfo "Nothing in common between $i and $j"
        else
            if [[ "$merge_base" = "$i_current_commit" ]]; then
                branch_not_pushed=false
            else
                loginfo "Branch $i not pushed completely to $j"
            fi
        fi
    done
    $branch_not_pushed && MISSING_BRANCHES="$MISSING_BRANCHES $i"
done
echo "There are $(echo "$MISSING_BRANCHES" | wc -w | tr -d " ") branches not pushed to $REMOTE"
