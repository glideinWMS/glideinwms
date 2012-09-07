#!/bin/bash
#
# Project:
#   glideinWMS
#
# Description:
#   Helper script to create the XML output file
#   containing the result of the validation test
#

# --------------------------------------------------------- #
# detail ()                                                 #
# generate and append detail tag                            #
# --------------------------------------------------------- #
function detail() {
    echo "    <detail>" >> otrb_output.xml
    echo "$1" | awk '{print "       " $0}' >> otrb_output.xml
    echo "    </detail>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# header ()                                                 #
# generate and append header tag                            #
# --------------------------------------------------------- #
function header() {
    XML='<?xml version="1.0"?>'
    OSG="<OSGTestResult id=\""
    OSGEnd="\" version=\"4.3.1\">"
    RES="<result>"
    echo -e "${XML}\n${OSG}$1${OSGEnd}\n  ${RES}" > otrb_output.xml #NOTE: wipe previous otrb_output.xml file
    return
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
    echo -e "  </result>\n</OSGTestResult>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# write_metric ()                                           #
# generate and append metric tag                            #
# --------------------------------------------------------- #
function write_metric(){
    DATE=`date "+%Y-%m-%dT%H:%M:%S%:z"`
    echo "    <metric name=\"$1\" ts=\"${DATE}\" uri=\"local\">$2</metric>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# status_ok ()                                              #
# generate and append status tag for OK jobs                #
# --------------------------------------------------------- #
function status_ok(){
    echo "    <status>OK</status>" >> otrb_output.xml
    while [ $# -gt 1 ]; do
      write_metric "$1" "$2"
      shift
      shift
    done
    close
    return
}

# --------------------------------------------------------- #
# status_error ()                                           #
# generate and append status tag for error jobs             #
# --------------------------------------------------------- #
function status_error(){
    echo "    <status>ERROR</status>" >> otrb_output.xml
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
    return
}


# --------------------------------------------------------- #
# usage ()                                                  #
# print usage                                               #
# --------------------------------------------------------- #
usage() {
	echo "Usage: -error|-ok [params]"; 
	echo "       -error id failstr detailfail [metricid metricval]+"; 
	echo "       -ok    id                    [metricid metricval]+"; 
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


