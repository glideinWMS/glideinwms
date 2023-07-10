#!/usr/bin/env python3
#
# Project:
#   glideinWMS
#
# File Version:
#
import argparse
import subprocess
import os
import re
import tempfile
import shutil
import warnings
import time
from datetime import datetime
import xml.etree.ElementTree as gfg
import sys
import random

parser = argparse.ArgumentParser(description="")
parser.add_argument('glidein_factory')
parser.add_argument('glidein_name')
parser.add_argument('glidein_entry')
parser.add_argument('client_name')
parser.add_argument('client_group')
parser.add_argument('repository_url')
parser.add_argument('proxy_url')
parser.add_argument('work_dir')
parser.add_argument('sign_id')
parser.add_argument('sign_type')
parser.add_argument('sign_entry_id')
parser.add_argument('condorg_cluster')
parser.add_argument('condorg_subcluster')
parser.add_argument('glidein_cred_id')
parser.add_argument('condorg_schedd')
parser.add_argument('descript_file')
parser.add_argument('descript_entry_file')
parser.add_argument('client_repository_url')
parser.add_argument('client_repository_group_url')
parser.add_argument('client_sign_id')
parser.add_argument('client_sign_type')
parser.add_argument('client_sign_group_id')
parser.add_argument('client_descript_file')
parser.add_argument('client_descript_group_file')
parser.add_argument('slots_layout')
parser.add_argument('operation_mode')
parser.add_argument('multi_glidein')
parser.add_argument('multi_glidein_restart', metavar='multi_glidein_restart [params]')
args, params = parser.parse_known_args()

def usage():
    print("Usage: glidein_startup.sh <options>")
    print("where <options> is:")
    print("  -factory <name>             : name of this factory")
    print("  -name <name>                : name of this glidein")
    print("  -entry <name>               : name of this glidein entry")
    print("  -clientname <name>          : name of the requesting client")
    print("  -clientgroup <name>         : group name of the requesting client")
    print("  -web <baseURL>              : base URL from where to fetch")
    print("  -proxy <proxyURL>           : URL of the local proxy")
    print("  -dir <dirID>                : directory ID (supports ., Condor, CONDOR, OSG, TMPDIR, AUTO)")
    print("  -sign <sign>                : signature of the signature file")
    print("  -signtype <id>              : type of signature (only sha1 supported for now)")
    print("  -signentry <sign>           : signature of the entry signature file")
    print("  -cluster <ClusterID>        : condorG ClusterId")
    print("  -subcluster <ProcID>        : condorG ProcId")
    print("  -submitcredid <CredentialID>: Credential ID of this condorG job")
    print("  -schedd <name>              : condorG Schedd Name")
    print("  -descript <fname>           : description file name")
    print("  -descriptentry <fname>      : description file name for entry")
    print("  -clientweb <baseURL>        : base URL from where to fetch client files")
    print("  -clientwebgroup <baseURL>   : base URL from where to fetch client group files")
    print("  -clientsign <sign>          : signature of the client signature file")
    print("  -clientsigntype <id>        : type of client signature (only sha1 supported for now)")
    print("  -clientsigngroup <sign>     : signature of the client group signature file")
    print("  -clientdescript <fname>     : client description file name")
    print("  -clientdescriptgroup <fname>: client description file name for group")
    print("  -slotslayout <type>         : how Condor will set up slots (fixed, partitionable)")
    print("  -v <id>                     : operation mode (std, nodebug, fast, check supported)")
    print("  -multiglidein <num>         : spawn multiple (<num>) glideins (unless also multirestart is set)")
    print("  -multirestart <num>         : started as one of multiple glideins (glidein number <num>)")
    print("  -param_* <arg>              : user specified parameters")
    sys.exit(1)

def construct_xml(result):

    x = datetime.now()
    glidein_end_time= x.strftime("%S")
    startup_time = x.strftime("%Y-%m-%dT%H:%M:%S%:z")

    ans = """
    <?xml version=\"1.0\"?> 
    <OSGTestResult id=\"glidein_startup.py\" version=\"4.3.1\"> 
        <operatingenvironment> 
            <env name=\"cwd\">""" + start_dir + """</env> 
        </operatingenvironment> 
        <test>
            <cmd> glidein_startup.py""" +  global_args + """</cmd>
            <tStart>""" + startup_time + """</tStart>
            <tEnd>""" +  x.strftime("%Y-%m-%dT%H:%M:%S%:z") + """</tEnd>
        </test>""" + result + """</OSGTestResult>
    """
    print(ans)

