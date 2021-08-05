#!/bin/sh

TARNAME=glideinwms-bigfiles-latest.tgz
tar --exclude='./README.txt' --exclude='./pull-bigfiles.sh' --exclude='./push-bigfiles.sh' --exclude="./$TARNAME" -cvzf "./$TARNAME" ./*

echo "New files saved to $TARNAME"

if [ "$1" = fnalu ]; then
  echo "Uploading the file to fnalu.fnal.gov:"
  scp "$TARNAME" "fnalu.fnal.gov:/web/sites/glideinwms.fnal.gov/htdocs/downloads/glideinwms-bigfiles-$(date +"%Y%m%d-%H%M").tgz"
fi
