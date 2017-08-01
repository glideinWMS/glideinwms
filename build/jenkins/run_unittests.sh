#!/bin/sh

unittestlist="test_frontend.py test_frontend_element.py test_cleanupSupport.py test_condorExe.py test_encodingSupport.py test_glideFactoryDowntimeLib.py test_glideinFrontendPlugins.py test_tarSupport.py" # test_logSupport.py"


run_unittests() {
	local log_dir=$1
	local branch_name=$2

	# Delete whatever's in the unittest reports directory
	unittests_reports_dir="$WORKSPACE/unittests-reports/"
	rm -f "$unittests_reports_dir/"*.xml
	rm -f "$log_dir/${branch_name}"*.xml

	unittest_errors=0

	for file in $unittestlist; do
	    echo "TESTING ==========> $file"
	    $GLIDEINWMS_SRC/unittests/$file
	    unittest_errors=$(($unittest_errors+$?))
	done

	# Rename, copy, then delete each unitest report
	for f in $(ls "$unittests_reports_dir")
	do

	    mv "$unittests_reports_dir/$f" "$log_dir/${branch_name}_$f"
	done

	unittest_test_count=$(cat $log_dir/${branch_name}_*.xml | grep "<testsuite" | tr -s " " | cut -d " " -f5 | cut -d "=" -f2 | sed 's/\"//g' | paste -s -d+ | bc)
	unittest_failure_count=$(cat $log_dir/${branch_name}_*.xml | grep "<testsuite" | tr -s " " | cut -d " " -f3 | cut -d "=" -f2 | sed 's/\"//g' | paste -s -d+ | bc)

	export unittest_errors
	export unittest_test_count
	export unittest_failure_count
	return
}


if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then

	WORKSPACE=$(pwd)
	export GLIDEINWMS_SRC=$WORKSPACE/glideinwms

	source $GLIDEINWMS_SRC/build/jenkins/utils.sh

	setup_python_venv $WORKSPACE

	run_unittests $WORKSPACE "Unittests"

	echo "Out of $unittest_test_count tests, $unittest_errors unittests had errors and $unittest_failure_count failures."
fi