def extract_parent_fname(exitcode):

    if os.path.getsize('otrx_output.xml') > 0:
        # file exists and is not 0 size
        with open('otrx_output.xml', 'r') as f:
            data = f.read()
        last_result=data

        if exitcode == 0:
            print("SUCCESS")
        else:
            last_script_name= os.system( """print(""" + last_result + """ |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}'""")
            print(last_script_name)
    else:
        print("Unknown")

    
def extract_parent_xml_detail(exitcode):

    x = datetime.now()
    glidein_end_time= x.strftime("%S")

    if os.path.getsize('otrx_output.xml') > 0:
        # file exists and is not 0 size
        with open('otrx_output.xml', 'r') as f:
            data = f.read()
        last_result=data

        if exitcode == 0:
            print( "  <result>")
            print("    <status>OK</status>")
            # propagate metrics as well
            for line in last_result:
                if re.search("<metric ", line):
                    print(line)
            print("  </result>")
        else:
            last_script_name=os.system("""print(""" + last_result + """ |awk '/<OSGTestResult /{split($0,a,"id=\""); split(a[2],b,"\""); print b[1];}'""")

            last_script_reason=os.system("""print(""" + last_result + """ | awk 'BEGIN{fr=0;}/<[/]detail>/{fr=0;}{if (fr==1) print $0}/<detail>/{fr=1;}'""")
            my_reason="     Validation failed in " + last_script_name + "." + last_script_reason

            print("  <result>")
            print("    <status>ERROR</status> <metric name=\"TestID\" ts=\"" + x.strftime("%Y-%m-%dT%H:%M:%S%:z") + "\" uri=\"local\">" + last_script_name + "</metric>")
            # propagate metrics as well (will include the failure metric)
            for line in last_result:
                if re.search("<metric ", line):
                    print(line)
            print("  </result>")
            print("  <detail>" + my_reason + "</detail>")
    else:
        # create a minimal XML file, else
        print("  <result>")
        if exitcode == 0:
            print("    <status>OK</status>")
        else:
            print("    <status>ERROR</status>")
            print("    <metric name=\"failure\" ts=\"" + x.strftime("%Y-%m-%dT%H:%M:%S%:z") + "\" uri=\"local\">Unknown</metric>")
        print("  </result><detail> No detail. Could not find source XML file. </detail>")


def basexml2simplexml(final_result):

    # augment with node info
    res = os.system(final_result +  " | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<operatingenvironment>/{fr=0;}'")
    print(res)
    print("    <env name=\"client_name\">" + client_name + "</env>")
    print("    <env name=\"client_group\">" + client_group + "</env>")

    print("    <env name=\"user\">$(id -un)</env>")
    print("    <env name=\"arch\">$(uname -m)</env>")

    if os.path.isabs("/etc/redhat-release"):
        with open('/etc/redhat-release', 'r') as f:
            data = f.read()
        print("    <env name=\"os\">" + data + "</env>")
    print("    <env name=\"hostname\">$(uname -n)</env>")

    print(os.system(final_result + " | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'"))
    
def simplexml2longxml(final_result_simple, global_result):

    print(os.system(final_result_simple + " | awk 'BEGIN{fr=1;}{if (fr==1) print $0}/<OSGTestResult /{fr=0;}'"))

    if global_result != "" :
        # subtests first, so it is more readable, when tailing
        print('  <subtestlist>')
        print('    <OSGTestResults>')
        print(os.system(global_result + " | awk '{print "      " $0}'"))
        print('    </OSGTestResults>')
        print('  </subtestlist>')


    print(os.system(final_result_simple + " | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<OSGTestResult /{fr=1;}/<operatingenvironment>/{fr=0;}'"))

    print("    <env name=\"glidein_factory\">" + args.glidein_factory + "</env>")
    print("    <env name=\"glidein_name\">" + args.glidein_name + "</env>")
    print("    <env name=\"glidein_entry\">" + args.glidein_entry + "</env>")
    print("    <env name=\"condorg_cluster\">" + args.condorg_cluster + "</env>")
    print("    <env name=\"condorg_subcluster\">" + args.condorg_subcluster + "</env>")
    print("    <env name=\"glidein_credential_id\">" + args.glidein_cred_id + "</env>")
    print("    <env name=\"condorg_schedd\">" + args.condorg_schedd + "</env>")

    print(os.system(final_result_simple + " | awk 'BEGIN{fr=0;}{if (fr==1) print $0}/<operatingenvironment>/{fr=1;}'"))

