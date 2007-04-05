#!/bin/bash

function warn {
 echo `date` $@
}

function usage {
    echo "Usage: glidein_startup.sh <options>"
    echo "where <options> is:"
    echo "  -factory <name>       : name of this factory"
    echo "  -name <name>          : name of this glidein"
    echo "  -entry <name>         : name of this glidein entry"
    echo "  -web <baseURL>        : base URL from where to fetch"
    echo "  -proxy <proxyURL>     : URL of the local proxy"
    echo "  -dir <dirID>          : directory ID (supports .,Condor, CONDOR, OSG)"
    echo "  -sign <sign>          : signature of the signature file"
    echo "  -signtype <id>        : type of signature (only sha1 supported for now)"
    echo "  -signentry <sign>     : signature of the entry signature file"
    echo "  -cluster <ClusterID>  : condorG ClusterId"
    echo "  -subcluster <ProcID>  : condorG ProcId"
    echo "  -schedd <name>        : condorG Schedd Name"
    echo "  -consts <fname>       : constants file name"
    echo "  -glidescript <fname>  : glidein startup file name"
    echo "  -v <id>               : verbosity level (std and dbg supported)"
    echo "  -param_* <arg>        : user specified parameters"
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
    -web)        repository_url="$2";;
    -proxy)      proxy_url="$2";;
    -dir)        work_dir="$2";;
    -sign)       sign_id="$2";;
    -signtype)   sign_type="$2";;
    -signentry)  sign_entry_id="$2";;
    -cluster)    condorg_cluster="$2";;
    -subcluster) condorg_subcluster="$2";;
    -schedd)     condorg_schedd="$2";;
    -consts)     consts_file="$2";;
    -glidescript)   glidescript_file="$2";;
    -v)          debug_mode="$2";;
    -param_*)    params="$params `echo $1 | awk '{print substr($0,8)}'` $2";;
    *)  warn "Unknown option $1"; usage 1>&2
esac
shift
shift
done


