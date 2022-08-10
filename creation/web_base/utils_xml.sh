################################
# Function used to create the xml content
# Arguments:
#   1: result
# Global:
#    result
#    glidein_end_time
construct_xml() {
  #TODO(F): Check
 # OSG_test_result="<?xml version=\"1.0\"?>
 #   <OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">
 #   <operatingenvironment>
 #       <env name=\"cwd\">%s</env>
 #   </operatingenvironment>
 #   <test>
 #       <cmd>%s %s</cmd>
 #       <tStart>%s</tStart>
 #       <tEnd>%s</tEnd>
 #   </test>
 #   %s
  #  </OSGTestResult>"
  #printf "$OSG_test_result" "${start_dir}" "$0" "${global_args}" "$(date --date=@\"${startup_time}\" +%Y-%m-%dT%H:%M:%S%:z)" "$(date --date=@\"${glidein_end_time}\" +%Y-%m-%dT%H:%M:%S%:z)" "$result"
  #create_xml OSG --id glidein_startup.sh { operatingenvironment { env --name cwd ${start_dir} } test { cmd $0 ${global_args} tStart $(date --date=@"${startup_time}" +%Y-%m-%dT%H:%M:%S%:z) tEnd $(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)} }    
  ##create_xml OSG --id 0 { operatingenvironment { env --name cwd 0 } test { cmd 0 0 tStart 0 tEnd 0 } 0 }      
  echo "<?xml version=\"1.0\"?>
  <OSGTestResult id=\"glidein_startup.sh\" version=\"4.3.1\">
    <operatingenvironment>
      <env name=\"cwd\">${start_dir}</env>
    </operatingenvironment>
    <test>
      <cmd>$0 ${global_args}</cmd>
      <tStart>$(date --date=@"${startup_time}" +%Y-%m-%dT%H:%M:%S%:z)</tStart>
      <tEnd>$(date --date=@"${glidein_end_time}" +%Y-%m-%dT%H:%M:%S%:z)</tEnd>
    </test>
  ${result}
  </OSGTestResult>"
  result="$1"
  glidein_end_time="$(date +%s)"
}

