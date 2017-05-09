#!/usr/bin/env python 
import os
import sys
import string
from glideinwms.lib import condorMonitor
from glideinwms.frontend.glideinFrontendLib import getGlideinCpusNum
from pprint import pprint
from tgutils import FrontendConfig, format_condor_dict

from collections import defaultdict
import argparse

def main(arg_poolsched, arg_poolcollt, arg_factcollt, arg_username):

    print("TG Main starts ")
    print(" ")
    print(" ")

    factory_collector = arg_factcollt
    pool_collector = arg_poolcollt
    pool_scheduler = arg_poolsched
    username = arg_username

    poolScheduler = condorMonitor.CondorQ( pool_scheduler )
    poolCollector = condorMonitor.CondorStatus( "any", pool_name=pool_collector )
    gwmsCollector = condorMonitor.CondorStatus( "any", pool_name=factory_collector )
    poolCollector.require_integrity(True)
    gwmsCollector.require_integrity(True)

#    group_name = 'main'
#    frontend_name = 'hepcloud-devfe-fnal-gov_OSG_gWMSFrontend'
#    frontendgroup = frontend_name + '.' + group_name

# build constraint for jobs
    userurl = username + "@" + pool_scheduler

# TG:
# TG:
# TG: note that there are two types of idle jobs
# TG: type 1: idle jobs that match JobStatus==1 Owner== && User==
# TG: type 2: idle jobs that match JobStatus==1 Owner== && User==  AND also satisfy job_query_expr of glideresource CA
    idlejob_query = '(JobStatus==1) && (Owner=="%s") && (User=="%s")' % (username, userurl) # hkformatlist = [ ('RequestCpus', 'i') ]
    poolScheduler.load(idlejob_query)
    idleJobList = poolScheduler.fetchStored()

    print("TG Number of Idle jobs queued in the USR-Scheduler %s is %d " % (pool_scheduler, len(idleJobList)))
    print(" ")

# at this point, I need to know if there are matching glideins
# first, get the matching expressions from the glideresource

    print("TG starts with the USRCollector %s" % pool_collector)
    print(" ")
    print(" ")

#    sys.exit(0)

####################################################################################################################
####################################################################################################################
# build constraint for glideresource
    glires_constraint  = '(GlideinMyType=?="%s")' % "glideresource" # additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
    poolCollector.load(glires_constraint)
    glires_data = poolCollector.fetchStored() # print( type(glires_data ) )  # answer is dict
#   glires_data is a dictionary of all glideresource
# looks like condorMonitor.CondorStatus( "any", pool_name=).fetchStored() returns a dictionary with the Names as the keys.

    print("TG Number of glideresource CAs from USR-Collector %s is %d " % (pool_collector, len(glires_data)))
    print(" ")

# TG: the fact that a list of glideresource classads exist, means that
# TG: there are matches between factory query_expr in Frontend and glidefactory CA
# TG: so, we start with a list of existing glideresource CAs
# TG: and reduced to a list of glideresource CAs that accept the current idle job by using job query_expr
# TG: and for each combination of Job and Glidein(Factory Entry), we see if match_expr is satisfied
# TG: which means that glideclient CA will have actual requests for glideins
    dict_glires_jobs = defaultdict(list)
    dict_jobs_glires = defaultdict(list)
    for gridx in glires_data:   #        print("glideresource idx = %s" % gridx)
# following 2 not used within this loop.
#        match_expression = glires_data[gridx]['GlideClientMatchingGlideinCondorExpr']
#        fac_query_exp    = glires_data[gridx]['GlideClientMatchingInternalPythonExpr']
        job_query_exp = glires_data[gridx]['GlideClientConstraintJobCondorExpr']
# build constraint to query jobs that match job_query_exp # ( (JobUniverse==5) && (GLIDEIN_Is_Monitor =!= TRUE) && (JOB_Is_Monitor =!= TRUE) )
        job_query_exp_and_idle = job_query_exp + '&& (%s)' % idlejob_query
        poolScheduler.load(job_query_exp_and_idle)
        condorq_data = poolScheduler.fetchStored()  # job = condorq_data[ condorq_data.keys()[0] ]
#        print 'number of matched jobs is ', len( condorq_data )
        for jobidx in condorq_data:
            dict_glires_jobs[gridx].append(jobidx)

#    pprint( dict_glires_jobs )
# { u'MMEntry@gfactory_instance@gfactory_service@hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main': [(142, 0), (141, 0)] }

