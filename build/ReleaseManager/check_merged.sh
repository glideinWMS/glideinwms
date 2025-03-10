#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Script to check the Git branches vs the redmine tickets before a release
# See help_msh for more information

RELEASE_BRANCH=master
REDMINE=https://cdcvs.fnal.gov/redmine
GWMS_PROJECT_ID=72

filename="$(basename $0)"

# TODO: Query github for branch and merge information.
#  Use the local repository optionally to check if local branches have been merged
help_msg() {
    cat << EOF
$filename RELEASE [RBRANCH]
Check if all the branches have been merged in the release that is about to be cut.
Checks the branches merged in the current release branch against names containing one of the issue IDs.
Assumes that Git branch names include the Redmine issue ID and includes no spaces.
- List the issues that have no Git branches
- List issue related branches that are not contained in the release branch (have not been merged directly or indirectly)
In verbose mode adds more details about the issues and the branches above and also:
- List all the issues in the release
- List all the issues whose branches have not been merged directly to the release branch (they may have been merged indirectly)
Options
-h           Print this help
-v           Verbose mode
-a AUTHFILE  Add a configuration file to use for authentication. Make a private file.
             Write in it a line like "--user REDMINE_USER:REDMINE_PASSWORD"
-u USER      RedMine user. The script will ask for your RedMine (services) password twice.
             You cannot use -a and -u at the same time.
RELEASE Is the Version name in Redmine
RBRANCH Is the release branch name in Git, used to check if all issue branches have been merged
        It can be normally derived by the RELEASE value
This command must be run inside the Git repository. Future versions will query Github.
Remember to be in the VPN and use -a OR -u to authenticate to RedMine.
EOF
}

loginfo() {
    [[ -n "$VERBOSE" ]] && echo "$@"
}

VERBOSE=
AUTHFILE=
CURLUSER=
CURLOPTIONS=
while getopts ":a:u:hv" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  v) VERBOSE=yes;;
  a) AUTHFILE=$OPTARG;;
  u) CURLUSER=$OPTARG;;
  : ) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done
shift $((OPTIND-1))

if [[ -n "$AUTHFILE" && -n "$CURLUSER" ]]; then
    echo "ERROR: You cannot use -a and -u at the same time. The user is already specified in the AUTHFILE."
    help_msg
    exit 1
fi
[[ -n "$AUTHFILE" ]] && CURLOPTIONS="-K $AUTHFILE" || true
[[ -n "$CURLUSER" ]] && CURLOPTIONS="--user $CURLUSER" || true

RELEASE=$1
if [[ -z "$RELEASE" ]]; then
    echo "ERROR: Missing RELEASE argument."
    help_msg
    exit 1
fi

RELEASE_BRANCH=$2
if [[ -z "$RELEASE_BRANCH" ]]; then
    if [[ $RELEASE = v3_4* ]]; then
        RELEASE_BRANCH=master
    elif [[ $RELEASE = v3_5* ]]; then
        RELEASE_BRANCH=master
    elif [[ $RELEASE = v3_6* ]]; then
        RELEASE_BRANCH=master
    elif [[ $RELEASE = v3_7* ]]; then
        # RELEASE_BRANCH=branch_v3_7
        RELEASE_BRANCH=master
    elif [[ $RELEASE = v3_8* ]]; then
        RELEASE_BRANCH=branch_v3_8
    elif [[ $RELEASE = v3_9* ]]; then
        RELEASE_BRANCH=branch_v3_9
    elif [[ $RELEASE = v3_p3* ]]; then
        RELEASE_BRANCH=branch_v3_p3_a2
    else
        echo "ERROR: Unable to assign release branch to release $RELEASE."
        exit 1
    fi
fi

if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: required jq command not found."
    exit 1
fi

loginfo "Querying Redmine about the version ID and the issues..."

#VER_ID=$(curl -s -H "Content-Type: application/json" -X GET $REDMINE/projects/glideinwms/versions.json | jq ' .versions[] | {name: .name, id: .id } | select(.name == "'$RELEASE'") | .id')
VER_ID=$(curl $CURLOPTIONS -s -H "Content-Type: application/json" -X GET $REDMINE/projects/glideinwms/versions.json | jq ' .versions[] | select(.name == "'$RELEASE'") | .id')
if [[ -z "$VER_ID" ]]; then
    echo "ERROR: Unable to find the ID for version ${RELEASE}."
    echo "Please check the version name and that you can access Redmine (VPN and authentication)."
    exit 1
fi

# Issues are one per line, so grep does an OR in the matching. To flatten, use unquoted
# status_id=* is required, otherwise Redmine will ignore closed issues
# limit=200 is required, otherwise only 25 entries are returned (assuming no more than 200 issues per release)
VER_ISSUES_EXT=$(curl $CURLOPTIONS -s -H "Content-Type: application/json" -X GET $REDMINE/issues.json?limit=200\&project_id=$GWMS_PROJECT_ID\&fixed_version_id=$VER_ID\&status_id=\*  | jq '.issues[] | { id: .id, subject: .subject } ' )
VER_ISSUES=$(echo "$VER_ISSUES_EXT" | jq '.id' | sort)

