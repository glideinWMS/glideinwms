#!/bin/sh
# must use glidein_config, it is used as global variable
glidein_config=$1

# import add_config_line function
add_config_line_source=`grep '^ADD_CONFIG_LINE_SOURCE ' $glidein_config | awk '{print $2}'`
source $add_config_line_source
# find error reporting helper script
error_gen=`grep '^ERROR_GEN_PATH ' $glidein_config | awk '{print $2}'`

add_config_line myattribute myvalue


/bin/hostname
/bin/env | /bin/sort
/bin/echo "******** test singularity"
/bin/echo "PWD: $PWD (`pwd`), process 1:`ps -p1 -ocomm=`"
/bin/echo "PID($$):`/bin/cat /proc/$$/comm`"
/bin/echo "PPID($PPID):`/bin/cat /proc/$PPID/comm`"
/bin/env | grep -i singul
/bin/echo "GWMS_SINGULARITY_REEXEC:$GWMS_SINGULARITY_REEXEC"
/bin/echo "******** condor info (which -a, condor_config)"
which -a condor_q
which -a condor_status
/bin/echo "CONDOR_CONFIG ($CONDOR_CONFIG):`[ -e "$CONDOR_CONFIG" ] && ls -l "$CONDOR_CONFIG" || echo "File not found."`"
# ls -l "$CONDOR_CONFIG"
/bin/echo "******** condor_q follows"
condor_q -l
/bin/echo "******** separating condor_status **********"
/usr/bin/condor_status -any
/bin/echo "******** separating condor_status list **********"
/usr/bin/condor_status -l
/bin/echo "******** additional condor_status from amchine_ad **********"
echo "** condor_status -ads"
condor_status -ads $_CONDOR_MACHINE_AD -af Cpus
echo "** condor_status -target"
condor_status -target $_CONDOR_MACHINE_AD -af Cpus
echo "** only Cpus (egrep, line)"
egrep "^Cpus" $_CONDOR_MACHINE_AD
echo "** only Cpus (egrep and select)"
egrep "^Cpus" $_CONDOR_MACHINE_AD | cut -f 2 -d '='
echo "**"
egrep "^Cpus " $_CONDOR_MACHINE_AD | awk '{print $3}'
cp $_CONDOR_MACHINE_AD /tmp/pp1
/bin/echo "******** cat machine ad ($_CONDOR_MACHINE_AD) **********"
#cat $_CONDOR_MACHINE_AD
if [ -z "$1" ]; then
  /bin/sleep 5
else
  /bin/sleep $1
fi
/bin/echo "Ending"

"$error_gen" -ok short_singularity_test.sh  pwd $PWD proc1 "ps -p1 -ocomm=`" pid "`/bin/cat /proc/$PPID/comm`" reexec $GWMS_SINGULARITY_REEXEC opwd $GWMS_SINGULARITY_OUTSIDE_PWD opwd_list $GWMS_SINGULARITY_OUTSIDE_PWD_LIST

