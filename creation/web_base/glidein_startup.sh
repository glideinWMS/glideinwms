#!/bin/bash
#
# Project:
#   glideinWMS
#
# File Version: 
#

export LANG=C

function on_die {
        echo "Received kill signal... shutting down child processes" 1>&2
        ON_DIE=1
        kill %1
}

function ignore_signal {
        echo "Ignoring SIGHUP signal... Use SIGTERM or SIGINT to kill processes" 1>&2
}

function warn {
 echo `date` $@ 1>&2
}

function usage {
    echo "Usage: glidein_startup.sh <options>"
    echo "where <options> is:"
    echo "  -factory <name>             : name of this factory"
    echo "  -name <name>                : name of this glidein"
    echo "  -entry <name>               : name of this glidein entry"
    echo "  -clientname <name>          : name of the requesting client"
    echo "  -clientgroup <name>         : group name of the requesting client"
    echo "  -web <baseURL>              : base URL from where to fetch"
    echo "  -proxy <proxyURL>           : URL of the local proxy"
    echo "  -dir <dirID>                : directory ID (supports ., Condor, CONDOR, OSG, TMPDIR, TERAGRID)"
    echo "  -sign <sign>                : signature of the signature file"
    echo "  -signtype <id>              : type of signature (only sha1 supported for now)"
    echo "  -signentry <sign>           : signature of the entry signature file"
    echo "  -cluster <ClusterID>        : condorG ClusterId"
    echo "  -subcluster <ProcID>        : condorG ProcId"
    echo "  -schedd <name>              : condorG Schedd Name"
    echo "  -descript <fname>           : description file name"
    echo "  -descriptentry <fname>      : description file name for entry"
    echo "  -clientweb <baseURL>        : base URL from where to fetch client files"
    echo "  -clientwebgroup <baseURL>   : base URL from where to fetch client group files"
    echo "  -ciientsign <sign>          : signature of the client signature file"
    echo "  -clientsigntype <id>        : type of client signature (only sha1 supported for now)"
    echo "  -clientsigngroup <sign>     : signature of the client group signature file"
    echo "  -clientdescript <fname>     : client description file name"
    echo "  -clientdescriptgroup <fname>: client description file name for group"
    echo "  -v <id>                     : operation mode (std, nodebug, fast, check supported)"
    echo "  -param_* <arg>              : user specified parameters"
    exit 1
}


# params will contain the full list of parameters
# -param_XXX YYY will become "XXX YYY"
params=""

while [ $# -gt 0 ]
do case "$1" in
    -factory)    glidein_factory="$2";;
    -name)       glidein_name="$2";;
    -entry)      glidein_entry="$2";;
    -clientname) client_name="$2";;
    -clientgroup) client_group="$2";;
    -web)        repository_url="$2";;
    -proxy)      proxy_url="$2";;
    -dir)        work_dir="$2";;
    -sign)       sign_id="$2";;
    -signtype)   sign_type="$2";;
    -signentry)  sign_entry_id="$2";;
    -cluster)    condorg_cluster="$2";;
    -subcluster) condorg_subcluster="$2";;
    -schedd)     condorg_schedd="$2";;
    -descript)   descript_file="$2";;
    -descriptentry)   descript_entry_file="$2";;
    -clientweb)             client_repository_url="$2";;
    -clientwebgroup)        client_repository_group_url="$2";;
    -clientsign)            client_sign_id="$2";;
    -clientsigntype)        client_sign_type="$2";;
    -clientsigngroup)       client_sign_group_id="$2";;
    -clientdescript)        client_descript_file="$2";;
    -clientdescriptgroup)   client_descript_group_file="$2";;
    -v)          operation_mode="$2";;
    -param_*)    params="$params `echo $1 | awk '{print substr($0,8)}'` $2";;
    *)  (warn "Unknown option $1"; usage) 1>&2; exit 1
esac
shift
shift
done

####################################
# Cleaup, print out message and exit
work_dir_created=0
function glidein_exit {
  if [ $1 -ne 0 ]; then
    if [ $1 -ne 99 ]; then
      sleep $sleep_time 
      # wait a bit in case of error, to reduce lost glideins
      # note: exit code 99 means DAEMON_SHUTDOWN encountered
      # This should be considered a normal shutdown
    fi
  fi
  cd "$start_dir"
  if [ "$work_dir_created" -eq "1" ]; then
    rm -fR "$work_dir"
  fi

  glidein_end_time=`date +%s`
  let total_time=$glidein_end_time-$startup_time
  echo "=== Glidein ending `date` ($glidein_end_time) with code $1 after $total_time ==="
 
  exit $1
}

