#!/bin/bash
########################################################################
#  This script is used to create the necessary directories for schedds.
########################################################################
function logit {
  echo "$1"
}
#---------------
function logerr {
  logit "ERROR: $1";exit 1
}
#--------------
function usage {
  echo "
Usage: $PGM 

  This script uses condor_config_val to determine the necessary directories 
  for multiple secondary schedds.

  The condor_config_val script should be in your path and the CONDOR_CONFIG 
  environmental variable set correctly.
"
}
#-----------------
function validate {
  if [ "$(type condor_config_val &>/dev/null;echo $?)" != "0" ];then
    logerr "The condor_config_val script is not in your PATH and is required to do this."
  fi

  CONFIG_VAL="condor_config_val -h $(hostname -s)"
  OWNER=$($CONFIG_VAL CONDOR_IDS 2>/dev/null)
  if [ ! -n "$OWNER" ]; then
    logerr "Error determining who should own the Condor-related directories.
Either create a "condor" account, or set the CONDOR_IDS environment
variable to the valid uid.gid pair that should be used by Condor."
  fi

}
#-------------------------
function validate_attrs {
  local name=$1
  local dir=$($CONFIG_VAL  $name 2>/dev/null)
  if [ -z "$dir" ];then
    logerr "Undefined Condor attribute: $name"
  fi
}
#-------------------------
function create_dirs {
  local name=$1
  local dir=$($CONFIG_VAL $name)
  logit "  $name: $dir "
  if [  -d "$dir" ];then
    logit "  ... already exists"
  else  
    mkdir $dir;rtn=$?
    if [ "$rtn" != "0" ];then
      logerr "Permissions problem creating directory as owner: $OWNER"
    fi 
    logit "  ... created"
  fi
  chown $OWNER $dir;rtn=$?
  if [ "$rtn" != "0" ];then
    logerr "Permissions problem changing ownership to owner: $OWNER"
  fi 
  chmod 755 $dir
}
#-------------------------
function validate_all {
  for schedd in $schedds
  do
    if [ "$schedd" = "+" ];then
      continue
    fi
    logit "Validating schedd: $schedd"
    for a  in $attrs
    do
      attr=SCHEDD.$schedd.$a
      validate_attrs $attr
    done
  done
}
#-------------------------
function create_all {
  for schedd in $schedds
  do
    if [ "$schedd" = "+" ];then
      continue
    fi
    logit
    logit "Processing schedd: $schedd"
    for a  in $attrs
    do
      attr=SCHEDD.$schedd.$a
      validate_attrs $attr
      create_dirs $attr
    done
  done
}
#------------------------
#### MAIN ##############################################
PGM=$(basename $0)

validate

schedds="$($CONFIG_VAL  DC_DAEMON_LIST)"
attrs="LOCAL_DIR EXECUTE SPOOL LOCK"
#attrs=" EXECUTE SPOOL LOCK"

validate_all
create_all

exit 0

