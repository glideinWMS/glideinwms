#
# Description:
#   This tool displays the status of the glideinWMS pool
#   in a XML format
#
# Arguments:
#   None
#
# Author:
#   Igor Sfiligoi (May 9th 2007)
#

import string
import sys
sys.path.append("../factory")
sys.path.append("../frontend")
sys.path.append("../lib")

import glideFactoryInterface
import glideinFrontendInterface
import xmlFormat

remove_condor_stats=True
remove_internals=True

glideins_obj=glideinFrontendInterface.findGlideins(None)
clientsmon_obj=glideinFrontendInterface.findGlideinClientMonitoring(None,None)

glideins=glideins_obj.keys()
for glidein in glideins:
    glidein_el=glideins_obj[glidein]

    # Remove diagnostics attributes, if needed
    if remove_condor_stats:
        del glidein_el['attrs']['LastHeardFrom']

    #rename params into default_params
    glidein_el['default_params']=glidein_el['params']
    del glidein_el['params']

    if remove_internals:
        for attr in ('EntryName','GlideinName','FactoryName'):
            del glidein_el['attrs'][attr]
        
    entry_name,glidein_name,factory_name=string.split(glidein,"@")

    clients_obj=glideFactoryInterface.findWork(factory_name,glidein_name,entry_name)
    glidein_el['clients']=clients_obj
    clients=clients_obj.keys()
    for client in clients:
        if remove_internals:
            del clients_obj[client]['internals']
        
        # rename monitor into client_monitor
        clients_obj[client]['client_monitor']=clients_obj[client]['monitor']
        del clients_obj[client]['monitor']
        # add factory monitor
        if clientsmon_obj.has_key(client):
            clients_obj[client]['factory_monitor']=clientsmon_obj[client]['monitor']



sub_dict={'clients':{'dict_name':'clients','el_name':'client','subtypes_params':{'class':{}}}}
print xmlFormat.dict2string(glideins_obj,'glideinWMS','factory',
                            subtypes_params={'class':{'dicts_params':sub_dict}})

