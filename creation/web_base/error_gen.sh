#!/bin/bash

#############################################################
# variables                                                 #
#############################################################
OK_FILE="ok_output"
ERROR_FILE="error_output"


# --------------------------------------------------------- #
# detail ()                                                 #
# generate and append detail tag                            #
# --------------------------------------------------------- #
function detail() {
    echo "    <detail>"`cat string`"</detail>" >> output
    return
}

# --------------------------------------------------------- #
# header ()                                                 #
# generate and append header tag                            #
# --------------------------------------------------------- #
function header() {
    OSG="<OSGTestResult id=\""
    OSGEnd="\" version=\"1.2\">"
    RES="<result>"
    echo -e "${OSG}$1${OSGEnd}\n  ${RES}" > output #NOTE: wipe previous output file
    return
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
    echo -e "  </result>\n</OSGTestResult>" >> output
    return
}

# --------------------------------------------------------- #
# metric_error ()                                           #
# generate and append metric tag for errors                 #
# --------------------------------------------------------- #
function metric_error(){
    DATE=`date "+%Y-%m-%dT%H:%M:%S"`
    echo "    <metric name=\"failure\" ts=\"${DATE}\" uri=\"local\">$1</metric>" >> output
    echo "    <metric name=\"$2\" ts=\"${DATE}\" uri=\"local\">$3</metric>" >> output
    if [ $# -eq 5 ]; then
        echo "    <metric name=\"$4\" ts=\"${DATE}\" uri=\"local\">$5</metric>" >> output
    fi
    return
}

# --------------------------------------------------------- #
# metric_ok ()                                              #
# generate and append metric tag for OK jobs                #
# --------------------------------------------------------- #
function metric_ok(){
    DATE=`date "+%Y-%m-%dT%H:%M:%S"`
    echo "    <metric name=\"$1\" ts=\"${DATE}\" uri=\"local\">$2</metric>" >> output
    return
}

# --------------------------------------------------------- #
# status_ok ()                                              #
# generate and append status tag for OK jobs                #
# --------------------------------------------------------- #
function status_ok(){
    echo "    <status>OK</status>" >> output
    metric_ok "$@"
    close
    if [ -f $OK_FILE ]; then
	cat output >> $OK_FILE
    else
	cat output > $OK_FILE
    fi
    return
}

# --------------------------------------------------------- #
# status_error ()                                           #
# generate and append status tag for error jobs             #
# --------------------------------------------------------- #
function status_error(){
    echo "    <status>ERROR</status>" >> output
    metric_error "$@"
    detail
    close
    if [ -f $ERROR_FILE ]; then
	cat output >> $ERROR_FILE
    else
	cat output > $ERROR_FILE
    fi
    return
}


# --------------------------------------------------------- #
# usage ()                                                  #
# print usage                                               #
# --------------------------------------------------------- #
usage()
{
	echo "Usage: -error -ok {params}"; 
	return
}


############################################################
#
# Main
#
############################################################
mycmd=$1
header $2

shift
shift

case "$mycmd" in
    -error)    status_error "$@";;
    -ok)       status_ok "$@";;
    *)  (warn "Unknown option $mycmd"; usage) 1>&2; exit 1
esac


