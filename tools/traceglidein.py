#!/usr/bin/env python 
import os
import sys
import string
from glideinwms.lib import condorMonitor
from glideinwms.frontend.glideinFrontendLib import getGlideinCpusNum
from pprint import pprint
from hkutils import FrontendConfig, format_condor_dict

from collections import defaultdict
# to do
# my-Frontend = the Fronend that scans the Scedulers that I can submit my jobs to
# First, I might need to know whether the my-Frontend works fine..


def hkfind():
# Most importantly, I need to know the URL of the POOL Scheduler
    factory_collector = 'hepcloud-devfac.fnal.gov'
    pool_collector    = 'hepcloud-devfe.fnal.gov'
    pool_scheduler    = "hepcloud-devfe.fnal.gov"
# query parameters
    username = "hyunwoo"
    group_name = 'main'
    frontend_name = 'hepcloud-devfe-fnal-gov_OSG_gWMSFrontend'
    frontendgroup = frontend_name + '.' + group_name  # print 'frontgroup ', frontendgroup

# build constraint for jobs
    userurl = username + "@" + pool_scheduler

    idlejob_query = '(JobStatus==1) && (Owner=="%s") && (User=="%s")' % (username, userurl) # hkformatlist = [ ('RequestCpus', 'i') ]
    condorq = condorMonitor.CondorQ( pool_scheduler )
#    condorq.load( idlejob_query )
#    condorq_data = condorq.fetchStored()
#    print 'number of idle jobs is ', len( condorq_data ) #    pprint( condorq_data )


# at this point, I need to know if there are matching glideins
# first, get the matching expressions from the glideresource

# build constraint for glideresource
    glires_constraint  = '(GlideinMyType=?="%s")' % "glideresource" # additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
    additional_constraint = '&& (True)'
    glires_constraint += additional_constraint

    glires_status = condorMonitor.CondorStatus( "any", pool_name=pool_collector )
    glires_status.require_integrity(True)

    glires_status.load( glires_constraint )
    glires_data = glires_status.fetchStored() # print( type(glires_data ) )  # answer is dict


# here glires_data is a dictionary of all glideresource

    dict_glires_jobs = defaultdict(list)
    for gridx in glires_data:
        print( "glideresource idx = %s"% gridx)
        match_expression = glires_data[ gridx ][ 'GlideClientMatchingGlideinCondorExpr'  ]
        job_query_exp    = glires_data[ gridx ][ 'GlideClientConstraintJobCondorExpr'    ]
        fac_query_exp    = glires_data[ gridx ][ 'GlideClientMatchingInternalPythonExpr' ]

        print 'match exp = ', match_expression
        print 'job query = ', job_query_exp
        print 'fac query = ', fac_query_exp

# build constraint to query jobs that match job_query_exp # ( (JobUniverse==5) && (GLIDEIN_Is_Monitor =!= TRUE) && (JOB_Is_Monitor =!= TRUE) )
        job_query_exp += '&& (%s)' % idlejob_query
        condorq.load( job_query_exp )
        condorq_data = condorq.fetchStored()
#        job = condorq_data[ condorq_data.keys()[0] ]

        print 'jobs matching the query expression %s ===============' % job_query_exp
        print 'number of matched jobs is ', len( condorq_data )

#        pprint( condorq_data )
        for jobidx in condorq_data:
            dict_glires_jobs[    gridx ].append( jobidx )


# reverting dict_glires_jobs to dict_jobs_glires
    pprint( dict_glires_jobs )
    dict_jobs_glires = defaultdict(list)
    for tmpidx in dict_glires_jobs:
        for tmpidy in dict_glires_jobs[tmpidx]:
            dict_jobs_glires[ tmpidy ].append( tmpidx )
    pprint( dict_jobs_glires )


    glifac_constraint  = '(GlideinMyType=?="%s")' % "glidefactory"
#    additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
#    flient_constraint += additional_constraint
    glifac_constraint += '&& %s' % fac_query_exp

    glifac_status = condorMonitor.CondorStatus( "any", pool_name=factory_collector )
    glifac_status.require_integrity(True)

    glifac_status.load( glifac_constraint )
    glifac_data = glifac_status.fetchStored()
#    pprint( format_condor_dict(flient_data ))
    formatted_glifac_data = format_condor_dict( glifac_data )

#    pprint( formatted_glifac_data )


# HK> now glidefactoryclient 

    glifacli_constraint  = '(GlideinMyType=?="%s")' % "glidefactoryclient"
    glifacli_status = condorMonitor.CondorStatus( "any", pool_name=factory_collector )
    glifacli_status.require_integrity(True)

    glifacli_status.load( glifacli_constraint )
    glifacli_data = glifacli_status.fetchStored()
#    pprint( glifacli_data )


# HK> end glidefactoryclient 

# debugging purpose only
    for jobidx in dict_jobs_glires:
        print( jobidx )

        # this job is needed when doing eval( match_expression )
        job = condorq_data[ jobidx ]
#        pprint( job )
        # print( 'job type =', type( job ) ) # dict


        list_of_glideresources = dict_jobs_glires[ jobidx ]

        # looping over the names of glideresource class-ads
        for gridx in list_of_glideresources:
            match_expression = glires_data[gridx][ 'GlideClientMatchingGlideinCondorExpr' ]
            gfname           = glires_data[gridx][ 'GlideFactoryName' ]
            print( gfname )
            print( match_expression )
            associated_gf = formatted_glifac_data[ gfname ]
            glidein = associated_gf
#            pprint( associated_gf['attrs'])

            if eval( match_expression  ):
                print( 'job id %s and glidefactory id %s are matching.'%( job.get('GlobalJobId'), gfname )    )

                print( ' associated gatekeeper from glidefactoryclient = %s ' % glifacli_data[ gridx ][ 'GLIDEIN_Gatekeeper'  ] )
                print( ' associated minimum from glidefactoryclient = %d ' % glifacli_data[ gridx ][ 'GlideinMonitorRequestedIdle' ] )
                print( ' associated maximum from glidefactoryclient = %d ' % glifacli_data[ gridx ][ 'GlideinMonitorRequestedMaxGlideins' ] )


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

          
    sys.exit(0)

#from glidefactoryclient
#ReqClientName = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
#ReqClientReqName = "MMEntry@gfactory_instance@gfactory_service"
#ReqGlidein       = "MMEntry@gfactory_instance@gfactory_service"
#ReqEntryName = "MMEntry"
#ReqFactoryName = "gfactory_service"
#ReqGlideinName = "gfactory_instance"

    sys.exit(0)

### at this point, I need to know if there are Machine CAs

def main():
    hkfind()

if __name__ == '__main__':
    main()
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


