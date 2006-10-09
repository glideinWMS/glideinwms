#
# Description:
#   This is the main of the glideinFrontend
#
# Arguments:
#   $1 = poll period (in seconds)
#   $2 = advertize rate even if no changes (every $2 loops)
#   $3 = config file
#
# Author:
#   Igor Sfiligoi (Sept 19th 2006)
#

import os
import sys
import traceback
import time
sys.path.append("../lib")

import glideinFrontendInterface
import glideinFrontendLib

############################################################
def iterate_one(frontend_name,factory_pool,
                schedd_names,job_constraint,match_str,
                max_idle,reserve_idle,
                glidein_params):

    glidein_dict=glideinFrontendInterface.findGlideins(factory_pool)
    condorq_dict=glideinFrontendLib.getIdleCondorQ(schedd_names,job_constraint)

    print "Match"
    count_glideins=glideinFrontendLib.countMatchIdle(match_str,condorq_dict,glidein_dict)

    for glidename in count_glideins.keys():
        request_name=glidename

        idle_jobs=count_glideins[glidename]

        if idle_jobs>0:
            glidein_min_idle=idle_jobs+reserve_idle # add a little safety margin
            if glidein_min_idle>max_idle:
                glidein_min_idle=max_idle # but never go above max
        else:
            # no idle, make sure the glideins know it
            glidein_min_idle=0 

        print "Advertize %s %i"%(request_name,glidein_min_idle)
        glideinFrontendInterface.advertizeWork(factory_pool,frontend_name,request_name,glidename,glidein_min_idle,glidein_params)

    return

############################################################
def iterate(sleep_time,
            frontend_name,factory_pool,
            schedd_names,job_constraint,match_str,
            max_idle,reserve_idle,
            glidein_params):
    is_first=1
    while 1:
        print "Iteration at %s" % time.ctime()
        try:
            done_something=iterate_one(frontend_name,factory_pool,schedd_names,job_constraint,match_str,max_idle,reserve_idle,glidein_params)
        except:
            if is_first:
                raise
            else:
                # if not the first pass, just warn
                tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                                sys.exc_info()[2])
                print "Exception: %s" %(jid,segment,tb)
                
        is_first=0
        print "Sleep"
        time.sleep(sleep_time)

############################################################
def main(sleep_time,advertize_rate,config_file):
    config_dict={}
    execfile(config_file,config_dict)
    iterate(sleep_time,
            config_dict['frontend_name'],config_dict['factory_pool'],
            config_dict['schedd_names'], config_dict['job_constraint'],config_dict['match_string'],
            20, 5,
            config_dict['glidein_params'])

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
 
