#
# Project:
#   glideinWMS
#
# File Version: 
#   $Id: ldapMonitor.py,v 1.2.28.1 2010/08/31 18:49:17 parag Exp $
#
# Description:
#   This module implements classes to query the ldap server
#   and manipulate the result
#
# Author:
#   Igor Sfiligoi (Jul 22nd 2008)
#

import ldap

class LDAPQuery:
    def __init__(self,
                 ldap_url,ldap_port, # where to find LDAP server
                 base,filter_str):   # what to read
        self.ldap_url=ldap_url
        self.ldap_port=ldap_port
        self.base=base
        self.filter_str=filter_str
        self.stored_data=None

    # load info in internal storage
    def load(self,additional_filter_str=None):
        self.stored_data=self.fetch(additional_filter_str)

    # rpint out the internal storage
    def fetchStored(self):
        return self.stored_data

    # load from LDAP and print out
    # do not store locally
    def fetch(self,additional_filter_str=None):
        if additional_filter_str==None:
            additional_filter_str=""

        filter_str="(%s%s)"%(self.filter_str,additional_filter_str)

        ldap_obj=ldap.open(self.ldap_url,self.ldap_port)
        ldap_obj.simple_bind('','')
        try:
            bdii_data=ldap_obj.search_s(self.base,ldap.SCOPE_SUBTREE,
                                        filter_str)
        except ldap.FILTER_ERROR, e:
            raise ValueError, "LDAP filter error for '%s': %s"%(filter_str,e)
        del ldap_obj

        out_data={}
        for elarr in bdii_data:
            el1,el2=elarr
            if out_data.has_key(el1):
                raise RuntimeError,"Dublicate element found: "+el1
            out_data[el1]=el2
            
        del bdii_data
        return out_data
        
class BDIICEQuery(LDAPQuery):
    def __init__(self,
                 bdii_url,bdii_port=2170,     # where to find LDAP server
                 additional_filter_str=None): # what to read
        if additional_filter_str==None:
            additional_filter_str=""
            
        filter_str="&(GlueCEInfoContactString=*)%s"%additional_filter_str

        LDAPQuery.__init__(self,bdii_url,bdii_port,
                           "mds-vo-name=local,o=grid",filter_str)

    def fetch(self,additional_filter_str=None):
        out_data=LDAPQuery.fetch(self,additional_filter_str)
        for k in out_data.keys():
            cluster_id=k.split("Mds-Vo-name=",1)[1].split(",",1)[0]
            out_data[k]['Mds-Vo-name']=[cluster_id,'local']

        return out_data
        
    def filterStatus(self, usable=True):
        old_data=self.stored_data
        if old_data==None:
            raise RuntimeError, "No data loaded"
        new_data={}
        for k in old_data.keys():
            if (old_data[k]['GlueCEStateStatus'][0]=='Production')==usable:
                new_data[k]=old_data[k]
        self.stored_data=new_data

