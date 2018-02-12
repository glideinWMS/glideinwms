#!/bin/bash
mk_line(){
    echo "-------------------------------------------------------"
}
source setup.sh
touch $fact_fqdn.errs
  mk_line  >> $fact_fqdn.errs
./factory.gwms_version.sh  >> $fact_fqdn.errs
./factory.condor_version.sh  >> $fact_fqdn.errs
  mk_line  >> $fact_fqdn.errs
./factory.exceptions.sh >> $fact_fqdn.errs
./factory.gwms_errs.sh >> $fact_fqdn.errs
./factory.condor_errs.sh >> $fact_fqdn.errs
./factory.gwms_errs.sh >> $fact_fqdn.errs
  mk_line  >> $fact_fqdn.errs
./frontend.gwms_version.sh >> $vofe_fqdn.errs
./frontend.condor_version.sh >> $vofe_fqdn.errs
  mk_line >> $vofe_fqdn.errs
./frontend.exceptions.sh >> $vofe_fqdn.errs
./frontend.gwms_errs.sh >> $vofe_fqdn.errs
./frontend.condor_errs.sh >> $vofe_fqdn.errs
./frontend.gwms_errs.sh >> $vofe_fqdn.errs
unset fact_fqdn
unset vofe_fqdn