# converting dict_glires_jobs to dict_jobs_glires
    for tmpidx in dict_glires_jobs:
        for tmpidy in dict_glires_jobs[tmpidx]:
            dict_jobs_glires[tmpidy].append(tmpidx)
#    pprint( dict_jobs_glires )
# { (142, 0): [u'MMEntry@gfactory_instance@gfactory_service@hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main'], 
#   (141, 0): [u'MMEntry@gfactory_instance@gfactory_service@hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main'] }

###################################################################
#    glicli_constraint   = '(GlideinMyType=?="%s")' % "glideclient"
#    gwmsCollector.load( glicli_constraint )
#    glicli_data2 = gwmsCollector.fetchStored()  #    pprint( glicli_data2.keys() )

    glifacli_constraint = '(GlideinMyType=?="%s")' % "glidefactoryclient"
    gwmsCollector.load(glifacli_constraint)
    glifacli_data = gwmsCollector.fetchStored()  #    pprint( glifacli_data.keys() )
###################################################################
    print( "  " )
    print( "  " )
    print( "major loop starts =========================================" )

    for jobidx in idleJobList:

        print( "  " )
        print( "  " )


        if jobidx not in dict_jobs_glires:
            print("TG-Diagnosis: job ID %s.%s does not satisfy job query_expr of any group" % jobidx)
            pass

        # this job is needed when doing eval( match_expression )
        job = idleJobList[jobidx]

        print("Now, for a given Job, we loop over the associated glideresource classads  =========================================" )
        list_of_glideresources = dict_jobs_glires[jobidx]
        print("TG-Diagnosis: job ID (%s.%s) can go to %d glideresources" % (jobidx[0],jobidx[1], len(list_of_glideresources)))

        # looping over the names of glideresource class-ads
        print( "    looping over associated glideresource classads" )
        for gridx in list_of_glideresources:
            print( "  " )

            print("    the glideresource classAd ID = %s" % gridx)
# gridx = Name = MMEntry@gfactory_instance@gfactory_service@hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main

            match_expression = glires_data[gridx]['GlideClientMatchingGlideinCondorExpr']
            fac_query_exp = glires_data[gridx]['GlideClientMatchingInternalPythonExpr']
            gfname = glires_data[gridx]['GlideFactoryName']
            print("    Entry %s is already coupled with this resource via fac_query_exp" % (gfname))
# TG: 
# TG: For a given Job, if this Job can belong to multiple groups, there can be multiple glideresource that match this Job
# TG: which means duplicate glidefactoy CAs will be displayed here..
            glifac_constraint  = '(GlideinMyType=?="glidefactory") && %s' % fac_query_exp
            gwmsCollector.load(glifac_constraint)
            glifac_data = gwmsCollector.fetchStored()
            formatted_glifac_data = format_condor_dict(glifac_data)
            glidein = formatted_glifac_data[ gfname ] # this is the associated glidefactory

            print("    TG: Now let's see if this Job %s can request some glideins to this Entry %s" % (jobidx[0], gfname))

            if eval(match_expression):
# TG: the fact that this job and this glidefactory are matched means that the request of glideins can be sent to this Entry...
# TG: So, the whole idea is that after the matching is verified, we can look at glidefactoryclient to acquire other meaningful information
                print('=> job id %s and glidefactory id %s are matching.' % (job.get('GlobalJobId'), gfname))

# TG: Remember that the Name of glideresource and the Name of glideFactoryClient are the same but the Name of glideClient is a bit different

# TG: in case of multiple group-matching, there can be multiple glidefactoryclient classads with the same gridx.
# TG: so, it would be better to use glires_data
#                print(' associated minimum from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorRequestedIdle'])
#                print(' associated maximum from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorRequestedMaxGlideins'])
                print('=>associated minimum from glidefactoryclient = %d' % glires_data[gridx]['GlideFactoryMonitorTotalRequestedIdle'])
                print('=>associated maximum from glidefactoryclient = %d' % glires_data[gridx]['GlideFactoryMonitorTotalRequestedMaxGlideins'])

# the following two information is originally available from glidefactory client but also available in glideresource
               
                print("TG: If number of glidein requests in glideclient is not ok, someting might be wrong, let's see if any limits are triggered")

