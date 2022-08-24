#!/bin/bash

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#*******************************************************************#
# utils_xml.sh                                                      #
# This script contains xml utility functions                        #
#*******************************************************************#

################################
# Create the xml general content
# Arguments:
#   1: result
construct_xml() {
  local result tStart tEnd cmd glidein_end_time
  result=$1
  glidein_end_time="$(date +%s)"
  cmd="$0 ${GLOBAL_ARGS}"
  tStart="$(date --date=@"${startup_time}" +%Y-%m-%dT%H:%M:%S%:z)"
  tEnd="$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)"
  create_xml OSG --id glidein_startup.sh { oe { e --name cwd "${start_dir}" } t { c "${cmd}" tS "${tStart}" tE "${tEnd}" } "${result}" }
}

################################
# Extract the parent xml fname (element inside the id of OSGTestResult)
# Arguments:
#   1: exit code
extract_parent_fname(){
  local exitcode last_result last_script_name
  exitcode=$1
  if [ -s otrx_output.xml ]; then # file exists and is not 0 size
      last_result=$(cat otrx_output.xml)
      if [ "${exitcode}" -eq 0 ]; then
          echo "SUCCESS"
      else
          last_script_name=$(echo "${last_result}" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}')
          echo "${last_script_name}"
      fi
  else
      echo "Unknown"
  fi
}

################################
# Extract the parent xml details
# Arguments:
#   1: exit code
extract_parent_xml_detail() {
  local glidein_end_time exitcode last_result last_script_name last_script_reason my_reason
  exitcode=$1
  glidein_end_time="$(date +%s)"
  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result="$(cat otrx_output.xml)"
      if [ "${exitcode}" -eq 0 ]; then
          echo "  <result>"
          echo "    <status>OK</status>"
          #propagate metrics as well
          echo "${last_result}" | grep '<metric '
          echo "  </result>"
      else
          last_script_name=$(echo "${last_result}" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}')
          last_script_reason=$(echo "${last_result}" | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}')
          my_reason="     Validation failed in ${last_script_name}. ${last_script_reason}" "${last_script_name}"
          echo "  <result>"
          echo "    <status>ERROR</status>
                <metric name=\"TestID\" ts=\"$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">${last_script_name}</metric>"
          # propagate metrics as well (will include the failure metric)
          echo "${last_result}" | grep '<metric '
          echo "  </result>"
          echo "  <detail>${my_reason}</detail>"
      fi
  else
      # create a minimal XML file, else
       echo "  <result>"
      if [ "${exitcode}" -eq 0 ]; then
          echo "    <status>OK</status>"
      else
          echo "    <status>ERROR</status>"
          echo "    <metric name=\"failure\" ts=\"$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)\" uri=\"local\">Unknown</metric>"
      fi
      echo "  </result>
  <detail>
    No detail. Could not find source XML file.
  </detail>"
  fi
}

