#
# factory/tool specific condorLogs helper
#

import time,os.path
import glideFactoryLogParser
import condorLogParser

# get the list of jobs that were active at a certain time
def get_glideins(log_dir_name,date_arr,time_arr):
    glidein_list=[]

    cldata=glideFactoryLogParser.dirSummaryTimingsOutFull(log_dir_name)
    cldata.load(active_only=False)
    glidein_data=cldata.data['Completed'] # I am interested only in the completed ones

    ref_ctime=time.mktime(date_arr+time_arr+(0,0,-1))

    for glidein_el in glidein_data:
        glidein_id,fistTimeStr,runningStartTimeStr,lastTimeStr=glidein_el
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
    
    log_dir_name=os.path.join(factory_dir,"entry_%s/log"%entry)
    glidein_list=get_glideins(log_dir_name,date_arr,time_arr)
    for glidein_id in glidein_list:
        glidein_log_file="job.%i.%i."%condorLogParser.rawJobId2Nr(glidein_id)
        glidein_log_file+=ext
        glidein_log_filepath=os.path.join(log_dir_name,glidein_log_file)
        if os.path.exists(glidein_log_filepath):
            log_list.append(glidein_log_filepath)

    return log_list
    
# get the list of log files for an entry that were active at a certain time
def get_glidein_logs(factory_dir,entries,date_arr,time_arr,ext="err"):
    log_list=[]
    for entry in entries:
        entry_log_list=get_glidein_logs_entry(factory_dir,entry,date_arr,time_arr,ext)
        log_list+=entry_log_list

    return log_list
