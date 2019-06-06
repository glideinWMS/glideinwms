#!/bin/sh

function help() {
    echo
    echo "usage:"
    echo 
    echo "$prog somehost.fnal.gov  module      install module on somehost.fnal.gov"
    echo "                                                  use 'create_fermicloud_vm.sh' to create "
    echo "                                                  somehost.fnal.gov on fermicloud if desired "
    echo "                                                  'module' is a subdirectory containing a puppet build"
    echo "                                                  ie osg_client jobsub_server etc"
    echo ""
    echo "$prog --help                   Print this help message and exit"
    echo
    exit 0
}
prog=`basename $0`
if [ $# -lt 2 ]; then
    help
fi
if [ "$1" = "--help" ]; then
    help
fi
export REMOTE_HOST=$1
export REMOTE_SCRIPT="$2_apply.sh"
puppet module build $2
tarpath=$(find $2 -name '*.tar.gz' -print)
tarfile=$(basename $tarpath)
scp $tarpath root@${REMOTE_HOST}:$tarfile
echo "puppet module list | grep $2" > $REMOTE_SCRIPT
echo "if [ \$? -eq 0 ]; then" >> $REMOTE_SCRIPT
echo "    puppet module uninstall $2" >> $REMOTE_SCRIPT
echo "fi" >> $REMOTE_SCRIPT
echo "puppet module install $tarfile" >>$REMOTE_SCRIPT
echo "puppet apply -e \"class { $2 : $3 }\"" >> $REMOTE_SCRIPT
echo "" >> $REMOTE_SCRIPT
scp $REMOTE_SCRIPT root@${REMOTE_HOST}:$REMOTE_SCRIPT
ssh -t root@${REMOTE_HOST} bash $REMOTE_SCRIPT
#rm $REMOTE_SCRIPT
