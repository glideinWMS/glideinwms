. utils_tarballs.sh
. utils_signals.sh
. utils_log.sh
. utils_xml.sh
. utils_params.sh
. utils_crypto.sh
. glidein_cleanup.sh
. utils_fetch.sh

################################
# Function used to perform a wget request
# Arguments:
#   @: wget args
perform_wget() {
    wget_args=("$@")
    arg_len="${#wget_args[@]}"
    ffb_url="${wget_args[0]}"
    ffb_repository=$(dirname "${ffb_url}")
    ffb_real_fname=$(basename "${ffb_url}")
    proxy_url="None"
    for ((i=0; i<arg_len; i++));
    do
        if [ "${wget_args[${i}]}" = "--output-document" ]; then
            ffb_tmp_outname=${wget_args[${i}+1]}
        fi
        if [ "${wget_args[${i}]}" = "--proxy" ]; then
            proxy_url=${wget_args[${i}+1]}
        fi
    done
    START=$(date +%s)
    if [ "${proxy_url}" != "None" ]; then
        wget_args=(${wget_args[@]:0:${arg_len}-2})
        wget_cmd=$(echo "env http_proxy=${proxy_url} wget" "${wget_args[@]}"| sed 's/"/\\\"/g')
        wget_resp=$(env http_proxy="${proxy_url}" wget "${wget_args[@]}" 2>&1)
        wget_retval=$?
    else
        wget_cmd=$(echo "wget" "${wget_args[@]}"| sed 's/"/\\\"/g')
        wget_resp=$(wget "${wget_args[@]}" 2>&1)
        wget_retval=$?
    fi

    if [ ${wget_retval} -ne 0 ]; then
        wget_version=$(wget --version 2>&1 | head -1)
        log_warn "${wget_cmd} failed. version:${wget_version}  exit code ${wget_retval} stderr: ${wget_resp}"
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        # create_xml operatingenvironment { env cwd ${PWD} env uname $(uname -a) env release $(cat /etc/system-release) env wget_version ${wget_version}
        echo "<OSGTestResult id=\"perform_wget\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
    <env name=\"uname\">$(uname -a)</env>
    <env name=\"release\">$(cat /etc/system-release)</env>
    <env name=\"wget_version\">${wget_version}</env>
  </operatingenvironment>
  <test>
    <cmd>${wget_cmd}</cmd>
    <tStart>$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_url}</metric>
    <metric name=\"http_proxy\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${proxy_url}</metric>
    <metric name=\"source_type\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_id}</metric>
  </result>
  <detail>
  Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${wget_resp}
  </detail>
</OSGTestResult>" > otrb_output.xml
        log_warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        echo "<?xml version=\"1.0\"?>" > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${wget_retval}
}

################################
# Function used to perform a curl request
# Arguments:
#   @: curl args
perform_curl() {
    curl_args=("$@")
    arg_len="${#curl_args[@]}"
    ffb_url="${curl_args[0]}"
    ffb_repository="$(dirname "${ffb_url}")"
    ffb_real_fname="$(basename "${ffb_url}")"
    for ((i=0; i<arg_len; i++));
    do
        if [ "${curl_args[${i}]}" = "--output" ]; then
            ffb_tmp_outname="${curl_args[${i}+1]}"
        fi
        if [ "${curl_args[${i}]}" = "--proxy" ]; then
            proxy_url="${curl_args[${i}+1]}"
        fi
    done

    START="$(date +%s)"
    curl_cmd="$(echo "curl" "${curl_args[@]}" | sed 's/"/\\\"/g')"
    curl_resp="$(curl "${curl_args[@]}" 2>&1)"
    curl_retval=$?
    if [ ${curl_retval} -eq 0 ] && [ ! -e "${ffb_tmp_outname}" ] ; then
        touch "${ffb_tmp_outname}"
    fi


    if [ "${curl_retval}" -ne 0 ]; then
        curl_version="$(curl --version 2>&1 | head -1)"
        log_warn "${curl_cmd} failed. version:${curl_version}  exit code ${curl_retval} stderr: ${curl_resp} "
        # cannot use error_*.sh helper functions
        # may not have been loaded yet, and wget fails often
        echo "<OSGTestResult id=\"perform_curl\" version=\"4.3.1\">
  <operatingenvironment>
    <env name=\"cwd\">${PWD}</env>
    <env name=\"uname\">$(uname -a)</env>
    <env name=\"release\">$(cat /etc/system-release)</env>
    <env name=\"curl_version\">${curl_version}</env>
  </operatingenvironment>
  <test>
    <cmd>${curl_cmd}</cmd>
    <tStart>$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
    <tEnd>$(date +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
  </test>
  <result>
    <status>ERROR</status>
    <metric name=\"failure\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Network</metric>
    <metric name=\"URL\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_url}</metric>
    <metric name=\"http_proxy\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${proxy_url}</metric>
    <metric name=\"source_type\" ts=\"$(date --date=@"${START}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${ffb_id}</metric>
  </result>
  <detail>
  Failed to load file '${ffb_real_fname}' from '${ffb_repository}' using proxy '${proxy_url}'.  ${curl_resp}
  </detail>
</OSGTestResult>" > otrb_output.xml
        log_warn "Failed to load file '${ffb_real_fname}' from '${ffb_repository}'."

        if [ -f otr_outlist.list ]; then
            chmod u+w otr_outlist.list
        else
            touch otr_outlist.list
        fi
        cat otrb_output.xml >> otr_outlist.list
        echo "<?xml version=\"1.0\"?>" > otrx_output.xml
        cat otrb_output.xml >> otrx_output.xml
        rm -f otrb_output.xml
        chmod a-w otr_outlist.list
    fi
    return ${curl_retval}
}