## limits triggered for this Frontend and Factory
#[root@hepcloud-devfe gwms_4989]# condor_status -any -l -constraint '(MyType=?="glideresource")' | sort | grep GlideClientLimit
#GlideClientLimit TotalGlideinsGlobal = "count=0, limit=0"
#GlideClientLimit  IdleGlideinsGlobal = "count=0, limit=0"
#GlideClientLimit TotalGlideinsPerFrontend = "count=0, limit=0"
#GlideClientLimit  IdleGlideinsPerFrontend = "count=0, limit=0"

#GlideClientLimit TotalGlideinsPerEntry
#GlideClientLimit  IdleGlideinsPerEntry
#GlideClientLimit TotalGlideinsPerGroup
#GlideClientLimit  IdleGlideinsPerGroup
#GlideClientLimit TotalGlideinsPerFrontend
#GlideClientLimit  IdleGlideinsPerFrontend
#GlideClientLimit TotalGlideinsGlobal
#GlideClientLimit  IdleGlideinsGlobal
                if True:
                    try:
                        print('  %s  Limits triggered = %s' % ('GlideClientLimitTotalGlideinsPerEntry', glires_data[gridx]['GlideClientLimitTotalGlideinsPerEntry']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitTotalGlideinsPerEntry')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitIdleGlideinsPerEntry', glires_data[gridx]['GlideClientLimitIdleGlideinsPerEntry']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitIdleGlideinsPerEntry')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitTotalGlideinsPerGroup', glires_data[gridx]['GlideClientLimitTotalGlideinsPerGroup']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitTotalGlideinsPerGroup')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitIdleGlideinsPerGroup', glires_data[gridx]['GlideClientLimitIdleGlideinsPerGroup']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitIdleGlideinsPerGroup')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitTotalGlideinsPerFrontend', glires_data[gridx]['GlideClientLimitTotalGlideinsPerFrontend']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitTotalGlideinsPerFrontend')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitIdleGlideinsPerFrontend', glires_data[gridx]['GlideClientLimitIdleGlideinsPerFrontend']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitIdleGlideinsPerFrontend')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitTotalGlideinsGlobal', glires_data[gridx]['GlideClientLimitTotalGlideinsGlobal']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitTotalGlideinsGlobal')
                    try:
                        print('  %s   Limits triggered = %s' % ('GlideClientLimitIdleGlideinsGlobal', glires_data[gridx]['GlideClientLimitIdleGlideinsGlobal']))
                    except:
                        pass
                        #print(' Limits triggered not avaliable = %s' % 'GlideClientLimitIdleGlideinsGlobal')
########################## next comes the Factory limits
# GlideinMonitor Status_GlideFactoryLimit IdleGlideinsPerEntry
# GlideinMonitor Status_GlideFactoryLimit HeldGlideinsPerEntry
# GlideinMonitor Status_GlideFactoryLimit TotalGlideinsPerEntry
# GlideinMonitor Status_GlideFactoryLimit IdlePerClass_fe_sec_class
# GlideinMonitor Status_GlideFactoryLimit TotalPerClass_fe_sec_class


                print( "  " )
                print( "    TG: Does this Entry have any problem submitting glidein_startup to %s?" %glires_data[gridx]['GLIDEIN_Gatekeeper'])
                print('     =>Running glidein_startup from Entry Scheduler = %d' % glires_data[gridx]['GlideFactoryMonitorStatusRunning'])
                print('     =>Queued  glidein_startup from Entry Scheduler = %d' % glires_data[gridx]['GlideFactoryMonitorStatusIdle'])
                print( "    same information but from glide factory client" )
                print('     queued glidein_startup from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalStatusIdle'])
                print('     running glidein_startup from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalStatusRunning'])


                print( "    Number of glideins, working-glideins and idling-glideins" )
                print('     idling-glideins from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalClientMonitorGlideIdle'])
                print('     working-glideins from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalClientMonitorGlideRunning'])
                print('     total from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalClientMonitorGlideTotal'])


                print( "    TG: Low look at Factory limits")
                if True:
                    try:
                        print('  %s Limits triggered = %s' % ('GlideinMonitorStatus_GlideFactoryLimitIdleGlideinsPerEntry', glifacli_data[gridx]['GlideinMonitorStatus_GlideFactoryLimitIdleGlideinsPerEntry']))
                    except:
                        pass
                        #print('Limits triggered not avaliable = %s' % 'GlideinMonitorStatus_GlideFactoryLimitIdleGlideinsPerEntry')
                    try:
                        print('  %s Limits triggered = %s' % ('GlideinMonitorStatus_GlideFactoryLimitHeldGlideinsPerEntry', glifacli_data[gridx]['GlideinMonitorStatus_GlideFactoryLimitHeldGlideinsPerEntry']))
                    except:
                        pass
                        #print('Limits triggered not avaliable = %s' % 'GlideinMonitorStatus_GlideFactoryLimitHeldGlideinsPerEntry')
                    try:
                        print('  %s Limits triggered = %s' % ('GlideinMonitorStatus_GlideFactoryLimitTotalGlideinsPerEntry', glifacli_data[gridx]['GlideinMonitorStatus_GlideFactoryLimitTotalGlideinsPerEntry']))
                    except:
                        pass
                        #print( ' Limits triggered not avaliable = %s' % 'GlideinMonitorStatus_GlideFactoryLimitTotalGlideinsPerEntry' )

                print( "    Number of Jobs from USRScheduler, how useful is this information?" )
                print('     JobsIdle from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalClientMonitorJobsIdle'])
                print('     JobsRunning from glidefactoryclient = %d ' % glifacli_data[gridx]['GlideinMonitorTotalClientMonitorJobsRunning'])
