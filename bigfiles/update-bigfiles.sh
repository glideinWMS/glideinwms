#!/bin/sh

echo "Starting the big files download"
rm ./glideinwms-bigfiles-latest.tgz

# Download the latest big files
if ! wget -q https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tgz 2> /dev/null; then
  curl -s -o ./glideinwms-bigfiles-latest.tgz  https://glideinwms.fnal.gov/downloads/glideinwms-bigfiles-latest.tg 2> /dev/null
fi

if [ ! -e ./glideinwms-bigfiles-latest.tgz ]; then
  echo "Download with wget and curl failed. Could not update big files."
  exit 1
fi

echo "Files retrieved:"
tar xvzf glideinwms-bigfiles-latest.tgz
