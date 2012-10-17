#!/usr/bin/env python
#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This is the main of the glideinFactory
#
# Arguments:
#   $1 = glidein submit_dir
#
# Author:
#   Igor Sfiligoi (Apr 9th 2007 - moved old glideFactory to glideFactoryEntry)
#

import os
import sys

STARTUP_DIR=sys.path[0]

import fcntl
import subprocess
import traceback
import signal
import time
import string
import copy

sys.path.append(os.path.join(STARTUP_DIR,"../lib"))

import glideFactoryPidLib
import glideFactoryConfig
import glideFactoryLib
import glideFactoryInterface
import glideFactoryMonitorAggregator
import glideFactoryMonitoring
import glideFactoryDowntimeLib

############################################################
def aggregate_stats(in_downtime):
    try:
        _ = glideFactoryMonitorAggregator.aggregateStatus(in_downtime)
    except:
        # protect and report
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logDebug("aggregateStatus failed: %s" % string.join(tb,''))
    
    try:
        _ = glideFactoryMonitorAggregator.aggregateLogSummary()
    except:
        # protect and report
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logDebug("aggregateLogStatus failed: %s" % string.join(tb,''))
    
    try:
        _ = glideFactoryMonitorAggregator.aggregateRRDStats()
    except:
        # protect and report
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logDebug("aggregateRRDStats failed: %s" % string.join(tb,''))
    
    return

# added by C.W. Murphy to make descript.xml
def write_descript(glideinDescript,frontendDescript,monitor_dir):
    glidein_data = copy.deepcopy(glideinDescript.data)
    frontend_data = copy.deepcopy(frontendDescript.data)
    entry_data = {}
    for entry in glidein_data['Entries'].split(","):
        entry_data[entry] = {}

        entryDescript = glideFactoryConfig.JobDescript(entry)
        entry_data[entry]['descript'] = entryDescript.data

        entryAttributes = glideFactoryConfig.JobAttributes(entry)
        entry_data[entry]['attributes'] = entryAttributes.data

        entryParams = glideFactoryConfig.JobParams(entry)
        entry_data[entry]['params'] = entryParams.data

    descript2XML = glideFactoryMonitoring.Descript2XML()
    xml_str = (descript2XML.glideinDescript(glidein_data) +
               descript2XML.frontendDescript(frontend_data) +
               descript2XML.entryDescript(entry_data))

    try:
        descript2XML.writeFile(monitor_dir, xml_str)
    except IOError:
        glideFactoryLib.log_files.logDebug("IOError in writeFile in descript2XML")
    # end add


############################################################
def is_crashing_often(startup_time, restart_interval, restart_attempts):
    crashing_often = True

    if (len(startup_time) < restart_attempts):
        # We haven't exhausted restart attempts
        crashing_often = False
    else:
        # Check if the service has been restarted often
        if restart_attempts == 1:
            crashing_often = True
        elif (time.time() - startup_time[0]) >= restart_interval:
            crashing_often = False
        else:
            crashing_often = True

    return crashing_often

def is_file_old(filename, allowed_time):
    """
    Check if the file is older than given time

    @type filename: String 
    @param filename: Full path to the file
    @type allowed_time: long
    @param allowed_time: Time is second
    
    @rtype: bool
    @return: True if file is older than the given time, else False 
    """
    if (time.time() > (os.path.getmtime(filename) + allowed_time)):
        return True
    return False

