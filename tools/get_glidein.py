#!/usr/bin/env python 
import os
import sys
import string
from glideinwms.lib import condorMonitor
from glideinwms.frontend.glideinFrontendLib import getGlideinCpusNum
from pprint import pprint


class FrontendConfig:
    def __init__(self):
        self.factory_id = "glidefactory"
        self.factory_global = "glidefactoryglobal"
        self.client_id = "glideclient"
        self.client_global = "glideclientglobal"
        self.factoryclient_id = "glidefactoryclient"
        self.glidein_attr_prefix = ""
        self.glidein_param_prefix = "GlideinParam"
        self.encrypted_param_prefix = "GlideinEncParam"
        self.glidein_monitor_prefix = "GlideinMonitor"
        self.glidein_config_prefix = "GlideinConfig"
        self.glidein_perfmetric_prefix = "GlideinPerfMetric"
        self.client_req_prefix = "Req"
        self.factory_signtype_id = "SupportedSignTypes"
        self.advertise_use_tcp = False
        self.advertise_use_multi = False
        self.condor_reserved_names = ("MyType", "TargetType", "GlideinMyType", "MyAddress", 'UpdatesHistory', 'UpdatesTotal', 'UpdatesLost', 'UpdatesSequenced', 'UpdateSequenceNumber', 'DaemonStartTime')

frontendConfig = FrontendConfig()
def format_condor_dict(data):
    reserved_names = frontendConfig.condor_reserved_names
    for k in reserved_names:
        if data.has_key(k):
            del data[k]

    out = {}

    for k in data.keys():
        kel = data[k].copy()

        el = {"params":{}, "monitor":{}}

        # first remove reserved anmes
        for attr in reserved_names:
            if kel.has_key(attr):
                del kel[attr]

        # then move the parameters and monitoring
        for (prefix, eldata) in ((frontendConfig.glidein_param_prefix, el["params"]),
                              (frontendConfig.glidein_monitor_prefix, el["monitor"])):
            plen = len(prefix)
            for attr in kel.keys():
                if attr[:plen] == prefix:
                    eldata[attr[plen:]] = kel[attr]
                    del kel[attr]

        # what is left are glidein attributes
        el["attrs"] = kel

        out[k] = el

    return out


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
    pool_collector = 'hepcloud-devfe.fnal.gov'

# query parameters
    username = "hyunwoo"
# build constraint for jobs
    hkschedd = "hepcloud-devfe.fnal.gov"

    userurl = username + "@" + hkschedd

    idlejob_query = '(JobStatus==1)&&(Owner=="%s")&&(User=="%s")'%(username, userurl)
#    hkformatlist = [ ('RequestCpus', 'i') ]
    hkformatlist = [ ]

    condorq = condorMonitor.CondorQ(hkschedd)
    condorq.load( idlejob_query )

    condorq_data = condorq.fetchStored()

    print 'number of idle jobs is ', len( condorq_data )

#    pprint( condorq_data )



### at this point, I need to know if there are Machine CAs

# at this point, I need to know if there are matching glideins
# first, get the matching expressions from the glideresource

# build constraint for glideresource
    pool_constraint  = '(GlideinMyType=?="%s")' % "glideresource"
#    additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
    additional_constraint = '&& (True)'
    pool_constraint += additional_constraint

    pool_status = condorMonitor.CondorStatus("any", pool_name=pool_collector)
    pool_status.require_integrity(True)

    pool_status.load(pool_constraint)
    pool_data = pool_status.fetchStored()
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

    keys = pool_data.keys()
    match_expression = pool_data[keys[0]]['GlideClientMatchingGlideinCondorExpr']
    job_query_exp    = pool_data[keys[0]]['GlideClientConstraintJobCondorExpr']
    fac_query_exp    = pool_data[keys[0]]['GlideClientMatchingInternalPythonExpr']


    factory_pool = 'hepcloud-devfac.fnal.gov'
    group_name = 'main'
    frontend_name = 'hepcloud-devfe-fnal-gov_OSG_gWMSFrontend'
    frontendgroup = frontend_name + '.' + group_name
    print 'frontgroup ', frontendgroup


# build constraint for jobs
    print 'jobs==============='

    job_query_exp += '&& (%s)' % idlejob_query
    condorq.load( job_query_exp )

    condorq_data = condorq.fetchStored()
    pprint( condorq_data )

    job = condorq_data[ condorq_data.keys()[0] ]


# build constraint for glidefactoryclient
    flient_constraint  = '(GlideinMyType=?="%s")' % "glidefactory"
#    flient_constraint  = '(GlideinMyType=?="%s")' % "glidefactoryclient"
#    additional_constraint = '&& (ReqClientName=?="%s")' % frontendgroup
#    flient_constraint += additional_constraint
    flient_constraint += '&& %s' % fac_query_exp

    flient_status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    flient_status.require_integrity(True)

    flient_status.load(flient_constraint)
    flient_data = flient_status.fetchStored()
    pprint( format_condor_dict(flient_data ))
    formatted_flient_data = format_condor_dict(flient_data)

    print '+++++++++++++++++++++++++++++++'



    print 'printing the match expression'
#    match_expression = "((True) and (getGlideinCpusNum(glidein) >= int(job.get(\"RequestCpus\", 1)))) and (True)"  
#    match_expression = "( (True) and (getGlideinCpusNum(glidein)) )"
    print match_expression

    for idx in formatted_flient_data.keys():

        glidein = formatted_flient_data[ idx ]
#    pprint( glidein )
        print 'eval:', eval( match_expression  )
        if eval( match_expression  ):
            print 'there is at least one glidein resource, i.e. glidefactory CA'
            print 'Now, I need to see if there are Machines that were created from these'
            print 'Also, I need to query the Factory Scheduler if there are glideins in the Entry Schedulers'
    sys.exit(0)


# build constraint for glidefactory
    status_constraint  = '(GlideinMyType=?="%s")' % "glidefactory"

    factory_identity   = "gfactory@hepcloud-devfac.fnal.gov"
    status_constraint += ' && (AuthenticatedIdentity=?="%s")' % factory_identity

    signtype = 'sha1'
    factory_signtype_id = "SupportedSignTypes"
    status_constraint += ' && stringListMember("%s",%s)' % (signtype, factory_signtype_id)

    factory_query_expr = '(True) && (((stringListMember("OSG", GLIDEIN_Supported_VOs))))'
    full_constraint    = '(%s) && ((PubKeyType=?="RSA") && (GlideinAllowx509_Proxy=!=False))'   % factory_query_expr
    status_constraint += ' && (%s)' % full_constraint
######### end 
    print 'final cons = ', status_constraint

    status = condorMonitor.CondorStatus("any", pool_name=factory_pool)
    status.require_integrity(True)
    status.load(status_constraint)
    data = status.fetchStored()
    pprint( data )
    firstkey = data.keys()[0]
    secndkey = data.keys()[1]
#    pprint( data[firstkey] )

    for x in data:
        print data[x]['EntryName']


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




def main():
    hkfind()

if __name__ == '__main__':
    main()