def print_tail(exit_code, final_result_simple, final_result_long):
    
    x = datetime.now()
    glidein_end_time= x.strftime("%S")

    total_time= glidein_end_time - startup_time
    print("=== Glidein ending" + datetime.now() +  "(" + glidein_end_time + ") with code" + exit_code + "after" + total_time + "===")
    print("=== XML description of glidein activity ===")
    for line in final_result_simple:
                if "<cmd>" not in line:
                    print(line)
    print("=== End XML description of glidein activity ===")

    print >> sys.stderr, ""
    print >> sys.stderr, "=== Encoded XML description of glidein activity ==="
    # print("${final_result_long}" | gzip --stdout - | b64uuencode 1>&2
    print >> sys.stderr, "=== End encoded XML description of glidein activity ==="



####################################
# Cleaup, print out message and exit
work_dir_created=0
glide_local_tmp_dir_created=0


def glidien_cleanup():
    # Remove Glidein directories (work_dir, glide_local_tmp_dir)
    # 1 - exit code
    # Using GLIDEIN_DEBUG_OPTIONS, start_dir, work_dir_created, work_dir, 
    #   glide_local_tmp_dir_created, glide_local_tmp_dir
    if not os.path.isabs(start_dir):
        warnings.warn("Cannot find" + start_dir + "anymore, exiting but without cleanup")
    else:
        if GLIDEIN_DEBUG_OPTIONS == nocleanup:
            warnings.warn("Skipping cleanup, disabled via" + GLIDEIN_DEBUG_OPTIONS)
        else:
            if work_dir_created == 1:
                os.remove(work_dir)
            if glide_local_tmp_dir_created == 1:
                os.remove(glide_local_tmp_dir)

# use this for early failures, when we cannot assume we can write to disk at all
# too bad we end up with some repeated code, but difficult to do better
def early_glidein_failure(error_msg):
    
    warnings.warn(str(error_msg))

    time.sleep(sleep_time)
    # wait a bit in case of error, to reduce lost glideins
    x = datetime.now()
    glidein_end_time= x.strftime("%S")

    result="    <metric name=\"failure\" ts=\"" + x.strftime("%Y-%m-%dT%H:%M:%S%:z") + "uri=\"local\">WN_RESOURCE</metric> \n<status>ERROR</status> \n<detail>\n\t" + error_msg + "\n</detail>"

    final_result= str(construct_xml(result))
    final_result_simple= str(basexml2simplexml(final_result))

    # have no global section
    final_result_long= str(simplexml2longxml(final_result_simple, ")"))

    glidien_cleanup()

    print_tail(1, final_result_simple, final_result_long)

    sys.exit(1)


