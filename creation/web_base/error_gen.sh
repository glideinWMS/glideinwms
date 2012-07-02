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
    echo "    <detail>" >> output
    echo -e "$1" | awk '{print "       " $0}' >> output
    echo "    </detail>" >> output
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
# write_metric ()                                           #
# generate and append metric tag                            #
# --------------------------------------------------------- #
function write_metric(){
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
    while [ $# -gt 1 ]; do
      write_metric "$1" "$2"
      shift
      shift
    done
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
    write_metric "failure" "$1"
    shift
    detstr=$1
    shift
    while [ $# -gt 1 ]; do
      write_metric "$1" "$2"
      shift
      shift
    done
    detail "$detstr"
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
	echo "Usage: -error|-ok {params}"; 
	echo "       -error id failstr detailfail {metricid metricval}+"; 
	echo "       -ok    id                    {metricid metricval}+"; 
	return
}


############################################################
#
# Main
#
############################################################
mycmd=$1
header "$2"

shift
shift

case "$mycmd" in
    -error)    status_error "$@";;
    -ok)       status_ok "$@";;
    *)  (warn "Unknown option $mycmd"; usage) 1>&2; exit 1
esac


