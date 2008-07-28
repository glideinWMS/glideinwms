#!/bin/bash

# This script is started just before the user job
# It is referenced by the USER_JOB_WRAPPER



# Condor job wrappers must replace its own image
exec "$@"
