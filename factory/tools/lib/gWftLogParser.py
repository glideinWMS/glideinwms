#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   factory/tool specific condorLogs helper
#

from future import standard_library
standard_library.install_aliases()
import time
import os.path
import mmap
import re
import binascii
import io
import gzip

from glideinwms.lib import condorLogParser
from glideinwms.factory import glideFactoryLogParser

# get the list of jobs that were active at a certain time
def get_glideins(log_dir_name, date_arr, time_arr):
    glidein_list=[]

    cldata=glideFactoryLogParser.dirSummaryTimingsOutFull(log_dir_name)
    cldata.load(active_only=False)
    glidein_data=cldata.data['Completed'] # I am interested only in the completed ones

    ref_ctime=time.mktime(date_arr+time_arr+(0, 0, -1))

    for glidein_el in glidein_data:
        glidein_id, fistTimeStr, runningStartTimeStr, lastTimeStr=glidein_el
        runningStartTime=condorLogParser.rawTime2cTimeLastYear(runningStartTimeStr)
        if runningStartTime>ref_ctime:
            continue # not one of them, started after
        lastTime=condorLogParser.rawTime2cTimeLastYear(lastTimeStr)
        if lastTime<ref_ctime:
            continue # not one of them, ended before
        glidein_list.append(glidein_id)

    return glidein_list
            
# get the list of log files for an entry that were active at a certain time
def get_glidein_logs_entry(factory_dir,entry,date_arr,time_arr,ext="err"):
    log_list=[]
    
    log_dir_name=os.path.join(factory_dir, "entry_%s/log"%entry)
    glidein_list=get_glideins(log_dir_name, date_arr, time_arr)
    for glidein_id in glidein_list:
        glidein_log_file="job.%i.%i."%condorLogParser.rawJobId2Nr(glidein_id)
        glidein_log_file+=ext
        glidein_log_filepath=os.path.join(log_dir_name, glidein_log_file)
        if os.path.exists(glidein_log_filepath):
            log_list.append(glidein_log_filepath)

    return log_list
    
# get the list of log files for an entry that were active at a certain time
def get_glidein_logs(factory_dir,entries,date_arr,time_arr,ext="err"):
    log_list=[]
    for entry in entries:
        entry_log_list=get_glidein_logs_entry(factory_dir, entry, date_arr, time_arr, ext)
        log_list+=entry_log_list

    return log_list

# extract the blob from a glidein log file starting from position 
def get_Compressed_raw(log_fname,start_str, start_pos=0):
    SL_START_RE=re.compile("%s\nbegin-base64 644 -\n"%start_str, re.M|re.DOTALL)
    size = os.path.getsize(log_fname)
    if size==0:
        return "" # mmap would fail... and I know I will not find anything anyhow
    fd=open(log_fname)
    try:
        buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            # first find the header that delimits the log in the file
            start_re=SL_START_RE.search(buf, 0)
            if start_re is None:
                return "" #no StartLog section
            log_start_idx=start_re.end()

            # find where it ends
            log_end_idx=buf.find("\n====", log_start_idx)
            if log_end_idx<0: # up to the end of the file
                return buf[log_start_idx:]
            else:
                return buf[log_start_idx:log_end_idx]
        finally:
            buf.close()
    finally:
        fd.close()

# extract the blob from a glidein log file
def get_Compressed(log_fname, start_str):
    raw_data=get_Compressed_raw(log_fname, start_str)
    if raw_data!="":
        gzip_data=binascii.a2b_base64(raw_data)
        del raw_data
        data_fd=gzip.GzipFile(fileobj=io.StringIO(gzip_data))
        data=data_fd.read()
    else:
        data=raw_data
    return data

# extract the blob from a glidein log file
def get_Simple(log_fname, start_str, end_str):
    SL_START_RE=re.compile(start_str+"\n", re.M|re.DOTALL)
    SL_END_RE=re.compile(end_str, re.M|re.DOTALL)
    size = os.path.getsize(log_fname)
    if size==0:
        return "" # mmap would fail... and I know I will not find anything anyhow
    fd=open(log_fname)
    try:
        buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            # first find the header that delimits the log in the file
            start_re=SL_START_RE.search(buf, 0)
            if start_re is None:
                return "" #no StartLog section
            log_start_idx=start_re.end()

            # find where it ends
            log_end_idx=SL_END_RE.search(buf, log_start_idx)
            if log_end_idx is None: # up to the end of the file
                return buf[log_start_idx:]
            else:
                return buf[log_start_idx:log_end_idx.start()]
        finally:
            buf.close()
    finally:
        fd.close()

# extract the Condor Log from a glidein log file
# condor_log_id should be something like "StartdLog"
def get_CondorLog(log_fname, condor_log_id):
    start_str="^%s\n======== gzip . uuencode ============="%condor_log_id
    return get_Compressed(log_fname, start_str)

# extract the XML Result from a glidein log file
def get_XMLResult(log_fname):
    start_str="^=== Encoded XML description of glidein activity ==="
    s=get_Compressed(log_fname, start_str)
    if s!="":
        return s
    # not found, try the uncompressed version
    start_str="^=== XML description of glidein activity ==="
    end_str="^=== End XML description of glidein activity ==="
    return get_Simple(log_fname, start_str, end_str)


# extract slot names
def get_StarterSlotNames(log_fname, condor_log_id='(StarterLog.slot[0-9]*[_]*[0-9]*)'):
    start_str="^%s\n======== gzip . uuencode ============="%condor_log_id
    SL_START_RE=re.compile("%s\nbegin-base64 644 -\n"%start_str, re.M|re.DOTALL)
    size = os.path.getsize(log_fname)
    if size==0:
        return "" # mmap would fail... and I know I will not find anything anyhow
    fd=open(log_fname)
    try:
        buf=mmap.mmap(fd.fileno(), size, access=mmap.ACCESS_READ)
        try:
            strings = SL_START_RE.findall(buf, 0)
            return strings
        finally:
            buf.close()
    finally:
        fd.close()