################################################################################################
            print( "    Now probing other Jobs from other Frontends contributing to the same Entry")

# first extract the information from the Entry about the same Frontend 
# how many glidein_startup.sh have been submitted from this Entry to the EntryScheduler
# By looking at the Machine classads, how many glideins are in the running mode within which user jobs are running
# By looking at the Machine classads, how many glideins are in the running mode within which user jobs are idling

# By looking at the Machine classads, how many glideins are in the idling mode within which user jobs are NOT assigned..

# glidefactoryclient has these
# ReqClientName = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
# ReqClientReqName = "MMEntry@gfactory_instance@gfactory_service"
# ReqGlidein       = "MMEntry@gfactory_instance@gfactory_service"


# the following code shows 
#other Frontend contributions to the Entry in question
#- jobs submitted to the Factory Scheduler from this Entry for the other Client
#- Glideins Idle or Running associated with this Entry for the other Client
#- Query result from USR Scheduler associated with this Entry for the other Client")

            for tmpx in glifacli_data:
#                pprint( glifacli_data[tmpx] )
#                print(glifacli_data[tmpx]['ReqClientName'])
#                print(glires_data[gridx]['GlideClientName'])

                if (glifacli_data[tmpx]['ReqGlidein'] == glires_data[gridx]['GlideFactoryName']) and (glifacli_data[tmpx]['ReqClientName'] != glires_data[gridx]['GlideClientName']):
                    print("jobs submitted to the Factory Scheduler from this Entry for the other Client")
                    print(   "=>Running glidein_startup %d"%glifacli_data[tmpx]['GlideinMonitorTotalStatusIdle'])
                    print(   "=>Queued  glidein_startup %d"%glifacli_data[tmpx]['GlideinMonitorTotalStatusRunning'])

                    print("   working-glideins or idling-glideins associated with this Entry for the other Client")
                    print(   "=>idling-glideins = %d"%glifacli_data[tmpx]['GlideinMonitorTotalClientMonitorGlideIdle'])
                    print(   "=>working-glideins= %d"%glifacli_data[tmpx]['GlideinMonitorTotalClientMonitorGlideRunning'])
                    print(   "=>Total = %d"%glifacli_data[tmpx]['GlideinMonitorTotalClientMonitorGlideTotal'])

                    print("Query result from USR Scheduler associated with this Entry for the other Client")
                    print(   "=>JobsIdle = %d"%glifacli_data[tmpx]['GlideinMonitorTotalClientMonitorJobsIdle'])
                    print(   "=>JobsRunning = %d"%glifacli_data[tmpx]['GlideinMonitorTotalClientMonitorJobsRunning'])





## HK> summary begin
#"""
#The achievements so far is,
#I have tried to collect all the relevant data
#in order to extract any meaningful insight into the surrounding circumstances which determine
#the conditions that will decide my job will run or not...
#"""
## HK> summary stop




# next extract the information from the Entry about the other Frontends

# I have to use GlideClientName = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main" from glideresource
# and the followings from glidefactoryclient
# ReqClientName = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
# ReqClientReqName = "MMEntry@gfactory_instance@gfactory_service"
# ReqGlidein       = "MMEntry@gfactory_instance@gfactory_service"



                # HK> summary comment: with this info, I can identify associated glideclient and glidefactoryclient classads
                # HK> from these 2 glideclient and glidefactoryclient classads, I can get how many
