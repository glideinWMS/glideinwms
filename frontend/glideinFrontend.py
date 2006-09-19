import os,sys,time
import glideinFrontendInterface
import glideinFrontendLib

client_name="testFrontend"

############################################################
def iterate_one(factory_pool,
                schedd_names,match_str,
                max_idle,reserve_idle,
                glidein_params):

    glidein_dict=glideinFrontendInterface.findGlideins(factory_pool)
    condorq_dict=glideinFrontendLib.getIdleCondorQ(schedd_names)

    print "Match"
    count_glideins=glideinFrontendLib.countMatchIdle(match_str,condorq_dict,glidein_dict)

    print count_glideins
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
        glideinFrontendInterface.advertizeWork(factory_pool,client_name,request_name,glidename,glidein_min_idle,glidein_params)

    return

############################################################
def iterate(factory_pool,
            schedd_names,match_str,
            max_idle,reserve_idle,
            glidein_params):
    while 1:
        print "Iteration at %s" % time.ctime()
        done_something=iterate_one(factory_pool,schedd_names,match_str,max_idle,reserve_idle,glidein_params)
        print "Sleep"
        time.sleep(30)

############################################################
def main():
    iterate(None,['sfiligoi@cms-xen6.fnal.gov'],'1',20,5,{"GLIDEIN_Collector":"cms-xen6.fnal.gov"})

############################################################
#
# S T A R T U P
#
############################################################

if __name__ == '__main__':
    main()
 