if [[ -z "$VER_ISSUES" ]]; then
    echo "WARNING: No issues for version ${RELEASE} (${VER_ID}). An error may have occurred."
    echo "Verify in Redmine: $REDMINE/versions/$RELEASE"
    exit
fi

# Some branches may not be local, get all
# A better version may strip duplicates (when 2 branches are the same, e.g. local and remote or between 2 remotes)
# Only the name is not sufficient, could be not in sync
# grep: to check multiple values at the same time use a milti-line variable or grep -f "$tmpfile"
# "* " is added at the beginning of the current branch, needs to be removed
VER_BRANCHES=$(git branch -al | grep "$VER_ISSUES"  | sed -e 's/^\*//' -e 's/^ *//' -e 's/ *$//')
VER_BRANCHES_LOCAL=$(echo "$VER_BRANCHES" | grep -v '^remotes')

VER_NOBRANCH=
for i in $VER_ISSUES; do
    [[ ! "$VER_BRANCHES" = *${i}* ]] && VER_NOBRANCH="$VER_NOBRANCH $i"
done

# All the branches merged directly in the current release branch
MERGED_BRANCHES=$(git branch --merged $RELEASE_BRANCH | grep "$VER_ISSUES" | sed -e 's/^ *//' -e 's/ *$//')
VER_NOMERGED=
for i in $VER_ISSUES; do
    [[ ! "$MERGED_BRANCHES" =  *${i}* ]] && VER_NOMERGED="$VER_NOMERGED $i"
done

# Both VER_NOBRANCH and VER_NOMERGED must be sorted
VER_ONLYBRANCH="$(comm -13 <(echo "$VER_NOBRANCH" | xargs -n1) <(echo "$VER_NOMERGED" | xargs -n1))"
tmp=$(comm -23 <(echo "$VER_NOBRANCH" | xargs -n1) <(echo "$VER_NOMERGED" | xargs -n1))
[[ -n "$tmp" ]] && { echo "WARNING: these issues appear to be merged but not in branches:"; echo " " $tmp; }

loginfo "Checking ${RELEASE} (${VER_ID})"
loginfo "Issues ($(echo $VER_ISSUES | wc -w)):"
loginfo " " $VER_ISSUES
echo "Issues without a branch ($(echo $VER_NOBRANCH | wc -w | tr -d '[:space:]')):"
echo "$VER_NOBRANCH"
if [[ -n  "$VERBOSE" ]]; then
    echo " Detailed list:"
    for i in $VER_NOBRANCH; do
        tmp=$(echo "$VER_ISSUES_EXT" | jq '. | select(.id == '$i') | .subject ')
        echo "  $i: " ${tmp}
        echo "$REDMINE/issues/$i"
    done
fi

loginfo "Issues without a branch merged directly in $RELEASE_BRANCH ($(echo $VER_NOMERGED | wc -w | tr -d '[:space:]')), $(echo $VER_ONLYBRANCH | wc -w | tr -d '[:space:]') with branch:"
loginfo "$VER_NOMERGED"
# issues with branches, but not contained (not merged) in the release
VER_NOCONTAIN=
# list of the branches corresponding to the issues in VER_NOCONTAIN
VER_NOCONTAIN_BRANCH=
if [[ -n "$VER_ONLYBRANCH" ]]; then
    loginfo "These issues have branches but have not been merged directly in $RELEASE_BRANCH:"
    for i in $VER_ONLYBRANCH; do
        line="${i}: "
        separator=
        nocontain=false
        for j in $(grep $i <(echo "$VER_BRANCHES")); do
            # not a good test, $j should be a REF:
            # if ! git branch --contains $j $RELEASE_BRANCH > /dev/null 2>&1; then
            merge_base=$(git merge-base $RELEASE_BRANCH $j 2> /dev/null)
            merge_source_current_commit=$(git rev-parse $j 2> /dev/null)
            # an existing branch (these are coming from branch -al) should never be w/o reference
            [[ -z "$merge_source_current_commit" ]] && echo "ERROR: branch $j is empty!"
            if [[ "$merge_base" != "$merge_source_current_commit" ]]; then
                # j is not merged in RELEASE_BRANCH (at least not the current tip)
                separator="$separator (NC)"
                nocontain=true
                VER_NOCONTAIN_BRANCH="$VER_NOCONTAIN_BRANCH $j"
            fi
            line="${line}$separator $j"
            separator=','
        done
        $nocontain && VER_NOCONTAIN="$VER_NOCONTAIN $i"
        loginfo " $line"
    done
else
    loginfo "All issue related branches have been merged directly in $RELEASE_BRANCH"
fi
if [[ -n "$VER_NOCONTAIN" ]]; then
    echo "Issues with a branch not contained in $RELEASE_BRANCH ($(echo $VER_NOCONTAIN | wc -w | tr -d '[:space:]')):"
    echo " $VER_NOCONTAIN"
    echo " List of the branches:"
    echo "  $VER_NOCONTAIN_BRANCH"
else
    loginfo "All issue related branches have been merged (at least indirectly)"
fi

# echo "Version branches: "
# echo "$VER_BRANCHES"
# echo "Version merged branches: "
# echo "$MERGED_BRANCHES"
