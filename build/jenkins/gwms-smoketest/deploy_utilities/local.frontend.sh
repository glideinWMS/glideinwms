cd /usr/sbin
if [ ! -d "$GWMS_DIR" ]; then
    echo you must set \$GWMS_DIR correctly to proceed
    echo exiting
    exit -1
fi
echo $GWMS_DIR exists, proceeding

/bin/rm glideinFrontendElement.pyc
/bin/rm glidecondor_addDN
ln -s $GWMS_DIR/install/glidecondor_addDN .
/bin/rm glidecondor_createSecCol                                               
ln -s $GWMS_DIR/install/glidecondor_createSecCol .
/bin/rm glidecondor_createSecSched                                  
ln -s $GWMS_DIR/install/glidecondor_createSecSched .
/bin/rm glideinFrontend
ln -s $GWMS_DIR/frontend/glideinFrontend.py glideinFrontend
/bin/rm glideinFrontendElement.py
ln -s $GWMS_DIR/frontend/glideinFrontendElement.py .
if [ -d /usr/lib/python2.6/site-packages ]; then
  cd /usr/lib/python2.6/site-packages/
  /bin/rm -rf glideinwms
  ln -s $GWMS_DIR .
elif [ -d /usr/lib/python2.7/site-packages ]; then
  cd /usr/lib/python2.7/site-packages/
  /bin/rm -rf glideinwms
  ln -s $GWMS_DIR .
fi