# use this one once the most basic ops have been done
def glidein_exit(exitcode):
    # Removed lines about $lock_file (lock file for whole machine) not present elsewhere

    gwms_process_scripts("$GWMS_DIR", cleanup)

    global_result=""
    if os.path.isabs(otr_outlist.list):
        with open('otr_outlist.list', 'r') as f:
            data = f.read()
        global_result = data
        os.chmod('otr_outlist.list', stat.S_IWRITE)


    ge_last_script_name= extract_parent_fname(exitcode)
    result= extract_parent_xml_detail(exitcode)
    final_result= construct_xml(result)

    # augment with node info
    final_result_simple= basexml2simplexml(final_result)

    # Create a richer version, too
    final_result_long= simplexml2longxml(final_result_simple, global_result)

    if exitcode != 0:
        report_failed = ""
        with open('glidein_config', 'r') as f:
            data = f.read()
        for line in data:
                if re.search("^GLIDEIN_Report_Failed ", line, re.IGNORECASE):
                    report_failed += line
        report_failed = "\n".join(report_failed.split(" ")[2:] )
        

        if report_failed == "":
            report_failed="NEVER"

        for line in data:
                if re.search("^GLIDEIN_Factory_Report_Failed ", line, re.IGNORECASE):
                    factory_report_failed += line
        factory_report_failed = "\n".join(factory_report_failed.split(" ")[2:] )

        

        if factory_report_failed == "":

            for line in data:
                if re.search("^GLIDEIN_Factory_Collector ", line, re.IGNORECASE):
                    factory_collector += line
            factory_collector = "\n".join(factory_collector.split(" ")[2:] )

            
            if factory_collector == "":
                # no point in enabling it if there are no collectors
                factory_report_failed="NEVER"
            else:
                factory_report_failed="ALIVEONLY"


        do_report=0
        if report_failed != "NEVER" or factory_report_failed != "NEVER" :
            do_report=1


        # wait a bit in case of error, to reduce lost glideins
        x = datetime.now()
        dl= x.strftime("%S") + sleep_time
        dlf=dl
        add_config_line("GLIDEIN_ADVERTISE_ONLY", "1")
        add_config_line("GLIDEIN_Failed", "True")
        add_config_line("GLIDEIN_EXIT_CODE", str(exitcode))
        add_config_line("GLIDEIN_ToDie", str(dl))
        add_config_line("GLIDEIN_Expire", str(dl))
        add_config_line("GLIDEIN_LAST_SCRIPT", str(ge_last_script_name))
        add_config_line("GLIDEIN_ADVERTISE_TYPE", "Retiring")

        add_config_line("GLIDEIN_FAILURE_REASON", "Glidein failed while running" + ge_last_script_name + ". Keeping node busy until" + str(dl) + " " + str(dlf) + ".")

        for line in data:
            if re.search("^CONDOR_VARS_FILE ", line, re.IGNORECASE):
                condor_vars_file += line
        condor_vars_file = "\n".join(condor_vars_file.split(" ")[2:] )

        
        if condor_vars_file != "":
            # if we are to advertise, this should be available... else, it does not matter anyhow
            add_condor_vars_line("GLIDEIN_ADVERTISE_ONLY", "C", "True", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_Failed", "C", "True", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_EXIT_CODE", "I", "-", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_ToDie", "I", "-", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_Expire", "I", "-", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_LAST_SCRIPT", "S", "-", "+", "Y", "Y", "-")
            add_condor_vars_line("GLIDEIN_FAILURE_REASON", "S", "-", "+", "Y", "Y", "-")

        main_work_dir= get_work_dir(main)
        t = x.strftime("%S")
        for t in range(t,dl):
            if os.path.isabs(main_work_dir + "/" + last_script) and do_report == 1:
                # if the file exists, we should be able to talk to the collectors
                # notify that things went badly and we are waiting
                if factory_report_failed != "NEVER":
                    add_config_line("GLIDEIN_ADVERTISE_DESTINATION", "Factory")
                    warnings.warn( "Notifying Factory of error")
                    execfile(main_work_dir + "/" + last_script + " glidein_config")
                    # passing glidein_config as a parameter to that script

                if report_failed != "NEVER":
                    add_config_line("GLIDEIN_ADVERTISE_DESTINATION", "VO")
                    warnings.warn("Notifying VO of error")
                    execfile(main_work_dir + "/" + last_script + " glidein_config")


            # sleep for about 5 mins... but randomize a bit
            ds = 250 + random.randint(sys.maxint) % 100
            das = x.strftime("%S") + ds
            if das > dl:
                # too long, shorten to the deadline
                ds = dl -  x.strftime("%S")
 
            warnings.warn("Sleeping" +  str(ds))
            time.sleep(ds)

        if os.path.isabs(main_work_dir + "/" + last_script) and do_report == 1:
            # notify that things went badly and we are going away
            if factory_report_failed != "NEVER":
                add_config_line("GLIDEIN_ADVERTISE_DESTINATION", "Factory")
                if factory_report_failed == "ALIVEONLY":
                    add_config_line("GLIDEIN_ADVERTISE_TYPE", "INVALIDATE")
                else:
                    add_config_line("GLIDEIN_ADVERTISE_TYPE", "Killing")
                    add_config_line("GLIDEIN_FAILURE_REASON", "Glidein failed while running" + ge_last_script_name + ". Terminating now. (" + str(dl) + ") (" + str(dlf) + ")")

                execfile(main_work_dir + "/" + last_script + " glidein_config")
                warnings.warn("Last notification sent to Factory")

            if report_failed != "NEVER":
                add_config_line("GLIDEIN_ADVERTISE_DESTINATION", "VO")
                if report_failed == "ALIVEONLY":
                    add_config_line("GLIDEIN_ADVERTISE_TYPE", "INVALIDATE")
                else:
                    add_config_line("GLIDEIN_ADVERTISE_TYPE", "Killing")
                    add_config_line("GLIDEIN_FAILURE_REASON", "Glidein failed while running" + ge_last_script_name + ". Terminating now. (" + str(dl) + ") (" + str(dlf) + ")")

                execfile(main_work_dir + "/" + last_script + " glidein_config")
                warnings.warn("Last notification sent to VO")


    log_write("glidein_startup.sh", "text", "glidein is about to exit with retcode" + exitcode, "info")
    # send_logs_to_remote()

    glidien_cleanup()

    print_tail(exitcode, final_result_simple, final_result_long)

    sys.exit(exitcode)


####################################################
# automatically determine and setup work directories
def automatic_work_dir():
    targets=[ str(_CONDOR_SCRATCH_DIR),
                str(OSG_WN_TMP),
                str(TG_NODE_SCRATCH),
                str(TG_CLUSTER_SCRATCH),
                str(SCRATCH),
                str(TMPDIR),
                str(TMP),
                str(PWD)
            ]
    # unset TMPDIR

    # kb
    disk_required=1000000

    for d in targets:

        print >> sys.stder ("Checking " + d + " for potential use as work space... ")

        # does the target exist?
        if not os.path.isabs(d):
            print >> sys.stder ("  Workdir: " + d + " does not exist")
            continue

        # make sure there is enough available diskspace
        # free="$(df -kP "${d}" | awk '{if (NR==2) print $4}')"
        # if "x" + str(free) == "x" or free < disk_required:
        #     print >> sys.stderr "  Workdir: not enough disk space available in " + d
        #     continue

        # if touch "${d}/.dirtest.$$" >/dev/null 2>&1; then
        #     print >> sys.stderr "  Workdir: " + d + " selected" 
        #     rm -f "${d}/.dirtest.$$" >/dev/null 2>&1
        #     # rm - remove files
        #     # $$ - PID of shell 
        #     # 2>&1 - print to stderr
        #     work_dir = d
        #     return 0

        print >> sys.stderr ("  Workdir: not allowed to write to " + d)

    return 1


#######################################
# Parameters utility functions

def params_get_simple():
    # Retrieve a simple parameter (no special characters in its value) from the param list
    # 1:param, 2:param_list (quoted string w/ spaces)
    pass

def params_decode():
    pass


# Put parameters into the config file
def params2file():
    pass

################
# Parse and verify arguments

# allow some parameters to change arguments
# multiglidein GLIDEIN_MULTIGLIDEIN -> multi_glidein
# TODO: add lines 729-837 beneath this comment
# tmp_par = params_get_simple("GLIDEIN_MULTIGLIDEIN", str(params))
# [ -n "${tmp_par}" ] &&  multi_glidein=${tmp_par}

# case "${operation_mode}" in
#     nodebug)
#         sleep_time=1199
#         set_debug=0;;
#     fast)
#         sleep_time=150
#         set_debug=1;;
#     check)
#         sleep_time=150
#         set -x
#         set_debug=2;;
#     *)
#         sleep_time=1199
#         set_debug=1;;
# esac

if descript_file == "":
    warnings.warn( "Missing descript fname.")
    usage()

if descript_entry_file == "":
    warnings.warn("Missing descript fname for entry.")
    usage()

if glidein_name == "":
    warnings.warn("Missing gliden name.")
    usage()

if glidein_entry == "":
    warnings.warn("Missing glidein entry name.")
    usage()


if repository_url == "":
    warnings.warn("Missing Web URL.")
    usage()

repository_entry_url= repository_url + "/" + "entry_" + glidein_entry

if proxy_url == "":
    proxy_url="None"


if proxy_url == "OSG":
    if OSG_SQUID_LOCATION == "":
        # if OSG does not define a Squid, then don't use any
        proxy_url="None"
        warnings.showwarning(message = "OSG_SQUID_LOCATION undefined, not using any Squid URL")
    # else:
    #     proxy_url="$(print("${OSG_SQUID_LOCATION}" | awk -F ':' '{if ($2 =="") {print $1 ":3128"} else {print $0}}')"


if sign_id == "":
    warnings.warn( "Missing signature.")
    usage()

if sign_entry_id == "":
    warnings.warn( "Missing entry signature.")
    usage()

if sign_type == "":
    sign_type="sha1"

if sign_type != "sha1":
    warnings.warn( "Unsupported signtype " + sign_type + " found.")
    usage()

if client_repository_url != "":
  # client data is optional, user url as a switch
  if client_sign_type == "":
      client_sign_type="sha1"

  if client_sign_type != "sha1":
    warnings.warn( "Unsupported clientsigntype " + client_sign_type + " found.")
    usage()

  if client_descript_file == "":
    warnings.warn( "Missing client descript fname.")
    usage()

  if client_repository_group_url != "":
      # client group data is optional, user url as a switch
      if client_group == "":
          warnings.warn( "Missing client group name.")
          usage()

      if client_descript_group_file == "":
          warnings.warn( "Missing client descript fname for group.")
          usage()


def md5wrapper(filename, option):
    # $1 - file name
    # $2 - option (quiet)
    # Result returned on stdout
    pass
    # ERROR_RESULT="???"
    # # local ONLY_SUM

    # if "x" + filename =="xquiet":
    #     ONLY_SUM=yes
   
    # local executable=md5sum
    # if which ${executable} 1>/dev/null 2>&1; then
    #     [ -n "${ONLY_SUM}" ] && executable="md5sum \"$1\" | cut -d ' ' -f 1" ||  executable="md5sum \"$1\""
    # else
    #     executable=md5
    #     if ! which ${executable} 1>/dev/null 2>&1; then
    #         print(ERROR_RESULT)
    #         warnings.warn( "md5wrapper error: can't neither find md5sum nor md5")
    #         return 1
  
    #     [ -n "${ONLY_SUM}" ] && executable="md5 -q \"$1\"" || executable="md5 \"$1\""
    
    # local res
    # Flagged by some checkers but OK
    # if ! res="$(eval "${executable}" 2>/dev/null)"; then
    #     print(ERROR_RESULT)
    #     warnings.warn( "md5wrapper error: can't calculate md5sum using" + executable)
    #     return 1

    # print(res)


# Generate directory ID
def dir_id():
    # create an id to distinguish the directories when preserved
    # [[ ! ",${GLIDEIN_DEBUG_OPTIONS}," = *,nocleanup,* ]] && return
    # dir_id=""
    # tmp="${repository_url%%.*}"
    # tmp="${tmp#*//}"
    # dir_id="${tmp: -4}"
    # tmp="${client_repository_url%%.*}"
    # tmp="${tmp#*//}"
    # dir_id="${dir_id}${tmp: -4}"
    # [[ -z "${dir_id}" ]] && dir_id='debug'
    # print("${dir_id}_"
    pass

# Generate glidein UUID
# TODO: add lines 886-1002 beneath this comment
# if command -v uuidgen >/dev/null 2>&1; then
#     glidein_uuid="$(uuidgen)"
# else:
#     glidein_uuid="$(od -x -w32 -N32 /dev/urandom | awk 'NR==1{OFS='-'; print $2$3,$4,$5,$6,$7$8$9}')"

x = datetime.now()
startup_time= x.strftime("%S")

print("Starting glidein_startup.sh at " + x + " " + startup_time)

print("script_checksum   = " + md5wrapper(glidein_startup.py))
print("debug_mode        = " + operation_mode)
print("condorg_cluster   = " + condorg_cluster)
print("condorg_subcluster= " + condorg_subcluster)
print("condorg_schedd    = " + condorg_schedd)
print("glidein_uuid      = " + glidein_uuid)
print("glidein_credential_id = " + glidein_cred_id)
print("glidein_factory   = " + glidein_factory)
print("glidein_name      = " + glidein_name)
print("glidein_entry     = " + glidein_entry)

if client_name != "":
    # client name not required as it is not used for anything but debug info
    print("client_name       = " + client_name)

if client_group != "":
    print("client_group      = " + client_group)

print("multi_glidein/restart = " + multi_glidein +"/" + multi_glidein_restart)
print("work_dir          = " + work_dir)
print("web_dir           = " + repository_url)
print("sign_type         = " + sign_type)
print("proxy_url         = " + proxy_url)
print("descript_fname    = " + descript_file)
print("descript_entry_fname = " + descript_entry_file)
print("sign_id           = " + sign_id)
print("sign_entry_id     = " + sign_entry_id)

if client_repository_url != "":
    print("client_web_dir              = " + client_repository_url)
    print("client_descript_fname       = " + client_descript_file)
    print("client_sign_type            = " + client_sign_type)
    print("client_sign_id              = " + client_sign_id)
    if client_repository_group_url != "":
        print("client_web_group_dir        = " + client_repository_group_url)
        print("client_descript_group_fname = " + client_descript_group_file)
        print("client_sign_group_id        = " + client_sign_group_id)

print("Running on $(uname -n)")
print("System: $(uname -a)")
if os.path.isabs('/etc/redhat-release'):
 print("Release: $(cat /etc/redhat-release 2>&1)")

print("As: $(id)")
print("PID: $$")

if set_debug != 0:
  print >> sys.stderr ("------- Initial environment ---------------" )
#   env 1>&2
  print >> sys.stderr ("------- =================== ---------------")


# Before anything else, spawn multiple glideins and wait, if asked to do so
if multi_glidein != "" and multi_glidein_restart == "" and int(multi_glidein) > 1:
    # start multiple glideins
    ON_DIE=0
    # trap 'ignore_signal' SIGHUP
    # trap_with_arg 'on_die_multi' SIGTERM SIGINT SIGQUIT
    do_start_all(multi_glidein)
    # Wait for all glideins and exit 0
    # TODO: Summarize exit codes and status from all child glideins
    print >> sys.stderr ("------ Multi-glidein parent waiting for child processes (" + GWMS_MULTIGLIDEIN_CHILDS + ") ----------")
    time.sleep(sleep_time)
    print >> sys.stder ("------ Exiting multi-glidein parent ----------")
    sys.exit(0)


########################################
# make sure nobody else can write my files
# In the Grid world I cannot trust anybody
old_umask = os.umask(0o022)
stats = os.stat()

if oct(stats.st_mode)!= "0022":
    early_glidein_failure("Failed in umask 0022")


########################################
# Setup OSG and/or Globus
if os.path.isfile(OSG_GRID + "/setup.sh") and os.access(OSG_GRID + "/setup.sh", os.R_OK):
    pass
    # . "${OSG_GRID}/setup.sh"
    
else:
    if os.path.isfile(GLITE_LOCAL_CUSTOMIZATION_DIR + "/cp_1.sh") and os.access(GLITE_LOCAL_CUSTOMIZATION_DIR + "/cp_1.sh", os.R_OK):
       pass
        # . "${GLITE_LOCAL_CUSTOMIZATION_DIR}/cp_1.sh"
        


if GLOBUS_PATH == "":
  if GLOBUS_LOCATION == "":
    # if GLOBUS_LOCATION not defined, try to guess it
    if os.path.isfile("/opt/globus/etc/globus-user-env.sh") and os.access("/opt/globus/etc/globus-user-env.sh", os.R_OK):
       GLOBUS_LOCATION="/opt/globus"
    elif os.path.isfile("/osgroot/osgcore/globus/etc/globus-user-env.sh") and os.access("/osgroot/osgcore/globus/etc/globus-user-env.sh", os.R_OK):
       GLOBUS_LOCATION="/osgroot/osgcore/globus"
    else:
       warnings.warn("GLOBUS_LOCATION not defined and could not guess it.")
       warnings.warn("Looked in:")
       warnings.warn(' /opt/globus/etc/globus-user-env.sh')
       warnings.warn(' /osgroot/osgcore/globus/etc/globus-user-env.sh')
       warnings.warn('Continuing like nothing happened')


  if os.path.isfile(GLOBUS_LOCATION + "/etc/globus-user-env.sh") and os.access(GLOBUS_LOCATION + "/etc/globus-user-env.sh", os.R_OK):
    # . "${GLOBUS_LOCATION}/etc/globus-user-env.sh"
    pass
  else:
    warnings.warn("GLOBUS_PATH not defined and " + GLOBUS_LOCATION + "/etc/globus-user-env.sh does not exist.")
    warnings.warn('Continuing like nothing happened')

def set_proxy_fullpath():
     # Set the X509_USER_PROXY path to full path to the file
    X509_USER_PROXY = os.environ.get("X509_USER_PROXY", "")
    
    try:
        fullpath = os.path.abspath(X509_USER_PROXY)
        print("Setting X509_USER_PROXY " + X509_USER_PROXY + " to canonical path " + fullpath, file=sys.stderr)
        os.environ["X509_USER_PROXY"] = fullpath
    except:
        print("Unable to get canonical path for X509_USER_PROXY, using " + X509_USER_PROXY, file=sys.stderr)

    # if fullpath=="$(readlink -f " + X509_USER_PROXY + ")":
    #     print >> sys.stderr ("Setting X509_USER_PROXY " + X509_USER_PROXY + " to canonical path " + fullpath)
    #     os.environ["X509_USER_PROXY"] = fullpath
    #     # export X509_USER_PROXY="${fullpath}"
    # else:
    #     print >> sys.stderr ("Unable to get canonical path for X509_USER_PROXY, using " + X509_USER_PROXY)

# [ -n "${X509_USER_PROXY}" ] && set_proxy_fullpath

# for tk in $(pwd)/*idtoken; do
#   export GLIDEIN_CONDOR_TOKEN="${tk}"
#   if fullpath="$(readlink -f $tk)"; then
#      echo "Setting GLIDEIN_CONDOR_TOKEN $tk to canonical path ${fullpath}" 1>&2
#      export GLIDEIN_CONDOR_TOKEN="${fullpath}"
#   else
#      echo "Unable to get canonical path for GLIDEIN_CONDOR_TOKEN $tk" 1>&2


########################################
# prepare and move to the work directory

# Replace known keywords: Condor, CONDOR, OSG, TMPDIR, AUTO, .
# Empty $work_dir means PWD (same as ".")
# A custom path could be provided (no "*)" in case)

# TODO: add lines 1035-1241 beneath this comment
if work_dir == "":
    work_dir=os.getcwd()
else:
    if work_dir == "Condor" or work_dir == "CONDOR":
        work_dir="_CONDOR_SCRATCH_DIR"
    elif work_dir == "OSG":
        work_dir = "OSG_WN_TMP"
    elif work_dir == "TMPDIR":
        work_dir = "TMPDIR"
    elif work_dir == "AUTO":
        automatic_work_dir()
    else:
        work_dir = os.getcwd()


if work_dir == "":
    early_glidein_failure("Unable to identify Startup dir for the glidein.")

if os.path.isfile(work_dir):
    # echo >/dev/null
    pass
else:
    early_glidein_failure("Startup dir " + work_dir + " does not exist.")


start_dir=os.getcwd()
print("Started in " + start_dir)

# TODO add  lines 1060 - 1241


############################################
# get the proper descript file based on id
# Arg: type (main/entry/client/client_group)
def get_repository_url():
    pass

#####################
# Check signature
def check_file_signature():
    pass

#####################
# Untar support func

def get_untar_subdir():
    pass

#####################
# Periodic execution support function and global variable
add_startd_cron_counter=0
def add_periodic_script():
    pass

#####################
# Fetch a single file
#
# Check cWDictFile/FileDictFile for the number and type of parameters (has to be consistent)
def fetch_file_regular():
    pass

def fetch_file():
    pass

def fetch_file_try():
    pass

def perform_wget():
    pass

def perform_curl():
    pass

def fetch_file_base():
    pass

# Adds $1 to GWMS_PATH and update PATH
def add_to_path():
    pass

# TODO: add lines 1805-2014 beneath this comment





if __name__ == "__main__":
    # Parse arguments from the terminal
    usage()
#