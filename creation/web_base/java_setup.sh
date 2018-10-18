#!/bin/bash

#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This script will setup the java parameters
#

glidein_config="$1"
tmp_fname="${glidein_config}.$$.tmp"

error_gen="`grep '^ERROR_GEN_PATH ' "$glidein_config" | cut -d ' ' -f 2-`"

condor_vars_file="`grep -i "^CONDOR_VARS_FILE " "$glidein_config" | cut -d ' ' -f 2-`"

# import add_config_line and add_condor_vars_line functions
add_config_line_source="`grep '^ADD_CONFIG_LINE_SOURCE ' "$glidein_config" | cut -d ' ' -f 2-`"
source "$add_config_line_source"

# Is java required?
need_java=`grep '^GLIDEIN_Java_Use ' "$glidein_config" | cut -d ' ' -f 2-`
if [ -z "$need_java" ]; then
    echo "`date` GLIDEIN_Java_Use not configured. Defaulting it to NEVER"
    need_java="NEVER"
fi

if [ "$need_java" == "NEVER" ]; then
  echo "`date` VO does not want to use Java"
    "$error_gen" -ok "java_setup.sh" "Java_check" "java"

  exit 0
fi

java_bin=`which java`

if [ -z "$java_bin" ]; then
   if [ "$need_java" == "REQUIRED" ]; then
        #echo "`date` VO mandates the use of Java but java not in the path." 1>&2
        STR="VO mandates the use of Java but java not in the path."
        "$error_gen" -error "java_setup.sh" "WN_Resource" "$STR" "attribute" "java"
     exit 1
   fi
   echo "`date` Java not found, but it was OPTIONAL"
    "$error_gen" -ok "java_setup.sh" "Java_check" "java"

   exit 0
fi

echo "`date` Using Java in $java_bin"

add_config_line "JAVA" "$java_bin"
add_condor_vars_line "JAVA" "C" "-" "+" "Y" "N" "-"

add_config_line "JAVA_MAXHEAP_ARGUMENT" "-Xmx"
add_condor_vars_line "JAVA_MAXHEAP_ARGUMENT" "C" "-" "+" "Y" "N" "-"

add_config_line "JAVA_CLASSPATH_ARGUMENT" "-classpath"
add_condor_vars_line "JAVA_CLASSPATH_ARGUMENT" "C" "-" "+" "Y" "N" "-"

add_config_line "JAVA_CLASSPATH_DEFAULT" '$(LIB),$(LIB)/scimark2lib.jar,.'
add_condor_vars_line "JAVA_CLASSPATH_DEFAULT" "C" "-" "+" "Y" "N" "-"

"$error_gen" -ok "java_setup.sh" "Java_check" "java"
exit 0
