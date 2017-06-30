#
# Project:
#   glideinWMS
#
# File Version: 
#
# Description:
#   This module implements classes to query the ldap server
#   and manipulate the result
#
# Author:
#   Igor Sfiligoi (Jul 22nd 2008)
#

import ldap #@UnresolvedImport
import re

class LDAPQuery:
    def __init__(self,
                 ldap_url,ldap_port, # where to find LDAP server
                 base,filter_str):   # what to read
        self.ldap_url = ldap_url
        self.ldap_port = ldap_port
        self.base = base
        self.filter_str = filter_str
        self.stored_data = None

    # load info in internal storage
    def load(self, additional_filter_str=None):
        self.stored_data = self.fetch(additional_filter_str)

    # rpint out the internal storage
    def fetchStored(self):
        return self.stored_data

    # load from LDAP and print out
    # do not store locally
    def fetch(self, additional_filter_str=None):
        if additional_filter_str is None:
            additional_filter_str = ""

        filter_str = "(%s%s)" % (self.filter_str, additional_filter_str)

        ldap_obj = ldap.open(self.ldap_url, self.ldap_port)
        ldap_obj.simple_bind('', '')
        try:
            bdii_data = ldap_obj.search_s(self.base, ldap.SCOPE_SUBTREE,
                                          filter_str)
        except ldap.FILTER_ERROR as e:
            raise ValueError, "LDAP filter error for '%s': %s" % (filter_str, e)
        del ldap_obj

        out_data = {}
        for elarr in bdii_data:
            el1, el2 = elarr
            if el1 in out_data:
                raise RuntimeError, "Dublicate element found: " + el1
            out_data[el1] = el2
            
        del bdii_data
        return out_data
        
class BDIICEQuery(LDAPQuery):
    def __init__(self,
                 bdii_url,bdii_port=2170,     # where to find LDAP server
                 additional_filter_str=None,base_string="Mds-vo-name=local,o=grid"): # what to read
        if additional_filter_str is None:
            additional_filter_str=""
            
        filter_str = "&(GlueCEInfoContactString=*)%s" % additional_filter_str

        LDAPQuery.__init__(self,bdii_url,bdii_port,
                           base_string,filter_str)

    def fetch(self, additional_filter_str=None):
        out_data = LDAPQuery.fetch(self, additional_filter_str)
        for k in out_data.keys():
            cluster_id = k.split("Mds-Vo-name=", 1)[1].split(",", 1)[0]
            out_data[k]['Mds-Vo-name'] = [cluster_id, 'local']

        return out_data
        
    def filterStatus(self, usable=True):
        old_data = self.stored_data
        if old_data is None:
            raise RuntimeError, "No data loaded"
        new_data = {}
        for k in old_data.keys():
            if (old_data[k]['GlueCEStateStatus'][0] == 'Production') == usable:
                new_data[k] = old_data[k]
        self.stored_data = new_data


class SearchBDII:
    def __init__(self,url,port=None,VO=None,CE=None,
                 GlueCEUniqueID=None,ldapSearchStr=None,searchStr=None):
        
        #Store Initialization Variables
        self.bdiiUrl=url
        self.port=port
        self.VO=VO
        self.CE=CE
        self.GlueCEUniqueID=GlueCEUniqueID
        self.ldapSearchStr=ldapSearchStr
        self.searchStr=searchStr
        
        #Initial Storage Variables
        self.bdiiData=None

        #Run Initializing Functions
        self.query_bdii()
        self.search_bdii_data()

    def query_bdii(self):
        """ Retrieve the information from BDII. Apply appropriate ldap filter strings.
        """
        selectionStr=""
        baseStr="Mds-vo-name=local,o=grid"
        if self.VO:
            selectionStr=selectionStr+"(|(GlueCEAccessControlBaseRule=VO:" + self.VO + ")(GlueCEAccessControlBaseRule=VOMS:/" + self.VO + "/Role=pilot))"

        if self.CE:
            selectionStr=selectionStr+"(GlueCEInfoContactString="+self.CE+")"

        if self.GlueCEUniqueID:
            baseStr=self.GlueCEUniqueID
        if self.ldapSearchStr:
            selectionStr=selectionStr+self.ldapSearchStr
        if self.port:
            bdii_obj=BDIICEQuery(self.bdiiUrl,bdii_port=int(self.port),additional_filter_str=selectionStr,base_string=baseStr)
        else:    
            bdii_obj=BDIICEQuery(self.bdiiUrl,additional_filter_str=selectionStr,base_string=baseStr)
        bdii_obj.load()
        self.bdiiData=bdii_obj.fetchStored()
        del bdii_obj
    

    def search_bdii_data(self):
        """searches the base string of each retrieved entry for designated string.
        """
   
        dict={}
        ### only modify bdiiData if there is a search criteria
        if self.searchStr:
            found=False
            for key in self.bdiiData.keys():
                if self.searchStr in key:
                    dict[key]=self.bdiiData[key]
                    found=True
            if found==False:
                print "\n No entry found for search term \""+self.searchStr+"\" .\n"
            self.bdiiData.clear()
            self.bdiiData=dict
        

    def return_bdii_data(self):
        """Returns a dictionary of bdii information
        """
        return self.bdiiData


    def display_bdii_data(self,file=None):
        """Display entries.
        Args (file=None): file is the specified output file name. If blank, output is on command line.
        """
        if file:
            try:
                outFile=open(file,'w')
                for key in self.bdiiData.keys():
                    outFile.write("\n%s\n%s\n\n"%(key,self.bdiiData[key]))
            except:
                print "Error opening or closing specified file."
        else:
            for key in self.bdiiData.keys():
                print "\n"
                print key
                print "\n"
                print self.bdiiData[key]
                print "\n\n"