################################
# Convert base xml to simple xml
# Arguments:
#   1: final result
basexml2simplexml() {
  local final_result
  final_result="$1"
  # augment with node info
  echo "${final_result}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<operatingenvironment>/{fr=0;}'
  echo "    <env name=\"client_name\">${client_name}</env>"
  echo "    <env name=\"client_group\">${client_group}</env>"
  echo "    <env name=\"user\">$(id -un)</env>"
  echo "    <env name=\"arch\">$(uname -m)</env>"
  if [ -e '/etc/redhat-release' ]; then
      echo "    <env name=\"os\">$(cat /etc/redhat-release)</env>"
  fi
  echo "    <env name=\"hostname\">$(uname -n)</env>"
  echo "${final_result}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

################################
# Convert simple xml to long xml
# Arguments:
#   1: simple final result
#   2: global result
simplexml2longxml() {
  local final_result_simple global_result
  final_result_simple="$1"
  global_result="$2"
  echo "${final_result_simple}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<OSGTestResult /{fr=0;}'
  if [ "${global_result}" != "" ]; then
      # subtests first, so it is more readable, when tailing
      echo '  <subtestlist>'
      echo '    <OSGTestResults>'
      echo "${global_result}" | awk '{print "      " $0}'
      echo '    </OSGTestResults>'
      echo '  </subtestlist>'
  fi
  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<OSGTestResult /{fr=1;}/<operatingenvironment>/{fr=0;}'
  echo "    <env name=\"glidein_factory\">${glidein_factory}</env>"
  echo "    <env name=\"glidein_name\">${glidein_name}</env>"
  echo "    <env name=\"glidein_entry\">${glidein_entry}</env>"
  echo "    <env name=\"condorg_cluster\">${condorg_cluster}</env>"
  echo "    <env name=\"condorg_subcluster\">${condorg_subcluster}</env>"
  echo "    <env name=\"glidein_credential_id\">${glidein_cred_id}</env>"
  echo "    <env name=\"condorg_schedd\">${condorg_schedd}</env>"
  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

################################
# Add spaces, support to create_xml
# Global:
#   xml
add_spaces(){
  local c
  for (( c=1; c<=spaces; c++ ))
      do
        xml+=" "
      done
}

################################
# Create an xml file structure:
# create_xml TAG --option option_value .... tag_value TAG2 .....
# use '{' to specify the start if an inner tag and use '}' to specify the end
# use create_xml -s SPACES ... in case you want to create a subpart of an xml file not starting from the beginning specifying
# the number of spaces needed at the beginning in order to have a good indentation
# use create_xml -t to require as output only the tail tag of the xml file, i.e. </OSGTestResult>
# use create_xml -h to require as output only the header tag of the xml file, i.e. <?xml version=\"1.0\"?>"
# Arguments:
#   @: tags, options, values
# Global:
#   spaces
#   xml
#   end_xml
#   result
create_xml(){
    xml=""
    end_xml=""
    declare -i spaces=0;
    if [[ $1 == "-h" ]]
        then
            result="<?xml version=\"1.0\"?>"
            echo -e "$result"
            return 0
    fi
    if [[ $1 == "-t" ]]
        then
            result="</OSGTestResult>"
            echo -e "$result"
            return 0
    fi
    if [[ $1 == "-s" ]]
    then
        spaces+=$2
        shift 2
    else
      xml="<?xml version=\"1.0\"?>"
      xml+="\n"
    fi
    until [ $# -lt 1 ]
    do
        case "$1" in
            OSG|O)
                    add_spaces
                    xml+="<OSGTestResult"
                    while [[ "$2" = "-"* ]]
                    do
                       if [ $2 == "--id" ]; then
                          xml+=" id=\"$3\""
                       fi
                       shift 2
                    done
                    xml+=" version=\"4.3.1\">"
                    if [ "$2" == "{" ]; then
                        spaces+=1
                        end_xml="</OSGTestResult>"$end_xml
                        shift 1
                    else
                        xml+="</OSGTestResult>"
                    fi;;
            OSGShort|OS)
                    add_spaces
                    xml+="<OSGTestResult>"
                    if [ "$2" == "{" ]; then
                        spaces+=1
                        end_xml="</OSGTestResult>"$end_xml
                        shift 1
                    else
                        xml+="</OSGTestResult>"
                    fi;;
            operatingenvironment|oe)
                    add_spaces
                    xml+="<operatingenvironment>"
                    if [ "$2" == "{" ]; then
                        spaces+=1
                        end_xml="</operatingenvironment>"$end_xml
                        shift 1
                    else
                        xml+="</operatingenvironment>"
                    fi;;
            env|e)
                    add_spaces
                    xml+="<env"
                    while [[ "$2" = "-"* ]]
                    do
                          if [ "$2" == "--name" ]; then
                              xml+=" name=\"$3\""
                          fi
                          shift 2
                    done
                    xml+=">$2</env>"
                    shift 1;;
            test|t)
                    add_spaces
                    xml+="<test>"
                    if [ "$2" == "{" ]; then
                        spaces+=1
                        end_xml="</test>"$end_xml
                        shift 1
                    else
                        xml+="</test>"
                    fi;;
            cmd|c)
                    add_spaces
                    xml+="<cmd>$2</cmd>"
                    shift 1;;
            tStart|tS)
                    add_spaces
                    xml+="<tStart>$2</tStart>"
                    shift 1;;
            tEnd|tE)
                    add_spaces
                    xml+="<tEnd>$2</tEnd>"
                    shift 1;;
            result|r)
                    add_spaces
                    xml+="<result>"
                    if [ "$2" == "{" ]; then
                        spaces+=1
                        end_xml="</result>"$end_xml
                        shift 1
                    else
                        xml+="</result>"
                    fi;;
            status|s)   add_spaces
                        xml+="<status>$2</status>"
                        shift 1;;
            metric|m)     add_spaces
                        xml+="<metric"
                        while [[ "$2" = "-"* ]]
                        do
                              if [ "$2" == "--name" ]; then
                                 xml+=" name=\"$3\""
                              elif [ "$2" == "--ts" ]; then
                                 xml+=" ts=\"$3\""
                              elif [ "$2" == "--uri" ]; then
                                 xml+=" uri=\"$3\""
                              fi
                              shift 2
                        done
                        xml+=">$2</metric>"
                        shift 1;;
            detail|d)     add_spaces
                        xml+="<detail>$2</detail>"
                        shift 1;;
            "}")        output=$(echo $end_xml | cut -d'>' -f 1 | awk '{print $1">"}')
                        spaces=spaces-1
                        add_spaces
                        xml+=$output
                        end_xml=${end_xml#"$output"};;
            *)  xml+=$1;;
        esac
        shift 1
        if [ ! $# -eq 0 ]; then
            xml+="\n"
        fi
    done
    result=$xml
    echo -e "$result"
}
