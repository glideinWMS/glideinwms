# This is a simple file added here to test file inclusion in frontend.xml
# The content is not important

# get the glidein configuration file name, must use glidein_config, it is used as global variable
glidein_config=$1

# find error reporting helper script
error_gen=$(grep '^ERROR_GEN_PATH ' "$glidein_config" | awk '{print $2}')

echo "MMDB file1 stdout *@"
echo "MMDB file1 stderr *@" >&2

"$error_gen" -ok file1
