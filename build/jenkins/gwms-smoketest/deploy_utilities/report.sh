#!/bin/bash
mk_line(){
    echo "-------------------------------------------------------"
}
source ./setup.sh
mk_line  >  ${fact_fqdn}.factory.errs
./factory.gwms_version.sh  | tee -a ${fact_fqdn}.factory.errs
./factory.condor_version.sh  | tee -a ${fact_fqdn}.factory.errs
  mk_line  | tee -a ${fact_fqdn}.factory.errs
./factory.exceptions.sh | tee -a ${fact_fqdn}.factory.errs
  mk_line  | tee -a ${fact_fqdn}.factory.errs
./factory.gwms_errs.sh | tee -a ${fact_fqdn}.factory.errs
  mk_line  | tee -a ${fact_fqdn}.factory.errs
./factory.condor_errs.sh | tee -a ${fact_fqdn}.factory.errs
  mk_line  | tee -a ${fact_fqdn}.factory.errs
mk_line > ${vofe_fqdn}.frontend.errs
./frontend.gwms_version.sh | tee -a ${vofe_fqdn}.frontend.errs
./frontend.condor_version.sh | tee -a ${vofe_fqdn}.frontend.errs
  mk_line | tee -a ${vofe_fqdn}.frontend.errs
./frontend.exceptions.sh | tee -a ${vofe_fqdn}.frontend.errs
  mk_line | tee -a ${vofe_fqdn}.frontend.errs
./frontend.gwms_errs.sh | tee -a ${vofe_fqdn}.frontend.errs
  mk_line | tee -a ${vofe_fqdn}.frontend.errs
./frontend.condor_errs.sh | tee -a ${vofe_fqdn}.frontend.errs
unset fact_fqdn
unset vofe_fqdn

