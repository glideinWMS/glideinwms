
[ -z "$GWMS_SOURCEDIR" ] && GWMS_SOURCEDIR=../..


assert_exists() {
  assert [ -f "$1" ]
}

setupNotesEnv() {
  export TEMP_DIRECTORY="$(mktemp -d)"
}

teardownNotesEnv() {
  if [ $BATS_TEST_COMPLETED ]; then
    rm -rf $TEMP_DIRECTORY
  else
    echo "** Did not delete $TEMP_DIRECTORY, as test failed **"
  fi
}


