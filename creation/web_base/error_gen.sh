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
# detail (str)                                              #
# generate and append detail tag                            #
# --------------------------------------------------------- #
function detail() {
    echo "  <detail>" >> otrb_output.xml
    echo "$1" | awk '{print "    " $0}' >> otrb_output.xml
    echo "  </detail>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# header (id,status)                                        #
# generate and append header tag                            #
# --------------------------------------------------------- #
function header() {
    XML='<?xml version="1.0"?>'
    OSG="<OSGTestResult id=\""
    OSGEnd="\" version=\"4.3.1\">"
    RES="<result>\n    <status>$2</status>"
    echo -e "${XML}\n${OSG}$1${OSGEnd}\n  ${RES}" > otrb_output.xml #NOTE: wipe previous otrb_output.xml file
    return
}

# --------------------------------------------------------- #
# midsection ()                                             #
# generate and append result close tags.                    #
# --------------------------------------------------------- #
function midsection(){
    echo "  </result>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# close ()                                                  #
# generate and append header close tags.                    #
# --------------------------------------------------------- #
function close(){
    echo "</OSGTestResult>" >> otrb_output.xml
    return
}

# --------------------------------------------------------- #
# write_metric (key,val)                                    #
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
    myid="$1"
    shift

    header "$myid" OK
    while [ $# -gt 1 ]; do
      write_metric "$1" "$2"
      shift
      shift
    done
    midsection
    close
    return
}

# --------------------------------------------------------- #
# status_error ()                                           #
# generate and append status tag for error jobs             #
# --------------------------------------------------------- #
function status_error(){
    myid="$1"
    shift

    header "$myid" ERROR
    write_metric "failure" "$1"
    shift
    detstr=$1
    shift
    while [ $# -gt 1 ]; do
      write_metric "$1" "$2"
      shift
      shift
    done
    midsection
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

shift

case "$mycmd" in
    -error)    status_error "$@";;
    -ok)       status_ok "$@";;
    *)  (warn "Unknown option $mycmd"; usage) 1>&2; exit 1
esac


