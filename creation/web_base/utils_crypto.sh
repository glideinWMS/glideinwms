################################
# Function used to calculate the md5 sum
# Arguments:
#   1: file name
#   2: option (quiet)
md5wrapper() {
    local ERROR_RESULT="???"
    local ONLY_SUM
    if [ "x$2" = "xquiet" ]; then
        ONLY_SUM=yes
    fi
    local executable=md5sum
    if which ${executable} 1>/dev/null 2>&1; then
        [ -n "${ONLY_SUM}" ] && executable="md5sum \"$1\" | cut -d ' ' -f 1" ||  executable="md5sum \"$1\""
    else
        executable=md5
        if ! which ${executable} 1>/dev/null 2>&1; then
            echo "${ERROR_RESULT}"
            log_warn "md5wrapper error: can't neither find md5sum nor md5"
            return 1
        fi
        [ -n "${ONLY_SUM}" ] && executable="md5 -q \"$1\"" || executable="md5 \"$1\""
    fi
    local res
    # Flagged by some checkers but OK
    if ! res="$(eval "${executable}" 2>/dev/null)"; then
        echo "${ERROR_RESULT}"
        log_warn "md5wrapper error: can't calculate md5sum using ${executable}"
        return 1
    fi
    echo "${res}" # result returned on stdout
}

########################################
# Function used to set the X509_USER_PROXY path to full path to the file
set_proxy_fullpath() {
    if fullpath="$(readlink -f "${X509_USER_PROXY}")"; then
        echo "Setting X509_USER_PROXY ${X509_USER_PROXY} to canonical path ${fullpath}" 1>&2
        export X509_USER_PROXY="${fullpath}"
    else
        echo "Unable to get canonical path for X509_USER_PROXY, using ${X509_USER_PROXY}" 1>&2
    fi
}

#TODO(F): check if all together is ok
########################################
# Function used to set the tokens
set_proxy(){
    [ -n "${X509_USER_PROXY}" ] && set_proxy_fullpath
    num_gct=0
    
    for tk in "$(pwd)/credential_"*".idtoken"; do
      echo "Setting GLIDEIN_CONDOR_TOKEN to ${tk} " 1>&2
      num_gct=$(( num_gct + 1 ))
      export GLIDEIN_CONDOR_TOKEN="${tk}"
      fullpath="$(readlink -f "${tk}" )"
      if [ $? -eq 0 ]; then
         echo "Setting GLIDEIN_CONDOR_TOKEN ${tk} to canonical path ${fullpath}" 1>&2
         export GLIDEIN_CONDOR_TOKEN="${fullpath}"
      else
         echo "Unable to get canonical path for GLIDEIN_CONDOR_TOKEN ${tk}" 1>&2
      fi
    done
    if [ ! -f "${GLIDEIN_CONDOR_TOKEN}" ] ; then
        token_err_msg="problem setting GLIDEIN_CONDOR_TOKEN"
        token_err_msg="${token_err_msg} will attempt to recover, but condor IDTOKEN auth may fail"
        echo "${token_err_msg}"
        echo "${token_err_msg}" 1>&2
    fi
    if [ ! "${num_gct}" -eq  1 ] ; then
        token_err_msg="WARNING  GLIDEIN_CONDOR_TOKEN set ${num_gct} times, should be 1 !"
        token_err_msg="${token_err_msg} condor IDTOKEN auth may fail"
        echo "${token_err_msg}"
        echo "${token_err_msg}" 1>&2
    fi
}
