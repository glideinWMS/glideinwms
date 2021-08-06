#!/bin/bash
# Functiond to process bigfiles

SCRIPTS_SUBDIR=build/ci
TARNAME=glideinwms-bigfiles-latest.tgz
 
robust_realpath() {
    if ! realpath "$1" 2>/dev/null; then
        echo "$(cd "$(dirname "$1")"; pwd -P)/$(basename "$1")"
    fi
}

logerror() {
    echo "$filename ERROR: $1" >&2
}

logverbose() {
    [ -n "$VERBOSE" ] && echo "$1" 
}

help_msg() {
  cat << EOF
${filename} [options]
  Runs the test form COMMAND on the current glideinwms subdirectory, as is or checking out a branch from the repository.
 Options:
  -h          print this message
  -v          verbose
  -d REPO_DIR GlideinWMS repository root directory (default: trying to guess, otherwise '.')
  -p          pull: download and unpack the big files to the bigfiles directory if not already there
  -P          push: compress the big files
  -s SERVER   upload to SERVER via scp the bundled big files (ignored it -P is not specified)         
  -u          update (download and unpack even if files are already there). Used with -r and -p
  -r          replace the symbolic links with the linked linked to files in the bigfiles directory
              and write a list of replaced files to BF_LIST. Big files are downloaded if not in the bigfiles directory
  -R          copy the big files (from BF_LIST) to the bigfiles directory and replace the big files with the 
              symbolic links to the bigfiles directory
  -b BF_LIST  big files list (default: REPO_DIR/$BIGFILES_LIST)
 Examples:
  ./bifiles.sh -p           Use this before running unit tests or packaging the software, to pull the big files
  ./bifiles.sh -pr          Use this if you plan to edit a big file in place. Will pull and replace the symbolic links 
                            w/ the actual file
  ./bifiles.sh -PR          Use this before committing if you used ./bifiles.sh -pr. Will make sure that the big file
                            is replaced with the proper link. Remember to send the archive wit the new 
                            big files ($TARNAME) to a GlideinWMS librarian
EOF
}

guess_repo_dir() {
    # Guesses work for glideinwms, ., .. (from bigfiles), ../.. (from build/bigfiles)
    # Using bigfiles/README.txt as marker. Default is "."
    if [[ -e glideinwms/bigfiles/README.txt ]]; then
        echo "glideinwms"
    elif [[ -e ../bigfiles/README.txt ]]; then
        echo ".."
    elif [[ -e ../../bigfiles/README.txt ]]; then
        echo "../.."
    else
        echo "."
    fi
}

parse_options() {
    # Parse and validate options to the bigfiles_aux command
    # OPTS=$(getopt --options $SHORT --long $LONG --name "$0" -- "$@")
    # The man page mentions optional options' arguments for getopts but they are not handled correctly
    # Defaults
    # REPO_DIR="${MYDIR}/../.."
    # REPO_DIR="glideinwms"
    REPO_DIR=$(guess_repo_dir)
    BIGFILES_LIST=bigfiles/bigfiles_list.txt
    UPDATE_FILES=
    REPLACE_FILES=
    DO_DOWNLOAD=
    BIGFILES_SERVER=
    BF_PULL=
    BF_PUSH=
    [[ "$filename" = "bigfiles-pull"* ]] && BF_PULL=yes
    [[ "$filename" = "bigfiles-push"* ]] && BF_PUSH=yes
    while getopts ":hpPs:urRvb:d:" option
    do
        case "${option}"
        in
        h) help_msg; exit 0;;
        p) BF_PULL=yes;;
        P) BF_PUSH=yes;;
        s) BIGFILES_SERVER="$OPTARG";;
        u) UPDATE_FILES=yes;;
        r) REPLACE_LINKS=yes;;
        R) REPLACE_BIGFILES=yes;;
        v) VERBOSE=yes;;
        b) BIGFILES_LIST="$OPTARG";;
        d) REPO_DIR="$OPTARG";;
        : ) logerror "illegal option: -$OPTARG requires an argument"; help_msg 1>&2; exit 1;;
        *) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
        \?) logerror "illegal option: -$OPTARG"; help_msg 1>&2; exit 1;;
        esac
    done
    # Validate options
    if [[ -n "${REPLACE_LINKS}${BF_PULL}" && -n "${REPLACE_BIGFILES}${BF_PUSH}" ]]; then 
        logerror "illegal option combination: -r or -p cannot be used at the same time of -R or -P"
        help_msg 1>&2
        exit 1
    fi
    [[ -n "$BF_PULL" || -n "$REPLACE_LINKS" ]] && DO_DOWNLOAD=yes
    [[ "$BIGFILES_SERVER" = "fnalu" ]] && BIGFILES_SERVER="fnalu.fnal.gov:/web/sites/glideinwms.fnal.gov/htdocs/downloads"
    [[ "$BIGFILES_SERVER" = "fnalu.fnal.gov" ]] && BIGFILES_SERVER="fnalu.fnal.gov:/web/sites/glideinwms.fnal.gov/htdocs/downloads"
}

