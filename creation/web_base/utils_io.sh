################################
# Function used to log warning statements
# Arguments:
#   @: content to warn
log_warn() {
    echo "WARN $(date)" "$@" 1>&2
}

################################
# Function used to log debug statements
# Arguments:
#   @: content to debug
log_debug() {
    echo "DEBUG $(date)" "$@" 1>&2
}

#####################
# Function used to prit a header line
# Arguments:
#   1: content of the header line
#   2 (optional): 2 if needs to write to stderr
print_header_line(){
    local content
    if [ $# -eq 1 ]; then
        content=$1
        echo "===  ${content}  ==="
    elif [ $# -eq 2 -a $2 -eq 2 ]
    then
        content=$1
        echo "===  ${content}  ===" 1>&2
    fi
}