class BdiiLdap:
   def __init__(self, bdii="uscmsbd2.fnal.gov"):
       self.bdii = bdii
       self.DEBUG = 0
       self.map_source = {'ceList': [], 'bdii': ''}
       self.ce_to_cluster_map = {}
       self.cluster_to_site_map = {}

   def runldapquery(self, filter, attribute):
       bdii = self.bdii
       if self.DEBUG:
           print "runldapquery ["+bdii+"]", filter, attribute
       attribute = attribute.split(' ')
       filter = filter.strip()
       filter = filter.lstrip("'").rstrip("'")

       bdiiuri = 'ldap://' + bdii + ':2170'
       l = ldap.initialize(bdiiuri)

       l.simple_bind_s('', '')

       base = "o=grid"
#        base = "mds-vo-name=USCMS-FNAL-WC1,mds-vo-name=local,o=grid"
       scope = ldap.SCOPE_SUBTREE
       timeout = 0
       result_set = []
       filter = filter.strip("'")

       try:
           result_id = l.search(base, scope, filter, attribute)
           while True:
               result_type, result_data = l.result(result_id, timeout)
               if (result_data == []):
                   break
               else:
                   if result_type == ldap.RES_SEARCH_ENTRY:
                       result_set.append(result_data)

       except ldap.LDAPError as error_message:
           print error_message
           raise

       return result_set

   def clearMaps(self):
       self.map_source['ceList'] = []
       self.map_source['bdii'] = ''
       self.ce_to_cluster_map.clear()
       self.cluster_to_site_map.clear()

   def generateMaps(self, ceList=[]):
       """
       Generate maps of CE to Cluster and Cluster to Site as 
       ce_to_cluster_map, cluster_to_site_map

       ceList: list of GlueCEUniqueIDs
       bdii: BDII instance to query

       If ceList is an empty list, generate a map for all CEs.
       """

       if self.bdii == self.map_source['bdii']: # check for cached maps
           if (not ceList and self.map_source['ceList'] == 'ALL') or \
              (ceList and self.map_source['ceList'] == ceList):
               return

       self.clearMaps()

       if ceList:
           query = self.buildOrQuery('GlueCEUniqueID', ceList)
       else:
           query = '(GlueCEUniqueID=*)'

       pout = self.runldapquery(query, 'GlueCEUniqueID GlueForeignKey')

       r = re.compile('^GlueClusterUniqueID\s*=\s*(.*)')
       for x in pout:
           host = x[0][1]['GlueCEUniqueID'][0]
           clusterid = x[0][1]['GlueForeignKey'][0]
           m = r.match(clusterid)
           if m: self.ce_to_cluster_map[host] = m.groups()[0]

       query = "(&(objectClass=GlueCluster)"
       if ceList:
           query += self.buildOrQuery('GlueClusterUniqueID', self.ce_to_cluster_map.values())
       else:
           query += '(GlueClusterUniqueID=*)'
       query += ")"

       pout = self.runldapquery(query, 'GlueClusterUniqueID GlueForeignKey')
       r = re.compile('^GlueSiteUniqueID=(.*)')
       for x in pout:
           cluster = x[0][1]['GlueClusterUniqueID'][0]
           foreign_keys = x[0][1]['GlueForeignKey']
           for foreign_key in foreign_keys:
               m = r.match(foreign_key)
               if m:
                   site = m.groups()[0]
                   self.cluster_to_site_map[cluster] = site

       # cache the list sources
       if ceList:
           self.map_source['ceList'] = ceList
       else:
           self.map_source['ceList'] = 'ALL'
       self.map_source['bdii'] = self.bdii

       if (self.DEBUG): print 40*'*', 'exit generateMaps', 40*'*'

   def buildOrQuery(self, gluekey, list):
       """
       Returns a nugget of LDAP requesting the OR of all items
       of the list equal to the gluekey
       """

       query = "(|"
       for x in list:
           query += "(%s=%s)" % (gluekey, x)
       query += ")"
       return query       
             
        
