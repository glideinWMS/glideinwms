#!/bin/bash
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
-h      Print this help
-v      Verbose mode
RELEASE Is the Version name in Redmine
RBRANCH Is the release branch name in Git, used to check if all issue branches have been merged
        It can be normally derived by the RELEASE value
This command must be run inside the Git repository. Future versions will query Github.
EOF
}

loginfo() {
    [[ -n "$VERBOSE" ]] && echo "$@"
}

VERBOSE=
while getopts ":hv" option
do
  case "${option}"
  in
  h) help_msg; exit 0;;
  v) VERBOSE=yes;;
  : ) echo "$filename: illegal option: -$OPTARG requires an argument" 1>&2; help_msg 1>&2; exit 1;;
  *) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  \?) echo "$filename: illegal option: -$OPTARG" 1>&2; help_msg 1>&2; exit 1;;
  esac
done
shift $((OPTIND-1))

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
    if [[ $RELEASE = v3_5* ]]; then
        RELEASE_BRANCH=master
    if [[ $RELEASE = v3_6* ]]; then
        RELEASE_BRANCH=master
    elif [[ $RELEASE = v3_7* ]]; then
        RELEASE_BRANCH=branch_v3_7
    elif [[ $RELEASE = v3_8* ]]; then
        RELEASE_BRANCH=branch_v3_8
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
VER_ID=$(curl -s -H "Content-Type: application/json" -X GET $REDMINE/projects/glideinwms/versions.json | jq ' .versions[] | select(.name == "'$RELEASE'") | .id')
if [[ -z "$VER_ID" ]]; then
    echo "ERROR: Unable to find the ID for version ${RELEASE}. Please check the name and try again."
    exit 1
fi

# Issues are one per line, so grep does an OR in the matching. To flatten, use unquoted
# status_id=* is required, otherwise Redmine will ignore closed issues
VER_ISSUES_EXT=$(curl -s -H "Content-Type: application/json" -X GET $REDMINE/issues.json?project_id=$GWMS_PROJECT_ID\&fixed_version_id=$VER_ID\&status_id=\*  | jq '.issues[] | { id: .id, subject: .subject } ' )
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
VER_BRANCHES=$(git branch -al | grep "$VER_ISSUES"  | sed -e 's/^ *//' -e 's/ *$//')
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
VER_NOCONTAIN=
VER_NOCONTAIN_BRANCH=
if [[ -n "$VER_ONLYBRANCH" ]]; then
    loginfo "These issues have branches but have not been merged directly in $RELEASE_BRANCH:"
    for i in $VER_ONLYBRANCH; do
        line="${i}: "
        separator=
        nocontain=
        for j in $(grep $i <(echo "$VER_BRANCHES")); do
            if ! git branch --contains $j $RELEASE_BRANCH > /dev/null 2>&1; then
                separator="$separator (NC)"
                nocontain=true
                VER_NOCONTAIN_BRANCH="$VER_NOCONTAIN_BRANCH $j"
            fi
            line="${line}$separator $j"
            separator=','
        done
        [[ -n "$nocontain" ]] && VER_NOCONTAIN="$VER_NOCONTAIN $i"
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


