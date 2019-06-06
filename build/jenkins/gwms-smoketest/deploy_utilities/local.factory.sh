#!/bin/bash
cd /usr/sbin
if [ ! -d "$GWMS_DIR" ]; then
    echo you must set \$GWMS_DIR correctly to proceed
    echo exiting
    exit -1
fi
echo $GWMS_DIR exists, proceeding

/bin/rm clone_glidein
ln -s $GWMS_DIR/creation/clone_glidein .
/bin/rm info_glidein
ln -s $GWMS_DIR/creation/info_glidein .
/bin/rm reconfig_glidein
ln -s $GWMS_DIR/creation/reconfig_glidein .
/bin/rm glidecondor_addDN
ln -s $GWMS_DIR/install/glidecondor_addDN .
/bin/rm glidecondor_createSecCol                                               
ln -s $GWMS_DIR/install/glidecondor_createSecCol .
/bin/rm glidecondor_createSecSched                                  
ln -s $GWMS_DIR/install/glidecondor_createSecSched .
/bin/rm glideFactory.py
ln -s $GWMS_DIR/factory/glideFactory.py .
/bin/rm glideFactory.py
ln -s $GWMS_DIR/factory/glideFactory.py .
/bin/rm glideFactoryEntry.py
ln -s $GWMS_DIR/factory/glideFactoryEntry.py .
/bin/rm glideFactoryEntryGroup.py
ln -s $GWMS_DIR/factory/glideFactoryEntryGroup.py .
if [ -d /usr/lib/python2.6/site-packages ]; then
  cd /usr/lib/python2.6/site-packages/
  /bin/rm -rf glideinwms
  ln -s $GWMS_DIR .
elif [ -d /usr/lib/python2.7/site-packages ]; then
  cd /usr/lib/python2.7/site-packages/
  /bin/rm -rf glideinwms
  ln -s $GWMS_DIR .
fi