#HK> now, I can query the Entry Scheduler to get the number of glideins 
# or from glidefactoryclient
#GlideFactoryMonitor TotalStatusHeld = 0
#GlideFactoryMonitor TotalStatusIdle = 0
#GlideFactoryMonitor TotalStatusIdleOther = 0
#GlideFactoryMonitor TotalStatusPending = 0
#GlideFactoryMonitor TotalStatusRunning = 1
#GlideFactoryMonitor TotalStatusStageIn = 0
#GlideFactoryMonitor TotalStatusStageOut = 0
#GlideFactoryMonitor TotalStatusWait = 0

# querying schedd_name = "schedd_glideins4@hepcloud-devfac.fnal.gov" directly might not make sense
# because factory code internally can extract this schedd information from job.descript files
# but traceglidein.py does not have access to this internal job.descript
# so, conclusion is, I should rely on 
# or from glidefactoryclient
#GlideFactoryMonitor TotalStatusHeld = 0
#GlideFactoryMonitor TotalStatusIdle = 0
#GlideFactoryMonitor TotalStatusIdleOther = 0
#GlideFactoryMonitor TotalStatusPending = 0
#GlideFactoryMonitor TotalStatusRunning = 1
#GlideFactoryMonitor TotalStatusStageIn = 0
#GlideFactoryMonitor TotalStatusStageOut = 0
#GlideFactoryMonitor TotalStatusWait = 0


#                schedd_name = "schedd_glideins4@hepcloud-devfac.fnal.gov"
#                q = condorMonitor.CondorQ(  schedd_name, pool_name=factory_collector  )
#                q.factory_name = "gfactory_service"
#                q.glidein_name = "gfactory_instance"
#                q.entry_name = "MMEntry"
#                q.client_name = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
#                q.load()
#    #    q.load(q_glidein_constraint, q_glidein_format_list)
#                tempdata = q.fetchStored()
#                pprint( tempdata )

#    sys.exit(0)

### at this point, I need to know if there are Machine CAs

if __name__ == '__main__':

    default_fact_collector = 'hepcloud-devfac.fnal.gov'
    default_pool_collector = 'hepcloud-devfe.fnal.gov'
    default_pool_scheduler = "hepcloud-devfe.fnal.gov"
    default_username       = "hyunwoo"

    parser = argparse.ArgumentParser( )
    parser.add_argument('--poolsched', action="store", dest="poolsched", default=default_pool_scheduler )
    parser.add_argument('--poolcollt', action="store", dest="poolcollt", default=default_pool_collector )
    parser.add_argument('--factcollt', action="store", dest="factcollt", default=default_fact_collector )
    parser.add_argument('--username',  action="store", dest="username",  default=default_username )

    hkargs = parser.parse_args( )
    print hkargs.poolsched
    print hkargs.poolcollt
    print hkargs.factcollt
    print hkargs.username

#    sys.exit(0)

    main( hkargs.poolsched, hkargs.poolcollt, hkargs.factcollt, hkargs.username )

# build constraint for glidefactory
#    status_constraint  = '(GlideinMyType=?="%s")' % "glidefactory"
#    factory_identity   = "gfactory@hepcloud-devfac.fnal.gov"
#    status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity
#    signtype = 'sha1'
#    factory_signtype_id = "SupportedSignTypes"
#    status_constraint += ' && stringListMember("%s",%s)' % (signtype, factory_signtype_id)
#    factory_query_expr = '(True) && (((stringListMember("OSG", GLIDEIN_Supported_VOs))))'
#    full_constraint    = '(%s) && ((PubKeyType=?="RSA") && (GlideinAllowx509_Proxy=!=False))'   % factory_query_expr
#    status_constraint += ' && (%s)' % full_constraint
########## end 
#    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
#    status.require_integrity(True)
#    status.load(status_constraint)
#    data = status.fetchStored()
#    pprint( data )
#    firstkey = data.keys()[0]
#    secndkey = data.keys()[1]
#    for x in data:
#        print data[x]['EntryName']

# build constraint for glideclient
#    client_constraint  = '(GlideinMyType=?="%s")' % "glideclient"
#    additional_constraint = '&& (ClientName=?="%s")' % frontendgroup
#    client_constraint += additional_constraint
#    client_status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
#    client_status.require_integrity(True)
#    client_status.load(client_constraint)
#    client_data = client_status.fetchStored()
#    pprint( client_data )
#    print '+++++++++++++++++++++++++++++++'


