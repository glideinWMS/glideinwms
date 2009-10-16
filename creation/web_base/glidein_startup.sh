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
    echo "  -dir <dirID>          : directory ID (supports ., Condor, CONDOR, OSG, TMPDIR)"
    echo "  -sign <sign>          : signature of the signature file"
    echo "  -signtype <id>        : type of signature (only sha1 supported for now)"
    echo "  -signentry <sign>     : signature of the entry signature file"
    echo "  -cluster <ClusterID>  : condorG ClusterId"
    echo "  -subcluster <ProcID>  : condorG ProcId"
    echo "  -schedd <name>        : condorG Schedd Name"
    echo "  -descript <fname>     : description file name"
    echo "  -descriptentry <fname>: description file name for entry"
    echo "  -v <id>               : verbosity level (std, nodebug and fast supported)"
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
    -descript)   descript_file="$2";;
    -descriptentry)   descript_entry_file="$2";;
    -v)          debug_mode="$2";;
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
    sleep $sleep_time # wait a bit in case of error, to reduce lost glideins
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
# and create_add_condor_vars_line
# This way other depending scripts can use it
function create_add_config_line {
    cat > "$1" << EOF
###################################
# Add a line to the config file
# Arg: line to add, first element is the id
# Uses global variablr glidein_config
function add_config_line {
    id=\$1

    rm -f \${glidein_config}.old #just in case one was there
    mv \$glidein_config \${glidein_config}.old
    if [ \$? -ne 0 ]; then
        warn "Error renaming \$glidein_config into \${glidein_config}.old"
        exit 1
    fi
    grep -v "^\$id " \${glidein_config}.old > \$glidein_config
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
sleep_time=1200
if [ "$debug_mode" == "nodebug" ]; then
 set_debug=0
elif [ "$debug_mode" == "fast" ]; then
 sleep_time=150
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
    

startup_time=`date +%s`
echo "Starting glidein_startup.sh at `date` ($startup_time)"
echo "debug_mode        = '$debug_mode'"
echo "condorg_cluster   = '$condorg_cluster'"
echo "condorg_subcluster= '$condorg_subcluster'"
echo "condorg_schedd    = '$condorg_schedd'"
echo "glidein_factory   = '$glidein_factory'"
echo "glidein_name      = '$glidein_name'"
echo "glidein_entry     = '$glidein_entry'"
echo "work_dir          = '$work_dir'"
echo "web_dir           = '$repository_url'"
echo "sign_type         = '$sign_type'"
echo "proxy_url         = '$proxy_url'"
echo "descript_fname    = '$descript_file'"
echo "descript_entry_fname = '$descript_entry_file'"
echo "sign_id           = '$sign_id'"
echo "sign_entry_id     = '$sign_entry_id'"
echo
echo "Running on `uname -n`"
echo "System: `uname -a`"
if [ -e '/etc/redhat-release' ]; then
 echo "Release: `cat /etc/redhat-release 2>&1`"
fi
echo "As: `id`"
echo "PID: $$"
echo

if [ $set_debug -eq 1 ]; then
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
       glidein_exit 1
    fi
  fi

  if [ -r "$GLOBUS_LOCATION/etc/globus-user-env.sh" ]; then
    . "$GLOBUS_LOCATION/etc/globus-user-env.sh"
  else
    warn "GLOBUS_PATH not defined and $GLOBUS_LOCATION/etc/globus-user-env.sh does not exist." 1>&2
    glidein_exit 1
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

short_entry_dir=entry_${glidein_entry}
entry_dir="${work_dir}/${short_entry_dir}"
mkdir "$entry_dir"
if [ $? -ne 0 ]; then
    warn "Cannot create '$entry_dir'" 1>&2
    glidein_exit 1
fi

create_add_config_line add_config_line.source
source add_config_line.source

wrapper_list="$PWD/wrapper_list.lst"
touch $wrapper_list

# create glidein_config
glidein_config="$PWD/glidein_config"
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
echo "PROXY_URL $proxy_url" >> glidein_config
echo "DESCRIPTION_FILE $descript_file" >> glidein_config
echo "DESCRIPTION_ENTRY_FILE $descript_entry_file" >> glidein_config
echo "GLIDEIN_Signature $sign_id" >> glidein_config
echo "GLIDEIN_Entry_Signature $sign_entry_id" >> glidein_config
echo "ADD_CONFIG_LINE_SOURCE $PWD/add_config_line.source" >> glidein_config
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

#####################
# Check signature
function check_file_signature {
    cfs_entry_dir="$1"
    cfs_fname="$2"

    if [ "$cfs_entry_dir" == "main" ]; then
	cfs_desc_fname="$cfs_fname"
	cfs_signature="signature.sha1"
    else
	cfs_desc_fname="$cfs_entry_dir/$cfs_fname"
	cfs_signature="$cfs_entry_dir/signature.sha1"
    fi

    if [ $check_signature -gt 0 ]; then # check_signature is global for simplicity
	tmp_signname="${cfs_signature}_$$_`date +%s`_$RANDOM"
	grep " $cfs_fname$" "$cfs_signature" > $tmp_signname
	if [ $? -ne 0 ]; then
	    rm -f $tmp_signname
	    echo "No signature for $cfs_desc_fname." 1>&2
	else
	    if [ "$cfs_entry_dir" == "main" ]; then
		sha1sum -c "$tmp_signname" 1>&2
		cfs_rc=$?
	    else
		(cd "$cfs_entry_dir" && sha1sum -c "../$tmp_signname") 1>&2
		cfs_rc=$?
	    fi
	    if [ $cfs_rc -ne 0 ]; then
		warn "File $cfs_desc_fname is corrupted." 1>&2
		rm -f $tmp_signname
		return 1
	    fi
	    rm -f $tmp_signname
	    echo "Signature OK for $cfs_desc_fname." 1>&2
	fi
    fi
    return 0
}

#####################
# Untar support func

function get_untar_subdir {
    gus_entry_dir="$1"
    gus_fname="$2"

    if [ "$gus_entry_dir" == "main" ]; then
	gus_config_cfg="UNTAR_CFG_FILE"
    else
	gus_config_cfg="UNTAR_CFG_ENTRY_FILE"
    fi

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
    fft_entry_dir="$1"
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
       fetch_file_base "$fft_entry_dir" "$fft_target_fname" "$fft_real_fname" "$fft_file_type" "$fft_config_out"
       fft_rc=$?
    fi

    return $fft_rc
}

function fetch_file_base {
    ffb_entry_dir="$1"
    ffb_target_fname="$2"
    ffb_real_fname="$3"
    ffb_file_type="$4"
    ffb_config_out="$5"

    if [ "$ffb_entry_dir" == "main" ]; then
	ffb_repository="$repository_url"
	ffb_tmp_outname="$ffb_real_fname"
	ffb_outname="$ffb_target_fname"
	ffb_desc_fname="$fname"
	ffb_signature="signature.sha1"
    else
	ffb_repository="$repository_url/$ffb_entry_dir"
	ffb_tmp_outname="$ffb_entry_dir/$ffb_real_fname"
	ffb_outname="$ffb_entry_dir/$ffb_target_fname"
	ffb_desc_fname="$ffb_entry_dir/$fname"
	ffb_signature="$ffb_entry_dir/signature.sha1"
    fi

    ffb_nocache_str=""
    if [ "$ffb_file_type" == "nocache" ]; then
          ffb_nocache_str="$wget_nocache_flag"
    fi

    # download file
    if [ "$proxy_url" == "None" ]; then # no Squid defined, use the defaults
	wget $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname"
	if [ $? -ne 0 ]; then
	    warn "Failed to load file '$ffb_real_fname' from '$ffb_repository'" 1>&2
	    return 1
	fi
    else  # I have a Squid
	env http_proxy=$proxy_url wget  $ffb_nocache_str -q  -O "$ffb_tmp_outname" "$ffb_repository/$ffb_real_fname" 
	if [ $? -ne 0 ]; then
	    # if Squid fails exit, because real jobs can try to use it too
	    warn "Failed to load file '$ffb_real_fname' from '$repository_url' using proxy '$proxy_url'" 1>&2
	    return 1
	fi
    fi

    # check signature
    check_file_signature "$ffb_entry_dir" "$ffb_real_fname"
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
	if [ "$ffb_outname" != "$last_script" ]; then # last_script global for simplicity
            echo "Executing $ffb_outname"
	    "./$ffb_outname" glidein_config "$ffb_entry_dir"
	    ret=$?
	    if [ $ret -ne 0 ]; then
		warn "Error running '$ffb_outname'" 1>&2
		return 1
	    fi
	else
	    echo "Skipping last script $last_script" 1>&2
	fi
    elif [ "$ffb_file_type" == "wrapper" ]; then
	echo "$PWD/$ffb_outname" >> "$wrapper_list"
    elif [ "$ffb_file_type" == "untar" ]; then
	ffb_untar_dir=`get_untar_subdir "$ffb_entry_dir" "$ffb_target_fname"`
	(mkdir "$ffb_untar_dir" && cd "$ffb_untar_dir" && tar -xmzf "$work_dir/$ffb_outname") 1>&2
	ret=$?
	if [ $ret -ne 0 ]; then
	    warn "Error untarring '$ffb_outname'" 1>&2
	    return 1
	fi
    fi

    if [ "$ffb_config_out" != "FALSE" ]; then
	if [ "$ffb_file_type" == "untar" ]; then
	    # when untaring the original file is less interesting than the untar dir
	    add_config_line "$ffb_config_out" "$work_dir/$ffb_untar_dir"
	    if [ $? -ne 0 ]; then
		glidein_exit 1
	    fi
	else
	    add_config_line "$ffb_config_out" "$work_dir/$ffb_outname"
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

# Fetch description file
fetch_file_regular "main" "$descript_file"
signature_file_line=`grep "^signature " "$descript_file"`
if [ $? -ne 0 ]; then
    warn "No signature in description file." 1>&2
    glidein_exit 1
fi
signature_file=`echo $signature_file_line|awk '{print $2}'`

# Fetch signature file
fetch_file_regular "main" "$signature_file"
echo "$sign_sha1  $signature_file">signature.sha1.test
sha1sum -c signature.sha1.test 1>&2
if [ $? -ne 0 ]; then
    warn "Corrupted signature file '$signature_file'." 1>&2
    glidein_exit 1
fi
# for simplicity use a fixed name for signature file
mv "$signature_file" "signature.sha1"

# Fetch description file for entry
fetch_file_regular "$short_entry_dir" "$descript_entry_file"
signature_entry_file_line=`grep "^signature " "$entry_dir/$descript_entry_file"`
if [ $? -ne 0 ]; then
    warn "No signature in description file for entry." 1>&2
    glidein_exit 1
fi
signature_entry_file=`echo $signature_entry_file_line|awk '{print $2}'`

# Fetch entry signature file
fetch_file_regular "$short_entry_dir" "$signature_entry_file"
echo "$sign_entry_sha1  $signature_entry_file">"$entry_dir/signature.sha1.test"
(cd $entry_dir; sha1sum -c signature.sha1.test) 1>&2
if [ $? -ne 0 ]; then
    warn "Corrupted entry signature file '$signature_entry_file'." 1>&2
    glidein_exit 1
fi
# for simplicity use a fixed name for signature file
mv "$entry_dir/$signature_entry_file" "$entry_dir/signature.sha1"

# re-enable for everything else
check_signature=1

# Now verify the description was not tampered with
# doing it so late should be fine, since nobody should have been able
# to fake the signature file, even if it faked its name in
# the description file
check_file_signature "main" "$descript_file"
if [ $? -ne 0 ]; then
    warn "Corrupted description file." 1>&2
    glidein_exit 1
fi

check_file_signature "$short_entry_dir" "$descript_entry_file"
if [ $? -ne 0 ]; then
    warn "Corrupted description file for entry." 1>&2
    glidien_exit 1
fi


##############################################
# Extract other infor from the descript files
for id in file_list after_file_list last_script
do
  id_line=`grep "^$id " "$descript_file"`
  if [ $? -ne 0 ]; then
    warn "No '$id' in description file." 1>&2
    glidein_exit 1
  fi
  id_val=`echo $id_line|awk '{print $2}'`
  eval $id=$id_val
done

# Repeat for entry

for id in file_list 
do
  id_line=`grep "^$id " "$entry_dir/$descript_entry_file"`
  if [ $? -ne 0 ]; then
    warn "No '$id' in entry description file." 1>&2
    glidein_exit 1
  fi
  id_var="${id}_entry"
  id_val=`echo $id_line|awk '{print $2}'`
  eval $id_var=$id_val
done

##############################
# Fetch list of support files
fetch_file_regular "main" "$file_list"
fetch_file_regular "$short_entry_dir" "$file_list_entry"
fetch_file_regular "main" "$after_file_list"

# Fetch files
while read file
do
    if [ "${file:0:1}" != "#" ]; then
	fetch_file "main" $file
    fi
done < "$file_list"

# Fetch entry files
while read file
do
    if [ "${file:0:1}" != "#" ]; then
	fetch_file "$short_entry_dir" $file
    fi
done < "$entry_dir/$file_list_entry"

while read file
do
    if [ "${file:0:1}" != "#" ]; then
	fetch_file "main" $file
    fi
done < "$after_file_list"

###############################
# Start the glidein main script
echo "# --- Last Script values ---" >> glidein_config
last_startup_time=`date +%s`
let validation_time=$last_startup_time-$startup_time
echo "=== Last script starting `date` ($last_startup_time) after validating for $validation_time ==="
echo
"./$last_script" glidein_config
ret=$?
last_startup_end_time=`date +%s`
let last_script_time=$last_startup_end_time-$last_startup_time
echo "=== Last script ended `date` ($last_startup_end_time) with code $ret after $last_script_time ==="
echo
if [ $ret -ne 0 ]; then
  warn "Error running '$last_script'" 1>&2
  glidein_exit 1
fi

#########################
# clean up after I finish
glidein_exit $ret