###################################
# Add a line to the config file
function add_config_line {
    id=$1

    rm -f glidein_config.old #just in case one was there
    mv glidein_config glidein_config.old
    if [ $? -ne 0 ]; then
	warn "Error renaming glidein_config into glidein_config.old" 1>&2
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    grep -v "^$id " glidein_config.old > glidein_config
    echo "$@" >> glidein_config
    rm -f glidein_config.old
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
 -e 's/\.start,/*/g'\
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
set_debug=0
sleep_time=300
if [ "$debug_mode" == "dbg" ]; then
 set_debug=1
 sleep_time=10
fi

if [ -z "glidein_name" ]; then
    warn "Missing gliden name!" 1>&2
    usage
fi

if [ -z "glidein_entry" ]; then
    warn "Missing glidein entry name!" 1>&2
    usage
fi


if [ -z "$repository_url" ]; then
    warn "Missing Web URL!" 1>&2
    usage
fi

if [ -z "$proxy_url" ]; then
  proxy_url="None"
fi

if [ -z "sign_id" ]; then
    warn "Missing signature!" 1>&2
    usage
fi

if [ -z "sign_entry_id" ]; then
    warn "Missing entry signature!" 1>&2
    usage
fi

if [ -z sign_type ]; then
    sign_type="sha1"
fi

if [ "$sign_type" == "sha1" ]; then
    sign_sha1="$sign_id"
    sign_entry_sha1="$sign_entry_id"
else
    warn "Unsupported signtype $sign_type found!" 1>&2
    usage
fi
    

echo "Start glidein_startup.sh"
echo "debug_mode        = '$debug_mode'"
echo "condorg_cluster   = '$condorg_cluster'"
echo "condorg_subcluster= '$condorg_subcluster'"
echo "condorg_schedd    = '$condorg_schedd'"
echo "glidein_factory   = '$glidein_factory'"
echo "glidein_name      = '$glidein_name'"
echo "glidein_entry     = '$glidein_entry'"
echo "work_dir          = '$work_dir'"
echo "web_dir           = '$repository_url'"
echo "sign_sha1         = '$sign_sha1'"
echo "proxy_url         = '$proxy_url'"
echo
echo "Running on `uname -n`"
echo "PID: $$"
echo

if [ $set_debug -eq 1 ]; then
  echo "------- Initial environment ---------------"
  env
  echo "------- =================== ---------------"
fi

########################################
# make sure nobody else can write my files
# In the Grid world I cannot trust anybody
umask 0022
if [ $? -ne 0 ]; then
    warn "Failed in umask 0022" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

########################################
# Setup OSG and/or Globus
if [ -r "$OSG_GRID/setup.sh" ]; then
    . $OSG_GRID/setup.sh
elif [ -r "$GLOBUS_LOCATION/etc/globus-user-env.sh" ]; then
    . $GLOBUS_LOCATION/etc/globus-user-env.sh
elif [ -r "/opt/globus/etc/globus-user-env.sh" ]; then
    GLOBUS_LOCATION=/opt/globus
    . $GLOBUS_LOCATION/etc/globus-user-env.sh
elif [ -r "/osgroot/osgcore/globus/etc/globus-user-env.sh" ]; then
    GLOBUS_LOCATION=/osgroot/osgcore/globus
    . $GLOBUS_LOCATION/etc/globus-user-env.sh
else
    warn "Could not find OSG and/or Globus!" 1>&2
    warn "Looked in:" 1>&2
    warn ' $OSG_GRID/setup.sh' 1>&2
    warn ' $GLOBUS_LOCATION/etc/globus-user-env.sh' 1>&2
    warn ' /opt/globus/etc/globus-user-env.sh' 1>&2
    warn ' /osgroot/osgcore/globus/etc/globus-user-env.sh' 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

########################################
# prepare and move to the work directory
if [ "$work_dir" == "Condor" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "CONDOR" ]; then
    work_dir="$_CONDOR_SCRATCH_DIR"
elif [ "$work_dir" == "OSG" ]; then
    work_dir="$OSG_WN_TMP"
elif [ "$work_dir" == "." ]; then
    work_dir=`pwd`
elif [ -z "$work_dir" ]; then
    work_dir=`pwd`
fi

start_dir=`pwd`
echo "Started in $start_dir"

def_work_dir="$work_dir/glide_XXXXXX"
work_dir=`mktemp -d "$def_work_dir"`
if [ $? -ne 0 ]; then
    warn "Cannot create temp '$def_work_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
else
    cd "$work_dir"
    if [ $? -ne 0 ]; then
	warn "Dir '$work_dir' was created but I cannot cd into it!" 1>&2
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    else
	echo "Running in $work_dir"
    fi
fi

# mktemp makes it user readable by definition (ignores umask)
chmod a+rx "$work_dir"
if [ $? -ne 0 ]; then
    warn "Failed chmod '$work_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

glide_tmp_dir="${work_dir}/tmp"
mkdir "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$glide_tmp_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi
# the tmpdir should be world readable
# This way it will work even if the user spawned by the glidein is different
# than the glidein user
chmod a+rwx "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Failed chmod '$glide_tmp_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi
# prevent others to remove or rename a file in tmp
chmod o+t "$glide_tmp_dir"
if [ $? -ne 0 ]; then
    warn "Failed special chmod '$glide_tmp_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

entry_dir="${work_dir}/entry_${glidein_entry}"
mkdir "$entry_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$entry_dir'" 1>&2
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

# create glidein_config
echo > glidein_config
echo "# --- glidein_startup vals ---" >> glidein_config
echo "GLIDEIN_Factory $glidein_factory" >> glidein_config
echo "GLIDEIN_Name $glidein_name" >> glidein_config
echo "GLIDEIN_Entry_Name $glidein_entry" >> glidein_config
echo "CONDORG_CLUSTER $condorg_cluster" >> glidein_config
echo "CONDORG_SUBCLUSTER $condorg_subcluster" >> glidein_config
echo "CONDORG_SCHEDD $condorg_schedd" >> glidein_config
echo "DEBUG_MODE $set_debug" >> glidein_config
echo "TMP_DIR $glide_tmp_dir" >> glidein_config
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

#####################
# Fetch a single file
function fetch_file {
    fetch_file_gen "$1" "$2" ""
}

function fetch_entry_file {
    fetch_file_gen "$1" "$2" "entry"
}

function fetch_file_gen {
    fetch_file_base "$1" "$2" "$3"
    if [ $? -ne 0 ]; then
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    return 0
}

function fetch_file_base {
    fname="$1"
    avoid_cache="$2"
    fetch_entry="$3"

    if [ -z "$fetch_entry" ]; then
	ffb_repository="$repository_url"
	ffb_outname="$fname"
	ffb_signature="signature.sha1"
    else
	ffb_repository="$repository_url/entry_$glidein_entry"
	ffb_outname="$entry_dir/$fname"
	ffb_signature="$entry_dir/signature.sha1"
    fi

    if [ "$proxy_url" == "None" ]; then # no Squid defined

	wget -q  -O "$ffb_outname" "$ffb_repository/$fname"
	if [ $? -ne 0 ]; then
	    warn "Failed to load file '$fname' from '$ffb_repository'" 1>&2
	    return 1
	fi
    else  # I have a Squid
        avoid_cache_str=""
        if [ "$avoid_cache" == "nocache" ]; then
          avoid_cache_str="$wget_nocache_flag"
        fi
	env http_proxy=$proxy_url wget $avoid_cache_str -q  -O "$ffb_outname" "$ffb_repository/$fname" 
	if [ $? -ne 0 ]; then
	    # if Squid fails exit, because real jobs can try to use it too
	    warn "Failed to load file '$fname' from '$repository_url' using proxy '$proxy_url'" 1>&2
	    return 1
	fi
    fi
    if [ $check_signature -gt 0 ]; then # check_signature is global for simplicity
	tmp_signname="${ffb_signature}_$$_`date +%s`"
	grep "$fname" "$ffb_signature" > $tmp_signname
	if [ $? -ne 0 ]; then
	    rm -f $tmp_signname
	    echo "No signature for $fname."
	else
	    if [ -z "$fetch_entry" ]; then
		sha1sum -c $tmp_signname
		ffb_rc=$?
	    else
		(cd $entry_dir; sha1sum -c $tmp_signname)
		ffb_rc=$?
	    fi
	    if [ $ffb_rc -ne 0 ]; then
		warn "File $fname is corrupted!" 1>&2
		rm -f $tmp_signname
		return 1
	    fi
	    rm -f $tmp_signname
	    echo "Signature OK for $fname."
	fi
    fi
    return 0
}

###########################
# Fetch a file and untar it
function fetch_subsystem {
    fetch_subsystem_base "$1" "$2" "$3" "$4"
    if [ $? -ne 0 ]; then
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    return 0
}

# this one will return 1 on error
function fetch_subsystem_base {
    subsystem_dir="$1"
    in_tgz="$2"
    config_out="$3"
    fetch_entry="$4"

    if [ -z "$fetch_entry" ]; then
	fetch_file "$in_tgz"
	in_tgz_path="$work_dir/$in_tgz"
    else
	fetch_file_entry "$in_tgz"
	in_tgz_path="$entry_dir/$in_tgz"	
    fi
    
    ss_dir="$work_dir/${subsystem_dir}"
    mkdir "$ss_dir"
    if [ $? -ne 0 ]; then
	warn "Cannot create '$ss_dir'" 1>&2
	return 1
    fi
    cd "$ss_dir"
    if [ $? -ne 0 ]; then
	warn "Could not change to '$ss_dir'" 1>&2
	return 1
    fi

    tar -xmzf "$in_tgz_path"
    if [ $? -ne 0 ]; then
	warn "Failed untarring $in_tgz_path" 1>&2
	return 1
    fi
    rm -f "$in_tgz_path"
    cd $work_dir
    add_config_line "$config_out $ss_dir"
    return 0
}


##########################
# Fetch subsytsem only if 
# requested in config file
function try_fetch_subsystem {
    if [ $# -ne 6 ]; then
	warn "Not enough arguments in try_fetch_subsystem $@" 1>&2
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    
    fetch_entry="$1"
    config_file="$2"
    config_check="$3"
    subsystem_dir="$4"
    in_tgz="$5"
    config_out="$6"

    if [ "$config_check" == "TRUE" ]; then
	# TRUE is a special case
	get_ss=1
    else
	get_ss=`grep -i "^$config_check" $config_file | awk '{print $2}'`
    fi

    if [ "$get_ss" == "1" ]; then
       fetch_subsystem "$subsystem_dir" "$in_tgz" "$config_out" "$fetch_entry"
    fi
}

# disable signature check for the signature file itself
# check_signature is global
check_signature=0

# Fetch signature file
fetch_file "signature.sha1"
echo "$sign_sha1  signature.sha1">signature.sha1.test
sha1sum -c signature.sha1.test
if [ $? -ne 0 ]; then
    warn "Corrupted signature file!" 1>&2
    cd "$start_dir";rm -fR "$work_dir"
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

# Fetch entry signature file
fetch_entry_file "signature.sha1"
echo "$sign_entry_sha1  signature.sha1">"$entry_dir/signature.sha1.test"
(cd $entry_dir; sha1sum -c signature.sha1.test)
if [ $? -ne 0 ]; then
    warn "Corrupted entry signature file!" 1>&2
    cd "$start_dir";rm -fR "$work_dir"
    sleep $sleep_time # wait a bit, to reduce lost glideins
    exit 1
fi

# re-enable for everything else
check_signature=1

##############################
# Fetch list of support files
fetch_file "file_list.lst"
fetch_entry_file "file_list.lst"

# Fetch files
while read file
do
    fetch_file $file
done < file_list.lst

# Fetch entry files
while read file
do
    fetch_entry_file $file
done < "$entry_dir/file_list.lst"

if [ -n "$consts_file" ]; then
    echo "# --- Provided constants  ---" >> glidein_config
    # merge constants
    while read line
    do
	add_config_line $line
    done < "$consts_file"
fi

if [ -n "$entry_dir/$consts_file" ]; then
    echo "# --- Provided entry constants  ---" >> glidein_config
    # merge constants
    while read line
    do
	add_config_line $line
    done < "$entry_dir$consts_file"
fi

##############################
# Fetch list of support files
fetch_file "subsystem_list.lst"
fetch_entry_file "subsystem_list.lst"

# Try fetching the subsystems
while read subsys
do
    try_fetch_subsystem "" glidein_config $subsys
done < subsystem_list.lst

# Try fetching the entry subsystems
while read subsys
do
    try_fetch_subsystem entry glidein_config $subsys
done < subsystem_list.lst

##############################
# Fetch list of scripts
fetch_file "script_list.lst"
fetch_entry_file "script_list.lst"

echo "# --- Script values ---" >> glidein_config
# Fetch and execute scripts
while read script
do
    fetch_file "$script"
    chmod u+x "$script"
    if [ $? -ne 0 ]; then
	warn "Error making '$script' executable" 1>&2
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    if [ "$script" != "$glidescript_file" ]; then
	"./$script" glidein_config
	ret=$?
	if [ $ret -ne 0 ]; then
	    warn "Error running '$script'" 1>&2
	    cd "$start_dir";rm -fR "$work_dir"
	    sleep $sleep_time # wait a bit, to reduce lost glideins
	    exit 1
	fi
   fi # glidescript must be the last to run
done < script_list.lst

# Fetch and execute scripts
while read script
do
    fetch_file_entry "$script"
    mv "$entry_dir/$script" "$script"
    chmod u+x "$script"
    if [ $? -ne 0 ]; then
	warn "Error making '$script' executable" 1>&2
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
    "./$script" glidein_config
    ret=$?
    if [ $ret -ne 0 ]; then
	warn "Error running '$script'" 1>&2
	cd "$start_dir";rm -fR "$work_dir"
	sleep $sleep_time # wait a bit, to reduce lost glideins
	exit 1
    fi
done < script_list.lst

###############################
# Start the glidein main script
echo "# --- Glinein Script values ---" >> glidein_config
"./$glidescript_file" glidein_config
ret=$?
if [ $ret -ne 0 ]; then
  warn "Error running '$glidescript_file'" 1>&2
  cd "$start_dir";rm -fR "$work_dir"
  sleep $sleep_time # wait a bit, to reduce lost glideins
  exit 1
fi

#########################
# clean up after I finish
cd $start_dir;rm -fR $work_dir
exit $ret