pull() {
    # This function is executed in "$REPO_DIR/bigfiles"
    local cmd_out
    logverbose "Starting the big files download"
    [ -f "./$TARNAME" ] && rm "./$TARNAME"
    # Download the latest big files
    if ! wget -q "https://glideinwms.fnal.gov/downloads/${TARNAME}" 2> /dev/null; then
      curl -s -o "./$TARNAME"  "https://glideinwms.fnal.gov/downloads/${TARNAME}" 2> /dev/null
    fi    
    if [ ! -e "./$TARNAME" ]; then
      logerror "Download with wget and curl failed. Could not update big files."
      exit 1
    fi
    logverbose "Files retrieved:"
    cmd_out=$(tar xvzf "${TARNAME}" 2>&1)
    logverbose "$cmd_out"
}

push() {
    # This function is executed in "$REPO_DIR/bigfiles"
    # 1. scp PATH: host:directory
    # ./[pull|push]-bigfiles.sh kept for compatibility
    local cmd_out
    cmd_out=$(tar --exclude='./README.txt' --exclude='./pull-bigfiles.sh' --exclude='./push-bigfiles.sh' --exclude="./$TARNAME" -cvzf "./$TARNAME" ./* 2>&1)
    logverbose "New files saved to ${TARNAME}:"
    logverbose "$cmd_out"
    # upload to the server
    if [[ -n "$1" ]]; then
        local tar_time
        tar_time=$(date +"%Y%m%d-%H%M")
        logverbose "Uploading the file to $1..."
        if ! scp -q "$TARNAME" "$1/glideinwms-bigfiles-${tar_time}.tgz"; then
            logerror "Upload failed"
        else
            ssh "${1%:*}" "cd ${1#*:} && rm -f ${TARNAME} && ln -s glideinwms-bigfiles-${tar_time}.tgz ${TARNAME}"
            logverbose "Upload completed"
        fi
    fi
}

_main() {
    # Setup the build environment
    filename="$(basename $0)"
    full_command_line="$*"
    export MYDIR=$(dirname $0)

    parse_options "$@"
    
    # Abort if the branch has no big files (bigfiles directory)
    if [ ! -d "$REPO_DIR/bigfiles" ]; then
        logverbose "No bigfiles directory. Nothing to do. Exiting"
        exit 0
    fi
    # Should download and expand the bigfiles? Using "cvmfs_utils.tar.gz" to verify that files have been expanded
    if [[ -n "$DO_DOWNLOAD" ]]; then
        if [[ -n "$UPDATE_FILES" || ! -e "$REPO_DIR/bigfiles/cvmfs_utils.tar.gz" ]]; then
            pushd "$REPO_DIR/bigfiles" > /dev/null
            if ! pull; then
                logerror "Failed to download the big files. Aborting"
                popd > /dev/null
                exit 1
            fi
            popd > /dev/null
        else
            logverbose "Big files already in '$REPO_DIR/bigfiles/'"
        fi
        if [[ -n "$REPLACE_LINKS" ]]; then
            # Replace the links (and write bigfiles_list) if requested 
            pushd "$REPO_DIR" > /dev/null
            rm -f ${BIGFILES_LIST}
            local links_list
            #find . | while read file; do dosomething "$file"; done
            links_list=$(find . \( -path "./doc/api*" -o -path "./unittests*" \) -prune -false -o -type l -print)
            for file in $links_list; do
                to_file=$(readlink "$file")
                if [[ "$file" = *","* || "$to_file" = *","* ]]; then
                    logerror "Invalid file name. No commas allowed ($file -> $to_file). Aborting"
                    popd  > /dev/null
                    exit 1
                fi 
                if [[ "$to_file" = *bigfiles/* ]]; then
                    if rm "$file" && cp "$(dirname "$file")/$to_file" "$file"; then
                        echo "${to_file},${file}" >> "${BIGFILES_LIST}"
                        logverbose "Copied '$(dirname "$file")/$to_file' -> '$file'"
                    else
                        logerror "Failed to copy '$(dirname "$file")/$to_file' -> '$file'"
                    fi
                fi
            done
            popd > /dev/null
        fi
        exit
    fi
    if [[ -n "$REPLACE_BIGFILES" ]]; then
        # replace the files w/ links (using bigfiles_list) if requested
        pushd "$REPO_DIR" > /dev/null
        while read -r line
        do
            to_file="${line%,*}"
            file="${line#*,}"
            cp "$file" "$(dirname "$file")/$to_file"
            rm "$file" 
            ln -sf "$to_file" "$file"
            logverbose "'$file' copied to '$(dirname "$file")/$to_file' and replaced w/ link"
        done < "${BIGFILES_LIST}"
        popd > /dev/null
    fi
    if [[ -n "$BF_PUSH" ]]; then
        pushd "$REPO_DIR/bigfiles" > /dev/null
        if ! push "$BIGFILES_SERVER"; then
            logerror "Failed to pack/push the big files. Aborting"
            popd > /dev/null
            exit 1
        fi
        popd > /dev/null
    fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    _main "$@"
fi

# ci/bigfiles w/ scripts
# in ci scripts
# pre-bigfiles
# post-bigfiles 