# Create a script that defines add_config_line
#   and add_condor_vars_line
# This way other depending scripts can use it
function create_add_config_line {
    cat > "$1" << EOF

function warn {
 echo \`date\` \$@ 1>&2
}

###################################
# Add a line to the config file
# Arg: line to add, first element is the id
# Uses global variablr glidein_config
function add_config_line {
    rm -f \${glidein_config}.old #just in case one was there
    mv \$glidein_config \${glidein_config}.old
    if [ \$? -ne 0 ]; then
        warn "Error renaming \$glidein_config into \${glidein_config}.old"
        exit 1
    fi
    grep -v "^\$1 " \${glidein_config}.old > \$glidein_config
    echo "\$@" >> \$glidein_config
    rm -f \${glidein_config}.old
}

####################################
# Add a line to the condor_vars file
# Arg: line to add, first element is the id
# Uses global variablr condor_vars_file
function add_condor_vars_line {
    id=\$1

    rm -f \${condor_vars_file}.old #just in case one was there
    mv \$condor_vars_file \${condor_vars_file}.old
    if [ \$? -ne 0 ]; then
        warn "Error renaming \$condor_vars_file into \${condor_vars_file}.old"
        exit 1
    fi
    grep -v "^\$id\b" \${condor_vars_file}.old > \$condor_vars_file
    echo "\$@" >> \$condor_vars_file
    rm -f \${condor_vars_file}.old
}
EOF
}

# Create a script that defines various id based functions 
# This way other depending scripts can use it
function create_get_id_selectors {
    cat > "$1" << EOF
############################################
# Get entry/client/group work dir
# Arg: type (main/entry/client/client_group)
function get_work_dir {
    if [ "\$1" == "main" ]; then
        grep "^GLIDEIN_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^GLIDEIN_ENTRY_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_GROUP_WORK_DIR " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_work_dir] Invalid id: \$1" 1>&2
    return 1
}

################################################
# Get entry/client/group description file name
# Arg: type (main/entry/client/client_group)
function get_descript_file {
    if [ "\$1" == "main" ]; then
        grep "^DESCRIPTION_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^DESCRIPTION_ENTRY_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_DESCRIPTION_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_DESCRIPTION_GROUP_FILE " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_descript_file] Invalid id: \$1" 1>&2
    return 1
}

############################################
# Get entry/client/group signature
# Arg: type (main/entry/client/client_group)
function get_signature {
    if [ "\$1" == "main" ]; then
        grep "^GLIDEIN_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "entry" ]; then
        grep "^GLIDEIN_Entry_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client" ]; then
        grep "^GLIDECLIENT_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    elif [ "\$1" == "client_group" ]; then
        grep "^GLIDECLIENT_Group_Signature " \${glidein_config} | awk '{print \$2}'
        return \$?
    fi
    echo "[get_signature] Invalid id: \$1" 1>&2
    return 1
}

############################################
# Get entry/client/group prefix
# Arg: type (main/entry/client/client_group)
function get_prefix {
    if [ "\$1" == "main" ]; then
        echo ""
    elif [ "\$1" == "entry" ]; then
        echo "ENTRY_"
    elif [ "\$1" == "client" ]; then
        echo "GLIDECLIENT_"
    elif [ "\$1" == "client_group" ]; then
        echo "GLIDECLIENT_GROUP_"
    else
        echo "[get_prefix] Invalid id: \$1" 1>&2
        return 1
    fi
}

EOF
}

###################################
# Put parameters into the config file
function params2file {
    param_list=""

    while [ $# -gt 0 ]
    do
       pfval=`echo "$2" | sed\
 -e 's/\.nbsp,/ /g'\
 -e 's/\.semicolon,/;/g'\
 -e 's/\.colon,/:/g'\
 -e 's/\.tilde,/~/g'\
 -e 's/\.not,/!/g'\
 -e 's/\.question,/?/g'\
 -e 's/\.star,/*/g'\
 -e 's/\.dollar,/$/g'\
 -e 's/\.comment,/#/g'\
 -e 's/\.sclose,/]/g'\
 -e 's/\.sopen,/[/g'\
 -e 's/\.gclose,/}/g'\
 -e 's/\.gopen,/{/g'\
 -e 's/\.close,/)/g'\
 -e 's/\.open,/(/g'\
 -e 's/\.gt,/>/g'\
 -e 's/\.lt,/</g'\
 -e 's/\.minus,/-/g'\
 -e 's/\.plus,/+/g'\
 -e 's/\.eq,/=/g'\
 -e "s/\.singquot,/'/g"\
 -e 's/\.quot,/"/g'\
 -e 's/\.fork,/\`/g'\
 -e 's/\.pipe,/|/g'\
 -e 's/\.backslash,/\\\/g'\
 -e 's/\.amp,/\&/g'\
 -e 's/\.comma,/,/g'\
 -e 's/\.dot,/./g'`
	add_config_line "$1 $pfval"
        if [ $? -ne 0 ]; then
	    glidein_exit 1
	fi
	if [ -z "$param_list" ]; then
	    param_list="$1"
	else
	    param_list="${param_list},$1"
	fi
	shift;shift
    done
    echo "PARAM_LIST ${param_list}"
    return 0
}


################
# Parse arguments
set_debug=1
sleep_time=1199
if [ "$operation_mode" == "nodebug" ]; then
 set_debug=0
elif [ "$operation_mode" == "fast" ]; then
 sleep_time=150
 set_debug=1
elif [ "$operation_mode" == "check" ]; then
 sleep_time=150
 set_debug=2
fi
 
if [ -z "$descript_file" ]; then
    warn "Missing descript fname." 1>&2
    usage
fi

if [ -z "$descript_entry_file" ]; then
    warn "Missing descript fname for entry." 1>&2
    usage
fi

if [ -z "$glidein_name" ]; then
    warn "Missing gliden name." 1>&2
    usage
fi

if [ -z "$glidein_entry" ]; then
    warn "Missing glidein entry name." 1>&2
    usage
fi


if [ -z "$repository_url" ]; then
    warn "Missing Web URL." 1>&2
    usage
fi

repository_entry_url="${repository_url}/entry_${glidein_entry}"

if [ -z "$proxy_url" ]; then
  proxy_url="None"
fi

if [ "$proxy_url" == "OSG" ]; then
  if [ -z "$OSG_SQUID_LOCATION" ]; then
     # if OSG does not define a Squid, then don't use any
     proxy_url="None"
     warn "OSG_SQUID_LOCATION undefined, not using any Squid URL" 1>&2
  else
     proxy_url=`echo $OSG_SQUID_LOCATION |awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}'`
  fi
fi

if [ -z "$sign_id" ]; then
    warn "Missing signature." 1>&2
    usage
fi

if [ -z "$sign_entry_id" ]; then
    warn "Missing entry signature." 1>&2
    usage
fi

if [ -z "$sign_type" ]; then
    sign_type="sha1"
fi

if [ "$sign_type" == "sha1" ]; then
    sign_sha1="$sign_id"
    sign_entry_sha1="$sign_entry_id"
else
    warn "Unsupported signtype $sign_type found." 1>&2
    usage
fi
    
if [ -n "$client_repository_url" ]; then
  # client data is optional, user url as a switch
  if [ -z "$client_sign_type" ]; then
      client_sign_type="sha1"
  fi

  if [ "$client_sign_type" == "sha1" ]; then
    client_sign_sha1="$client_sign_id"
  else
    warn "Unsupported clientsigntype $client_sign_type found." 1>&2
    usage
  fi
    
  if [ -z "$client_descript_file" ]; then
    warn "Missing client descript fname." 1>&2
    usage
  fi

  if [ -n "$client_repository_group_url" ]; then
      # client group data is optional, user url as a switch
      if [ -z '$client_group' ]; then
	  warn "Missing client group name." 1>&2
	  usage
      fi

      if [ -z "$client_descript_group_file" ]; then
	  warn "Missing client descript fname for group." 1>&2
	  usage
      fi

      if [ "$client_sign_type" == "sha1" ]; then
	  client_sign_group_sha1="$client_sign_group_id"
      else
	  warn "Unsupported clientsigntype $client_sign_type found." 1>&2
	  usage
      fi
  fi
fi

startup_time=`date +%s`
echo "Starting glidein_startup.sh at `date` ($startup_time)"
echo "debug_mode        = '$operation_mode'"
echo "condorg_cluster   = '$condorg_cluster'"
echo "condorg_subcluster= '$condorg_subcluster'"
echo "condorg_schedd    = '$condorg_schedd'"
echo "glidein_factory   = '$glidein_factory'"
echo "glidein_name      = '$glidein_name'"
echo "glidein_entry     = '$glidein_entry'"
if [ -n '$client_name' ]; then
    # client name not required as it is not used for anything but debug info
    echo "client_name       = '$client_name'"
fi
if [ -n '$client_group' ]; then
    echo "client_group       = '$client_group'"
fi
echo "work_dir          = '$work_dir'"
echo "web_dir           = '$repository_url'"
echo "sign_type         = '$sign_type'"
echo "proxy_url         = '$proxy_url'"
echo "descript_fname    = '$descript_file'"
echo "descript_entry_fname = '$descript_entry_file'"
echo "sign_id           = '$sign_id'"
echo "sign_entry_id     = '$sign_entry_id'"
if [ -n "$client_repository_url" ]; then
    echo "client_web_dir              = '$client_repository_url'"
    echo "client_descript_fname       = '$client_descript_file'"
    echo "client_sign_type            = '$client_sign_type'"
    echo "client_sign_id              = '$client_sign_id'"
    if [ -n "$client_repository_group_url" ]; then
	echo "client_web_group_dir        = '$client_repository_group_url'"
	echo "client_descript_group_fname = '$client_descript_group_file'"
	echo "client_sign_group_id        = '$client_sign_group_id'"
    fi
fi
echo
echo "Running on `uname -n`"
echo "System: `uname -a`"
if [ -e '/etc/redhat-release' ]; then
 echo "Release: `cat /etc/redhat-release 2>&1`"
fi
echo "As: `id`"
echo "PID: $$"
echo

if [ $set_debug -eq 1 ] || [ $set_debug -eq 2 ]; then
  echo "------- Initial environment ---------------"  1>&2
  env 1>&2
  echo "------- =================== ---------------" 1>&2
fi

########################################
# make sure nobody else can write my files
# In the Grid world I cannot trust anybody
umask 0022
if [ $? -ne 0 ]; then
    warn "Failed in umask 0022" 1>&2
    glidein_exit 1
fi

########################################
# Setup OSG and/or Globus
if [ -r "$OSG_GRID/setup.sh" ]; then
    . "$OSG_GRID/setup.sh"
else
  if [ -r "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh" ]; then
    . "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh"
  fi
fi

if [ -z "$GLOBUS_PATH" ]; then
  if [ -z "$GLOBUS_LOCATION" ]; then
    # if GLOBUS_LOCATION not defined, try to guess it
    if [ -r "/opt/globus/etc/globus-user-env.sh" ]; then
       GLOBUS_LOCATION=/opt/globus
    elif  [ -r "/osgroot/osgcore/globus/etc/globus-user-env.sh" ]; then
       GLOBUS_LOCATION=/osgroot/osgcore/globus
    else
       warn "GLOBUS_LOCATION not defined and could not guess it." 1>&2
       warn "Looked in:" 1>&2
       warn ' /opt/globus/etc/globus-user-env.sh' 1>&2
       warn ' /osgroot/osgcore/globus/etc/globus-user-env.sh' 1>&2
       warn 'Continuing like nothing happened' 1>&2
    fi
  fi

  if [ -r "$GLOBUS_LOCATION/etc/globus-user-env.sh" ]; then
    . "$GLOBUS_LOCATION/etc/globus-user-env.sh"
  else
    warn "GLOBUS_PATH not defined and $GLOBUS_LOCATION/etc/globus-user-env.sh does not exist." 1>&2
    warn 'Continuing like nothing happened' 1>&2
  fi
fi

########################################
# prepare and move to the work directory
if [ "$work_dir" == "Condor" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "CONDOR" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "OSG" ]; then
    work_dir="$OSG_WN_TMP"
elif [ "$work_dir" == "TMPDIR" ]; then
    work_dir="$TMPDIR"
elif [ "$work_dir" == "TERAGRID" ]; then
    work_dir="$TG_NODE_SCRATCH"
elif [ "$work_dir" == "." ]; then
    work_dir=`pwd`
elif [ -z "$work_dir" ]; then
    work_dir=`pwd`
fi

if [ -z "$work_dir" ]; then
    warn "Startup dir is empty." 1>&2
    glidein_exit 1
fi

if [ -e "$work_dir" ]; then
    echo >/dev/null
else
    warn "Startup dir $work_dir does not exist." 1>&2
    glidein_exit 1
fi

start_dir=`pwd`
echo "Started in $start_dir"

def_work_dir="$work_dir/glide_XXXXXX"
work_dir=`mktemp -d "$def_work_dir"`
if [ $? -ne 0 ]; then
    warn "Cannot create temp '$def_work_dir'" 1>&2
    glidein_exit 1
else
    cd "$work_dir"
    if [ $? -ne 0 ]; then
	warn "Dir '$work_dir' was created but I cannot cd into it." 1>&2
	glidein_exit 1
    else
	echo "Running in $work_dir"
    fi
fi
work_dir_created=1

# mktemp makes it user readable by definition (ignores umask)
chmod a+rx "$work_dir"
if [ $? -ne 0 ]; then
    warn "Failed chmod '$work_dir'" 1>&2
    glidein_exit 1
fi

glide_tmp_dir="${work_dir}/tmp"
mkdir "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$glide_tmp_dir'" 1>&2
    glidein_exit 1
fi
# the tmpdir should be world readable
# This way it will work even if the user spawned by the glidein is different
# than the glidein user
chmod a+rwx "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Failed chmod '$glide_tmp_dir'" 1>&2
    glidein_exit 1
fi
# prevent others to remove or rename a file in tmp
chmod o+t "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Failed special chmod '$glide_tmp_dir'" 1>&2
    glidein_exit 1
fi

short_main_dir=main
main_dir="${work_dir}/${short_main_dir}"
mkdir "$main_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$main_dir'" 1>&2
    glidein_exit 1
fi

short_entry_dir=entry_${glidein_entry}
entry_dir="${work_dir}/${short_entry_dir}"
mkdir "$entry_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$entry_dir'" 1>&2
    glidein_exit 1
fi

if [ -n "$client_repository_url" ]; then
    short_client_dir=client
    client_dir="${work_dir}/${short_client_dir}"
    mkdir "$client_dir"
    if [ $? -ne 0 ]; then
	warn "Cannot create '$client_dir'" 1>&2
	glidein_exit 1
    fi

    if [ -n "$client_repository_group_url" ]; then
	short_client_group_dir=client_group_${client_group}
	client_group_dir="${work_dir}/${short_client_group_dir}"
	mkdir "$client_group_dir"
	if [ $? -ne 0 ]; then
	    warn "Cannot create '$client_group_dir'" 1>&2
	    glidein_exit 1
	fi
    fi
fi

create_add_config_line add_config_line.source
source add_config_line.source

create_get_id_selectors get_id_selectors.source
source get_id_selectors.source

wrapper_list="$PWD/wrapper_list.lst"
touch $wrapper_list

# create glidein_config
glidein_config="$PWD/glidein_config"
echo > glidein_config
echo "# --- glidein_startup vals ---" >> glidein_config
echo "GLIDEIN_Factory $glidein_factory" >> glidein_config
echo "GLIDEIN_Name $glidein_name" >> glidein_config
echo "GLIDEIN_Entry_Name $glidein_entry" >> glidein_config
if [ -n '$client_name' ]; then
    # client name not required as it is not used for anything but debug info
    echo "GLIDECLIENT_Name $client_name" >> glidein_config
fi
if [ -n '$client_group' ]; then
    # client group not required as it is not used for anything but debug info
    echo "GLIDECLIENT_Group $client_group" >> glidein_config
fi
echo "CONDORG_CLUSTER $condorg_cluster" >> glidein_config
echo "CONDORG_SUBCLUSTER $condorg_subcluster" >> glidein_config
echo "CONDORG_SCHEDD $condorg_schedd" >> glidein_config
echo "DEBUG_MODE $set_debug" >> glidein_config
echo "GLIDEIN_WORK_DIR $main_dir" >> glidein_config
echo "GLIDEIN_ENTRY_WORK_DIR $entry_dir" >> glidein_config
echo "TMP_DIR $glide_tmp_dir" >> glidein_config
echo "PROXY_URL $proxy_url" >> glidein_config
echo "DESCRIPTION_FILE $descript_file" >> glidein_config
echo "DESCRIPTION_ENTRY_FILE $descript_entry_file" >> glidein_config
echo "GLIDEIN_Signature $sign_id" >> glidein_config
echo "GLIDEIN_Entry_Signature $sign_entry_id" >> glidein_config
if [ -n "$client_repository_url" ]; then
    echo "GLIDECLIENT_WORK_DIR $client_dir" >> glidein_config
    echo "GLIDECLIENT_DESCRIPTION_FILE $client_descript_file" >> glidein_config
    echo "GLIDECLIENT_Signature $client_sign_id" >> glidein_config
    if [ -n "$client_repository_group_url" ]; then
	echo "GLIDECLIENT_GROUP_WORK_DIR $client_group_dir" >> glidein_config
	echo "GLIDECLIENT_DESCRIPTION_GROUP_FILE $client_descript_group_file" >> glidein_config
	echo "GLIDECLIENT_Group_Signature $client_sign_group_id" >> glidein_config
    fi
fi
echo "ADD_CONFIG_LINE_SOURCE $PWD/add_config_line.source" >> glidein_config
echo "GET_ID_SELECTORS_SOURCE $PWD/get_id_selectors.source" >> glidein_config
echo "WRAPPER_LIST $wrapper_list" >> glidein_config
echo "# --- User Parameters ---" >> glidein_config
params2file $params

###################################
# Find out what kind of wget I have

wget_nocache_flag=""
wget --help |grep -q "\-\-no-cache "
if [ $? -eq 0 ]; then
  wget_nocache_flag="--no-cache"
else
  wget --help |grep -q "\-\-cache="
  if [ $? -eq 0 ]; then
    wget_nocache_flag="--cache=off"
  else
    warn "Unknown kind of wget, cannot disable caching" 1>&2
  fi
fi

############################################
# get the proper descript file based on id
# Arg: type (main/entry/client/client_group)
function get_repository_url {
    if [ "$1" == "main" ]; then
	echo $repository_url
    elif [ "$1" == "entry" ]; then
	echo $repository_entry_url
    elif [ "$1" == "client" ]; then
	echo $client_repository_url
    elif [ "$1" == "client_group" ]; then
	echo $client_repository_group_url
    else
	echo "[get_repository_url] Invalid id: $1" 1>&2
	return 1
    fi
}

#####################
# Check signature
function check_file_signature {
    cfs_id="$1"
    cfs_fname="$2"

    cfs_work_dir=`get_work_dir $cfs_id`

    cfs_desc_fname="${cfs_work_dir}/$cfs_fname"
    cfs_signature="${cfs_work_dir}/signature.sha1"

    if [ $check_signature -gt 0 ]; then # check_signature is global for simplicity
	tmp_signname="${cfs_signature}_$$_`date +%s`_$RANDOM"
	grep " $cfs_fname$" "$cfs_signature" > $tmp_signname
	if [ $? -ne 0 ]; then
	    rm -f $tmp_signname
	    echo "No signature for $cfs_desc_fname." 1>&2
	else
	    (cd "$cfs_work_dir" && sha1sum -c "$tmp_signname") 1>&2
	    cfs_rc=$?
	    if [ $cfs_rc -ne 0 ]; then
		warn "File $cfs_desc_fname is corrupted." 1>&2
		rm -f $tmp_signname
		return 1
	    fi
	    rm -f $tmp_signname
	    echo "Signature OK for ${cfs_id}:${cfs_fname}." 1>&2
	fi
    fi
    return 0
}

#####################
# Untar support func

function get_untar_subdir {
    gus_id="$1"
    gus_fname="$2"

    gus_prefix=`get_prefix $gus_id`
    gus_config_cfg="${gus_prefix}UNTAR_CFG_FILE"

    gus_config_file=`grep "^$gus_config_cfg " glidein_config | awk '{print $2}'`
    if [ -z "$gus_config_file" ]; then
	warn "Error, cannot find '$gus_config_cfg' in glidein_config." 1>&2
	glidein_exit 1
    fi

    gus_dir=`grep -i "^$gus_fname " $gus_config_file | awk '{print $2}'`
    if [ -z "$gus_dir" ]; then
	warn "Error, untar dir for '$gus_fname' cannot be empty." 1>&2
	glidein_exit 1
    fi

    echo "$gus_dir"
    return 0
}

#####################
# Fetch a single file
function fetch_file_regular {
    fetch_file "$1" "$2" "$2" "regular" "TRUE" "FALSE"
}

function fetch_file {
    if [ $# -ne 6 ]; then
	warn "Not enough arguments in fetch_file $@" 1>&2
	glidein_exit 1
    fi

    fetch_file_try "$1" "$2" "$3" "$4" "$5" "$6"
    if [ $? -ne 0 ]; then
	glidein_exit 1
    fi
    return 0
}

function fetch_file_try {
    fft_id="$1"
    fft_target_fname="$2"
    fft_real_fname="$3"
    fft_file_type="$4"
    fft_config_check="$5"
    fft_config_out="$6"

    if [ "$fft_config_check" == "TRUE" ]; then
	# TRUE is a special case
	fft_get_ss=1
    else
	fft_get_ss=`grep -i "^$fft_config_check " glidein_config | awk '{print $2}'`
    fi

    if [ "$fft_get_ss" == "1" ]; then
       fetch_file_base "$fft_id" "$fft_target_fname" "$fft_real_fname" "$fft_file_type" "$fft_config_out"
       fft_rc=$?
    fi

    return $fft_rc
}

function fetch_file_base {
    ffb_id="$1"
    ffb_target_fname="$2"
    ffb_real_fname="$3"
    ffb_file_type="$4"
    ffb_config_out="$5"

    ffb_work_dir=`get_work_dir $ffb_id`

    ffb_repository=`get_repository_url $ffb_id`

    ffb_tmp_outname="$ffb_work_dir/$ffb_real_fname"
    ffb_outname="$ffb_work_dir/$ffb_target_fname"
    ffb_desc_fname="$ffb_work_dir/$fname"
    ffb_signature="$ffb_work_dir/signature.sha1"


    ffb_nocache_str=""
    if [ "$ffb_file_type" == "nocache" ]; then
          ffb_nocache_str="$wget_nocache_flag"
    fi

    # download file
    if [ "$proxy_url" == "None" ]; then # no Squid defined, use the defaults
		wget --user-agent="wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name" $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname"
		if [ $? -ne 0 ]; then
			warn "Failed to load file '$ffb_real_fname' from '$ffb_repository'" 1>&2
			return 1
		fi
    else  # I have a Squid
		env http_proxy=$proxy_url wget --user-agent="wget/glidein/$glidein_entry/$condorg_schedd/$condorg_cluster.$condorg_subcluster/$client_name" $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname" 
		if [ $? -ne 0 ]; then
			# if Squid fails exit, because real jobs can try to use it too
			warn "Failed to load file '$ffb_real_fname' from '$repository_url' using proxy '$proxy_url'" 1>&2
			return 1
		fi
    fi

    # check signature
    check_file_signature "$ffb_id" "$ffb_real_fname"
    if [ $? -ne 0 ]; then
      return 1
    fi

    # rename it to the correct final name, if needed
    if [ "$ffb_tmp_outname" != "$ffb_outname" ]; then
      mv "$ffb_tmp_outname" "$ffb_outname"
      if [ $? -ne 0 ]; then
        return 1
      fi
    fi

    # if executable, execute
    if [ "$ffb_file_type" == "exec" ]; then
		chmod u+x "$ffb_outname"
		if [ $? -ne 0 ]; then
			warn "Error making '$ffb_outname' executable" 1>&2
			return 1
		fi
		if [ "$ffb_id" == "main" -a "$ffb_target_fname" == "$last_script" ]; then # last_script global for simplicity
			echo "Skipping last script $last_script" 1>&2
		else
            echo "Executing $ffb_outname"
            START=`date "+%Y-%m-%dT%H:%M:%S"`
			"$ffb_outname" glidein_config "$ffb_id"
            END=`date "+%Y-%m-%dT%H:%M:%S"`
			ret=$?
            source $main_dir/xml_parse.sh
            $main_dir/xml_parse.sh  "glidein_startup.sh" "$ffb_outname" glidein_config "$ffb_id" $START $END #generating test result document
			if [ $ret -ne 0 ]; then
                echo "=== Validation error in $ffb_outname ===" 1>&2
				warn "Error running '$ffb_outname'" 1>&2
				return 1
			fi
		fi
    elif [ "$ffb_file_type" == "wrapper" ]; then
		echo "$ffb_outname" >> "$wrapper_list"
    elif [ "$ffb_file_type" == "untar" ]; then
		ffb_short_untar_dir=`get_untar_subdir "$ffb_id" "$ffb_target_fname"`
		ffb_untar_dir="${ffb_work_dir}/${ffb_short_untar_dir}"
		(mkdir "$ffb_untar_dir" && cd "$ffb_untar_dir" && tar -xmzf "$ffb_outname") 1>&2
		ret=$?
		if [ $ret -ne 0 ]; then
			warn "Error untarring '$ffb_outname'" 1>&2
			return 1
		fi
    fi

    if [ "$ffb_config_out" != "FALSE" ]; then
		ffb_prefix=`get_prefix $ffb_id`
		if [ "$ffb_file_type" == "untar" ]; then
			# when untaring the original file is less interesting than the untar dir
			add_config_line "${ffb_prefix}${ffb_config_out}" "$ffb_untar_dir"
				if [ $? -ne 0 ]; then
					glidein_exit 1
				fi
		else
			add_config_line "${ffb_prefix}${ffb_config_out}" "$ffb_outname"
			if [ $? -ne 0 ]; then
				glidein_exit 1
			fi
		fi

    fi

    return 0
}

#####################################
# Fetch descript and signature files

# disable signature check before I get the signature file itself
# check_signature is global
check_signature=0

for gs_id in main entry client client_group
do
  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no cilent_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no cilent_repository_group
	  continue
      fi
  fi

  gs_id_work_dir=`get_work_dir $gs_id`

  # Fetch description file
  gs_id_descript_file=`get_descript_file $gs_id`
  fetch_file_regular "$gs_id" "$gs_id_descript_file"
  signature_file_line=`grep "^signature " "${gs_id_work_dir}/${gs_id_descript_file}"`
  if [ $? -ne 0 ]; then
      warn "No signature in description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
  signature_file=`echo $signature_file_line|awk '{print $2}'`

  # Fetch signature file
  gs_id_signature=`get_signature $gs_id`
  fetch_file_regular "$gs_id" "$signature_file"
  echo "$gs_id_signature  ${signature_file}">"${gs_id_work_dir}/signature.sha1.test"
  (cd "${gs_id_work_dir}"&&sha1sum -c signature.sha1.test) 1>&2
  if [ $? -ne 0 ]; then
      warn "Corrupted signature file '${gs_id_work_dir}/${signature_file}'." 1>&2
      glidein_exit 1
  fi
  # for simplicity use a fixed name for signature file
  mv "${gs_id_work_dir}/${signature_file}" "${gs_id_work_dir}/signature.sha1"
done

# re-enable for everything else
check_signature=1

# Now verify the description was not tampered with
# doing it so late should be fine, since nobody should have been able
# to fake the signature file, even if it faked its name in
# the description file
for gs_id in main entry client client_group
do
  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no cilent_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no cilent_repository_group
	  continue
      fi
  fi

  gs_id_descript_file=`get_descript_file $gs_id`
  check_file_signature "$gs_id" "$gs_id_descript_file"
  if [ $? -ne 0 ]; then
      gs_id_work_dir=`get_work_dir $gs_id`
      warn "Corrupted description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
done

###################################################
# get last_script, as it is used by the fetch_file
gs_id_work_dir=`get_work_dir main`
gs_id_descript_file=`get_descript_file main`
last_script=`grep "^last_script " "${gs_id_work_dir}/$gs_id_descript_file" | awk '{print $2}'`
if [ $? -ne 0 ]; then
    warn "last_script not in description file ${gs_id_work_dir}/$gs_id_descript_file." 1>&2
    glidein_exit 1
fi


##############################
# Fetch all the other files
for gs_file_id in "main file_list" "client preentry_file_list" "client_group preentry_file_list" "client aftergroup_preentry_file_list" "entry file_list" "client file_list" "client_group file_list" "client aftergroup_file_list" "main after_file_list"
do
  gs_id=`echo $gs_file_id |awk '{print $1}'`

  if [ -z "$client_repository_url" ]; then
      if [ "$gs_id" == "client" ]; then
	  # no client file when no client_repository
	  continue
      fi
  fi
  if [ -z "$client_repository_group_url" ]; then
      if [ "$gs_id" == "client_group" ]; then
	      # no client group file when no client_repository_group
	  continue
      fi
  fi

  gs_file_list_id=`echo $gs_file_id |awk '{print $2}'`
  
  gs_id_work_dir=`get_work_dir $gs_id`
  gs_id_descript_file=`get_descript_file $gs_id`
  
  # extract list file name
  gs_file_list_line=`grep "^$gs_file_list_id " "${gs_id_work_dir}/$gs_id_descript_file"`
  if [ $? -ne 0 ]; then
      if [ -z "$client_repository_group_url" ]; then
	  if [ "${gs_file_list_id:0:11}" == "aftergroup_" ]; then
	      # afterfile_.. files optional when no client_repository_group
	      continue
	  fi
      fi
      warn "No '$gs_file_list_id' in description file ${gs_id_work_dir}/${gs_id_descript_file}." 1>&2
      glidein_exit 1
  fi
  gs_file_list=`echo $gs_file_list_line |awk '{print $2}'`

  # fetch list file
  fetch_file_regular "$gs_id" "$gs_file_list"

  # Fetch files contained in list
  while read file
    do
    if [ "${file:0:1}" != "#" ]; then
	fetch_file "$gs_id" $file
    fi
  done < "${gs_id_work_dir}/${gs_file_list}"

done

###############################
# Start the glidein main script
echo "# --- Last Script values ---" >> glidein_config
last_startup_time=`date +%s`
let validation_time=$last_startup_time-$startup_time
echo "=== Last script starting `date` ($last_startup_time) after validating for $validation_time ==="
echo
ON_DIE=0
trap 'ignore_signal' HUP
trap 'on_die' TERM
trap 'on_die' INT
gs_id_work_dir=`get_work_dir main`
"${gs_id_work_dir}/$last_script" glidein_config &
wait $!
ret=$?
if [ $ON_DIE -eq 1 ]; then
        ret=0
fi
last_startup_end_time=`date +%s`
let last_script_time=$last_startup_end_time-$last_startup_time
echo "=== Last script ended `date` ($last_startup_end_time) with code $ret after $last_script_time ==="
echo
if [ $ret -ne 0 ]; then
  if [ $ret -eq 99 ]; then
    warn "Normal DAEMON_SHUTDOWN encountered while '$last_script'" 1>&2
  else
    warn "Error running '$last_script'" 1>&2
  fi
fi

#########################
# clean up after I finish
glidein_exit $ret
