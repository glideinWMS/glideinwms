#!/usr/bin/env python 
import os
import sys
import string
from glideinwms.lib import condorMonitor
from glideinwms.frontend.glideinFrontendLib import getGlideinCpusNum
from pprint import pprint
from hkutils import FrontendConfig, format_condor_dict


#JobStatus in job ClassAds
# 0 Unexpanded     U
# 1 Idle           I
# 2 Running        R
# 3 Removed        X
# 4 Completed      C
# 5 Held           H
# 6 Submission_err E

# JobCA has Owner = "hyunwoo"
# JobCA has User = "hyunwoo@POOLCollector"


# to do
# my-Frontend = the Fronend that scans the Scedulers that I can submit my jobs to
# First, I might need to know whether the my-Frontend works fine..


def hkfind():
# Most importantly, I need to know the URL of the POOL Scheduler
    factory_collector = 'hepcloud-devfac.fnal.gov'
    pool_collector = 'hepcloud-devfe.fnal.gov'
    pool_scheduler = "hepcloud-devfe.fnal.gov"
# query parameters
    username = "hyunwoo"
    group_name = 'main'
    frontend_name = 'hepcloud-devfe-fnal-gov_OSG_gWMSFrontend'
    frontendgroup = frontend_name + '.' + group_name
    print 'frontgroup ', frontendgroup


# build constraint for jobs
    userurl = username + "@" + pool_scheduler

    idlejob_query = '(JobStatus==1) && (Owner=="%s") && (User=="%s")' % (username, userurl)
#    hkformatlist = [ ('RequestCpus', 'i') ]

    condorq = condorMonitor.CondorQ( pool_scheduler )
    condorq.load( idlejob_query )
    condorq_data = condorq.fetchStored()
    print 'number of idle jobs is ', len( condorq_data )
#    pprint( condorq_data )


# at this point, I need to know if there are matching glideins
# first, get the matching expressions from the glideresource

# build constraint for glideresource
    glires_constraint  = '(GlideinMyType=?="%s")' % "glideresource"
#    additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
    additional_constraint = '&& (True)'
    glires_constraint += additional_constraint

    glires_status = condorMonitor.CondorStatus( "any", pool_name=pool_collector )
    glires_status.require_integrity(True)

    glires_status.load( glires_constraint )
    glires_data = glires_status.fetchStored()
#    pprint( pool_data )

#    for x in pool_data:
#        print pool_data[x]['GlideClientMatchingGlideinCondorExpr']
#        print pool_data[x]['GlideClientConstraintJobCondorExpr']
#        print pool_data[x]['GlideClientMatchingInternalPythonExpr']
#        print pool_data[x]['GlideClientConstraintFactoryCondorExpr']
#        print 'xxxxxxxxxxxxxxxxx'

#the match express: GlideClientMatchingGlideinCondorExpr  ="((True) and (getGlideinCpusNum(glidein) >= int(job.get(\"RequestCpus\", 1)))) and (True)"
#job query express: GlideClientConstraintJobCondorExpr    ="((JobUniverse==5)&&(GLIDEIN_Is_Monitor =!= TRUE)&&(JOB_Is_Monitor =!= TRUE)) && (True)"
#factory query exp: GlideClientMatchingInternalPythonExpr ="(True) && (((stringListMember(\"OSG\", GLIDEIN_Supported_VOs))))"
#start expression:  GlideClientConstraintFactoryCondorExpr="True"

    keys = glires_data.keys()
    print 'glideresource key = ', keys
    match_expression = glires_data[ keys[0] ][ 'GlideClientMatchingGlideinCondorExpr'  ]
    job_query_exp    = glires_data[ keys[0] ][ 'GlideClientConstraintJobCondorExpr'    ]
    fac_query_exp    = glires_data[ keys[0] ][ 'GlideClientMatchingInternalPythonExpr' ]

    print 'match exp = ', match_expression
    print 'job query = ', job_query_exp
    print 'fac query = ', fac_query_exp

# build constraint for jobs
    print 'jobs==============='
    job_query_exp += '&& (%s)' % idlejob_query
    condorq.load( job_query_exp )
    condorq_data = condorq.fetchStored()
    job = condorq_data[ condorq_data.keys()[0] ]



# build constraint for glidefactoryclient
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

    print 'printing the match expression'

    for idx in formatted_glifac_data.keys():
        glidein = formatted_glifac_data[ idx ]
#        print 'eval:', eval( match_expression  )
        if eval( match_expression  ):
            print 'there is at least one glidein resource, i.e. glidefactory CA'
            print 'Now, I need to see if there are Machines that were created from these'
            print 'Also, I need to query the Factory Scheduler if there are glideins in the Entry Schedulers'


#from glidefactoryclient
#ReqClientName = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
#ReqClientReqName = "MMEntry@gfactory_instance@gfactory_service"
#ReqGlidein       = "MMEntry@gfactory_instance@gfactory_service"
#ReqEntryName = "MMEntry"
#ReqFactoryName = "gfactory_service"
#ReqGlideinName = "gfactory_instance"

    schedd_name = "schedd_glideins4@hepcloud-devfac.fnal.gov"
    q = condorMonitor.CondorQ(  schedd_name, pool_name=factory_collector  )
    q.factory_name = "gfactory_service"
    q.glidein_name = "gfactory_instance"
    q.entry_name = "MMEntry"
    q.client_name = "hepcloud-devfe-fnal-gov_OSG_gWMSFrontend.main"
    q.load()
#    q.load(q_glidein_constraint, q_glidein_format_list)
    tempdata = q.fetchStored()
    pprint( tempdata )

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