############################################################
def clean_exit(childs):
    count=100000000 # set it high, so it is triggered at the first iteration
    sleep_time=0.1 # start with very little sleep
    while len(childs.keys())>0:
        count+=1
        if count>4:
            # Send a term signal to the childs
            # May need to do it several times, in case there are in the middle of something
            count=0
            entries=childs.keys()
            entries.sort()
            glideFactoryLib.log_files.logActivity("Killing entries %s"%entries)
            for entry_name in childs.keys():
                try:
                    os.kill(childs[entry_name].pid,signal.SIGTERM)
                except OSError:
                    glideFactoryLib.log_files.logActivity("Entry %s already dead"%entry_name)
                    del childs[entry_name] # already dead
            
        glideFactoryLib.log_files.logActivity("Sleep")
        time.sleep(sleep_time)
        # exponentially increase, up to 5 secs
        sleep_time=sleep_time*2
        if sleep_time>5:
            sleep_time=5
        
        entries=childs.keys()
        entries.sort()
        
        glideFactoryLib.log_files.logActivity("Checking dying entries %s"%entries)
        dead_entries=[]
        for entry_name in childs.keys():
            child=childs[entry_name]

            # empty stdout and stderr
            try:
                tempOut = child.fromchild.read()
                if len(tempOut)!=0:
                    glideFactoryLib.log_files.logWarning("Child %s STDOUT: %s"%(entry_name, tempOut))
            except IOError:
                pass # ignore
            try:
                tempErr = child.childerr.read()
                if len(tempErr)!=0:
                    glideFactoryLib.log_files.logWarning("Child %s STDERR: %s"%(entry_name, tempErr))
            except IOError:
                pass # ignore

            # look for exited child
            if child.poll()!=-1:
                # the child exited
                dead_entries.append(entry_name)
                del childs[entry_name]
                tempOut = child.fromchild.readlines()
                tempErr = child.childerr.readlines()
        if len(dead_entries)>0:
            glideFactoryLib.log_files.logActivity("These entries died: %s"%dead_entries)

    glideFactoryLib.log_files.logActivity("All entries dead")


############################################################
def spawn(sleep_time,advertize_rate,startup_dir,
          glideinDescript,entries,restart_attempts,restart_interval):

    global STARTUP_DIR
    childs={}

    starttime = time.time()
    oldkey_gracetime = int(glideinDescript.data['OldPubKeyGraceTime'])
    oldkey_eoltime = starttime + oldkey_gracetime
    
    childs_uptime={}

    factory_downtimes = glideFactoryDowntimeLib.DowntimeFile(glideinDescript.data['DowntimesFile'])

    glideFactoryLib.log_files.logActivity("Starting entries %s"%entries)
    try:
        for entry_name in entries:
            # Converted to using the subprocess module
            command_list = [sys.executable, 
                            os.path.join(STARTUP_DIR,"glideFactoryEntry.py"),
                            str(os.getpid()),
                            str(sleep_time),
                            str(advertize_rate),
                            startup_dir,
                            entry_name]
            childs[entry_name] = subprocess.Popen(command_list, shell=False,
                                                  stdout=subprocess.PIPE,
                                                  stderr=subprocess.PIPE)

            # Get the startup time. Used to check if the entry is crashing
            # periodically and needs to be restarted.
            childs_uptime[entry_name]=list()
            childs_uptime[entry_name].insert(0,time.time())
        glideFactoryLib.log_files.logActivity("Entry startup times: %s"%childs_uptime)

        for entry_name in childs.keys():
            # set it in non blocking mode
            # since we will run for a long time, we do not want to block
            for fd  in (childs[entry_name].stdout.fileno(),childs[entry_name].stderr.fileno()):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        while 1:
            # THIS IS FOR SECURITY
            # Make sure you delete the old key when its grace is up.
            # If a compromised key is left around and if attacker can somehow 
            # trigger FactoryEntry process crash, we do not want the entry to pick up 
            # the old key again when factory auto restarts it.  
            if ( (time.time() > oldkey_eoltime) and 
             (glideinDescript.data['OldPubKeyObj'] != None) ):
                glideinDescript.data['OldPubKeyObj'] = None
                glideinDescript.data['OldPubKeyType'] = None
                try:
                    glideinDescript.remove_old_key()
                    glideFactoryLib.log_files.logActivity("Removed the old public key after its grace time of %s seconds" % oldkey_gracetime)
                except:
                    # Do not crash if delete fails. Just log it.
                    glideFactoryLib.log_files.logActivity("Failed to remove the old public key after its grace time")
                    glideFactoryLib.log_files.logWarning("Failed to remove the old public key after its grace time")

            glideFactoryLib.log_files.logActivity("Checking entries %s"%entries)
            for entry_name in childs.keys():
                child=childs[entry_name]

                # empty stdout and stderr
                try:
                    tempOut = child.stdout.read()
                    if len(tempOut)!=0:
                        glideFactoryLib.log_files.logWarning("Child %s STDOUT: %s"%(entry_name, tempOut))
                except IOError:
                    pass # ignore
                try:
                    tempErr = child.stderr.read()
                    if len(tempErr)!=0:
                        glideFactoryLib.log_files.logWarning("Child %s STDERR: %s"%(entry_name, tempErr))
                except IOError:
                    pass # ignore
                
                # look for exited child
                if child.poll()!=-1:
                    # the child exited
                    glideFactoryLib.log_files.logWarning("Child %s exited. Checking if it should be restarted."%(entry_name))
                    tempOut = child.stdout.readlines()
                    tempErr = child.stderr.readlines()

                    if is_crashing_often(childs_uptime[entry_name],
                                         restart_interval, restart_attempts):
                        del childs[entry_name]
                        raise RuntimeError,"Entry '%s' has been crashing too often, quit the whole factory:\n%s\n%s"%(entry_name,tempOut,tempErr)
                    else:
                        # Restart the entry setting its restart time
                        glideFactoryLib.log_files.logWarning("Restarting child %s."%(entry_name))
                        del childs[entry_name]

                        # Converted to using the subprocess module
                        command_list = [sys.executable, 
                                        os.path.join(STARTUP_DIR,
                                                     "glideFactoryEntry.py"),
                                        str(os.getpid()),
                                        str(sleep_time),
                                        str(advertize_rate),
                                        startup_dir,
                                        entry_name]
                        childs[entry_name] = subprocess.Popen(
                                                 command_list, shell=False,
                                                 stdout=subprocess.PIPE,
                                                 stderr=subprocess.PIPE)

                        if len(childs_uptime[entry_name]) == restart_attempts:
                            childs_uptime[entry_name].pop(0)
                        childs_uptime[entry_name].append(time.time())
                        for fd  in (childs[entry_name].stdout.fileno(),
                                    childs[entry_name].stderr.fileno()):
                            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        glideFactoryLib.log_files.logWarning("Entry startup/restart times: %s"%childs_uptime)

            glideFactoryLib.log_files.logActivity("Aggregate monitoring data")
            aggregate_stats(factory_downtimes.checkDowntime())
            
            # do it just before the sleep
            glideFactoryLib.log_files.cleanup()

            glideFactoryLib.log_files.logActivity("Sleep %s secs" % sleep_time)
            time.sleep(sleep_time)
    finally:        
        # cleanup at exit
        glideFactoryLib.log_files.logActivity("Received signal...exit")
        try:
            try:
                clean_exit(childs)
            except:
                # if anything goes wrong, hardkill the rest
                for entry_name in childs.keys():
                    glideFactoryLib.log_files.logActivity("Hard killing entry %s"%entry_name)
                    try:
                        os.kill(childs[entry_name].pid,signal.SIGKILL)
                    except OSError:
                        pass # ignore dead clients
        finally:
            glideFactoryLib.log_files.logActivity("Deadvertize myself")
            try:
                glideFactoryInterface.deadvertizeFactory(glideinDescript.data['FactoryName'],
                                                         glideinDescript.data['GlideinName'])
            except:
                glideFactoryLib.log_files.logWarning("Factory deadvertize failed!")
                pass # just warn
            try:
                glideFactoryInterface.deadvertizeFactoryClientMonitoring(glideinDescript.data['FactoryName'],
                                                                         glideinDescript.data['GlideinName'])
            except:
                glideFactoryLib.log_files.logWarning("Factory Monitoring deadvertize failed!")
                pass # just warn
        glideFactoryLib.log_files.logActivity("All entries should be terminated")
        
        