################################
# Function used to extract the parent xml fname
# Arguments:
#   1: exit code
# Global:
#   last_result
#   last_script_name
#   exitcode
extract_parent_fname(){
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
# Function used to extract the parent xml details
# Arguments:
#   1: exit code
# Global:
#   exitcode
#   glidein_end_time
#   last_result
#   last_script_name
#   last_script_reason
#   my_reason
extract_parent_xml_detail() {
 # fail_result="<result>
 #         <status>%s</status>
 #         <metric name=\"TestID\" ts=\"%s\" uri=\"local\">%s</metric>
 #       </result>
 #       <detail>%s</detail>"
 # correct_result_no_details="<result>
 #               <status>%s</status>
 #             </result>"       
 # correct_result="<result>
 #            <status>%s</status>
 #          </result>
 #          <detail>%s</detail>"    
  exitcode=$1
  glidein_end_time="$(date +%s)"
  if [ -s otrx_output.xml ]; then
      # file exists and is not 0 size
      last_result="$(cat otrx_output.xml)"
      if [ "${exitcode}" -eq 0 ]; then
          #printf "$correct_result" "OK"
          echo "  <result>"
          echo "    <status>OK</status>"
          #propagate metrics as well
          echo "${last_result}" | grep '<metric '
          echo "  </result>"
      else
          last_script_name=$(echo "${last_result}" |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}')
          last_script_reason=$(echo "${last_result}" | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}')
          my_reason="     Validation failed in ${last_script_name}. ${last_script_reason}" "${last_script_name}"
          #printf "$fail_result" "ERROR" "$(date --date=@\"${glidein_end_time}\" +%Y-%m-%dT%H:%M:%S%:z)" "${my_reason}"
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
          #printf "$correct_result" "OK" "No detail. Could not find source XML file."
          echo "    <status>OK</status>"
      else
          #printf "$fail_result" "ERROR" "No detail. Could not find source XML file." "$(date --date=@\"${glidein_end_time}\" +%Y-%m-%dT%H:%M:%S%:z)" "Unknown" "No detail. Could not find source XML file."
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
# Function used to convert base xml to simple xml
# Arguments:
#   1: final result
# Global:
#   final_result
basexml2simplexml() {
  final_result="$1"
  #env="    <env name=\"%s\">%s</env>"
  # augment with node info
  echo "${final_result}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<operatingenvironment>/{fr=0;}'
  #printf "$env" "client_name" "${client_name}"
  #printf "$env" "client_group" "${client_group}"
  #printf "$env" "user" "$(id -un)"
  #printf "$env" "arch" "$(uname -m)"
  echo "    <env name=\"client_name\">${client_name}</env>"
  echo "    <env name=\"client_group\">${client_group}</env>"
  echo "    <env name=\"user\">$(id -un)</env>"
  echo "    <env name=\"arch\">$(uname -m)</env>"
  if [ -e '/etc/redhat-release' ]; then
      #printf "$env" "os" "$(cat /etc/redhat-release)" 
      echo "    <env name=\"os\">$(cat /etc/redhat-release)</env>"
  fi
  #printf "$env" "hostname" "$(uname -n)"
  echo "    <env name=\"hostname\">$(uname -n)</env>"
  echo "${final_result}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'
}

################################
# Function used to convert simple xml to long xml
# Arguments:
#   1: simple final result
#   2: global result
# Global:
#   final_result_simple
#   global_result
#   content
simplexml2longxml() {
  final_result_simple="$1"
  global_result="$2"
  #env="    <env name=\"%s\">%s</env>"
  #subtestlist = "  <subtestlist>
  #                   <OSGTestResults>
  #                     %s
  #                   </OSGTestResults>'
  #                  </subtestlist>"
  echo "${final_result_simple}" | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<OSGTestResult /{fr=0;}'
  if [ "${global_result}" != "" ]; then
      # subtests first, so it is more readable, when tailing
      content = "${global_result}" | awk '{print "      " $0}'
      #printf "$subtestlist" "$content"
      echo '  <subtestlist>'
      echo '    <OSGTestResults>'
      echo "${global_result}" | awk '{print "      " $0}'
      echo '    </OSGTestResults>'
      echo '  </subtestlist>'
  fi
  echo "${final_result_simple}" | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<OSGTestResult /{fr=1;}/<operatingenvironment>/{fr=0;}'
  #printf "$env" "glidein_factory" "${glidein_factory}"
  #printf "$env" "glidein_name" "${glidein_name}"
  #printf "$env" "glidein_entry" "${glidein_entry}"
  #printf "$env" "condorg_cluster" "${condorg_cluster}"
  #printf "$env" "condorg_subcluster" "${condorg_subcluster}"
  #printf "$env" "glidein_credential_id" "${glidein_cred_id}"
  #printf "$env" "condorg_schedd" "${condorg_schedd}"
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
# Function used to create an xml file structure
# Arguments:
#   @: tags, options, values
# Global:
#   xml
#   end_xml
# Returns:
#   xml
create_xml(){
    xml="<?xml version=\"1.0\"?>"
    endxml=""
    until [ $# -lt 1 ]
    do
        case "$1" in
            OSG)  xml+="<OSGTestResult id=\"$2\" version=\"4.3.1\">"
                    if [ $3 == "{" ]; then
                        endxml="</OSGTestResult>"+$endxml
                        shift 1
                    else
                        xml+="</OSGTestResult>"
                    fi
                    shift 2;;
            OSGShort)    xml+="<OSGTestResult>"
                    if [ $2 == "{" ]; then
                        endxml="</OSGTestResult>"+$endxml
                        shift 1
                    else
                        xml+="</OSGTestResult>"
                    fi
                    shift 1;;
            operatingenvironment)    xml += "<operatingenvironment>"
                    if [ $2 == "{" ]; then
                        endxml="</operatingenvironment>"+$endxml
                        shift 1
                    else
                        xml+="</operatingenvironment>"
                    fi
                    shift 1;;
            env)    xml+="<env name=\"$2\">$3</env>"
                shift 3;;
            test)   xml+="<test>"
                    if [ $2 == "{" ]; then
                        endxml="</test>"+$endxml
                        shift 1
                    else
                        xml+="</test>"
                    fi
                    shift 1;;
            cmd)    xml+="<cmd>$2</cmd>"
                shift 2;;
            tStart)    xml+="<tStart>$2</tStart>"
                            shift 2;;
            tEnd)      xml+="<tEnd>$2</tEnd>"
                shift 2;;
            result)   xml+="<result>"
                    if [ $2 == "{" ]; then
                        endxml="</result>"+$endxml
                        shift 1
                    else
                        xml+="</result>"
                    fi
                    shift 1;;
            status)     xml+="<status>$2</status>"
                        shift 2;;
            metric)     xml+="<metric name=\"$2\" ts=\"$3)\" uri=\"local\">$4</metric>"
                        shift 4;;
            detail)     xml+="<detail>$2</detail>"
                        shift 2;;
            "}")          output=$(echo $endxml | cut -d'>' -f 1 | awk '{print $1">"}')
                        xml+=$output
                        endxml=$(echo $endxml | cut -d'<' -f 3 | awk '{print "<"$1}')
                        shift 1;;
            *)  echo "not available";
              shift 1;;
        esac
    done
    echo "$xml"
}
