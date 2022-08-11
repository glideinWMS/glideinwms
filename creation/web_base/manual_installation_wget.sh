#!/bin/bash -xv

rm utils_*
rm glidein_startup_github.sh
rm glidein_cleanup.sh
rm glidein_startup.sh
wget -O glidein_startup_github.sh https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/glidein_startup.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/glidein_cleanup.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_crypto.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_fetch.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_log.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_http.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_filesystem.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_params.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_signals.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_tarballs.sh
wget https://raw.githubusercontent.com/terranovaa/glideinwms/master/creation/web_base/utils_xml.sh
cat glidein_startup_github.sh term_file tar_utils.tar.gz > glidein_startup.sh
chmod +x glidein_startup.sh
./manual_glidein_startup --wms-collector=fermicloud532.fnal.gov --client-name=fermicloud597-fnal-gov_OSG_gWMSFrontend.main --req-name=ITB_FC_CE2b@gfactory_instance@gfactory_service --cmd-out-file=glidein_startup_wrapper --glidein-startup=./glidein_startup.sh
./glidein_startup_wrapper