############################################################
def main(startup_dir):
    """
    Reads in the configuration file and starts up the factory
    
    @type startup_dir: String 
    @param startup_dir: Path to glideinsubmit directory
    """

    # We don't use this anywhere?
    #startup_time = time.time()

    # force integrity checks on all the operations
    # I need integrity checks also on reads, as I depend on them
    os.environ['_CONDOR_SEC_DEFAULT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_CLIENT_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_READ_INTEGRITY'] = 'REQUIRED'
    os.environ['_CONDOR_SEC_WRITE_INTEGRITY'] = 'REQUIRED'

    glideFactoryInterface.factoryConfig.lock_dir=os.path.join(startup_dir,"lock")

    glideFactoryConfig.factoryConfig.glidein_descript_file=os.path.join(startup_dir,glideFactoryConfig.factoryConfig.glidein_descript_file)
    glideinDescript=glideFactoryConfig.GlideinDescript()
    frontendDescript = glideFactoryConfig.FrontendDescript()

    write_descript(glideinDescript,frontendDescript,os.path.join(startup_dir, 'monitor/'))

    # the log dir is shared between the factory main and the entries, so use a subdir
    log_dir=os.path.join(glideinDescript.data['LogDir'],"factory")

    # Configure the process to use the proper LogDir as soon as you get the info
    glideFactoryLib.log_files=glideFactoryLib.LogFiles(log_dir,
                                                       float(glideinDescript.data['LogRetentionMaxDays']),
                                                       float(glideinDescript.data['LogRetentionMinDays']),
                                                       float(glideinDescript.data['LogRetentionMaxMBs']))

    try:
        os.chdir(startup_dir)
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Unable to change to startup_dir %s: %s" % (startup_dir,tb))
        raise

    try:
        
        if (is_file_old(glideinDescript.default_rsakey_fname, 
                        int(glideinDescript.data['OldPubKeyGraceTime']))):
            # First back and load any existing key
            glideFactoryLib.log_files.logActivity("Backing up and loading old key")
            glideinDescript.backup_and_load_old_key()
            # Create a new key for this run
            glideFactoryLib.log_files.logActivity("Recreating and loading new key")
            glideinDescript.load_pub_key(recreate=True)
        else:
            # Key is recent enough. Just reuse them.
            glideFactoryLib.log_files.logActivity("Key is recent enough")
            glideFactoryLib.log_files.logActivity("Reusing key for this run")
            glideinDescript.load_pub_key(recreate=False)
            glideFactoryLib.log_files.logActivity("Loading old key")
            glideinDescript.load_old_rsa_key()
        
        glideFactoryMonitorAggregator.glideFactoryMonitoring.monitoringConfig.my_name="%s@%s"%(glideinDescript.data['GlideinName'],glideinDescript.data['FactoryName'])

        # check that the GSI environment is properly set
        if not os.environ.has_key('X509_CERT_DIR'):
            if os.path.isdir('/etc/grid-security/certificates'):
                os.environ['X509_CERT_DIR']='/etc/grid-security/certificates'
                glideFactoryLib.log_files.logActivity("Environment variable X509_CERT_DIR not set, defaulting to /etc/grid-security/certificates")
            else:  
                glideFactoryLib.log_files.logWarning("Environment variable X509_CERT_DIR not set and /etc/grid-security/certificates does not exist. Need X509_CERT_DIR to work!")
                raise RuntimeError, "Need X509_CERT_DIR to work!"

        allowed_proxy_source=glideinDescript.data['AllowedJobProxySource'].split(',')
        if 'factory' in allowed_proxy_source:
            if not os.environ.has_key('X509_USER_PROXY'):
                glideFactoryLib.log_files.logWarning("Factory is supposed to allow provide a proxy, but environment variable X509_USER_PROXY not set. Need X509_USER_PROXY to work!")
                raise RuntimeError, "Factory is supposed to allow provide a proxy. Need X509_USER_PROXY to work!"
            


        glideFactoryInterface.factoryConfig.advertise_use_tcp=(glideinDescript.data['AdvertiseWithTCP'] in ('True','1'))
        glideFactoryInterface.factoryConfig.advertise_use_multi=(glideinDescript.data['AdvertiseWithMultiple'] in ('True','1'))
        sleep_time=int(glideinDescript.data['LoopDelay'])
        advertize_rate=int(glideinDescript.data['AdvertiseDelay'])
        restart_attempts=int(glideinDescript.data['RestartAttempts'])
        restart_interval=int(glideinDescript.data['RestartInterval'])
        
        entries=string.split(glideinDescript.data['Entries'],',')
        entries.sort()

        glideFactoryMonitorAggregator.monitorAggregatorConfig.config_factory(os.path.join(startup_dir,"monitor"),entries)
    except:
        tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                        sys.exc_info()[2])
        glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)
        raise

    # create lock file
    pid_obj=glideFactoryPidLib.FactoryPidSupport(startup_dir)
    
    # start
    pid_obj.register()
    try:
        try:
            spawn(sleep_time,advertize_rate,startup_dir,
                  glideinDescript,entries,restart_attempts,restart_interval)
        except KeyboardInterrupt,e:
            raise e
        except:
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            glideFactoryLib.log_files.logWarning("Exception occurred: %s" % tb)
    finally:
        pid_obj.relinquish()
    
############################################################
#
# S T A R T U P
#
############################################################

def termsignal(signr,frame):
    raise KeyboardInterrupt, "Received signal %s"%signr

if __name__ == '__main__':
    signal.signal(signal.SIGTERM,termsignal)
    signal.signal(signal.SIGQUIT,termsignal)

    try:
        main(sys.argv[1])
    except KeyboardInterrupt,e:
        glideFactoryLib.log_files.logActivity("Terminating: %s"%e)
