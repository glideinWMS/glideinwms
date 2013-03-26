import glideinwms.externals.simplejson as json
import urllib2
import urlparse
from glideinwms.factory import glideFactoryConfig
from glideinwms.lib import logSupport
import traceback
import sys

class APFMonClient:
    def __init__(self, BaseUrl='http://cms-xen43.fnal.gov/factory/',
                 APFMonUrl="http://cms-xen45.fnal.gov:8000/api/",
                 SSLPort=443):

        parsedUrl = urlparse.urlparse(BaseUrl)
        netloc = parsedUrl[1].split(":")[0] # remove port
        path = parsedUrl[2]

        self._BaseUrl = "https://%s:%d%s" % (netloc, SSLPort, path)

        config = glideFactoryConfig.GlideinDescript()
        self._factoryId=config.data['FactoryName']
        self._Tag=config.data['GlideinName']
        self._APFMonUrl = APFMonUrl
        # todo: add config for these
        self._Owner="CMS"
        self._Email="burt@fnal.gov"

    def registerFactory(self):
        logSupport.log.info("Registering factory to %s" % self._APFMonUrl)

        attrs = {
            'url' : self._BaseUrl,
            'email' : self._Email,
            'version' : self._Tag,
            'type': 'glideinWMS' # choices: glideinWMS or AutoPyFactory
            }

        data = json.dumps(attrs)
        url = self._APFMonUrl + "factories/%s" % self._factoryId
        try:
            _ = self._httpPut(url, data)
        except:
            logSupport.log.error("Unable to register factory to %s" % self._APFMonUrl)

    def _httpPut(self, url, data):
        # urllib only does GET and POST
        # from http://stackoverflow.com/questions/111945/is-there-any-way-to-do-http-put-in-python
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(url, data)
        request.get_method = lambda: 'PUT'
        result = opener.open(request)
        return result

    def sendJobIDs(self, factory_name, entry, fe_username, jobslist):
        # jobslist is list of (clusterId, ProcId) tuples
        logSupport.log.info("in sendJobIDs")
        entry = "%s:%s:entry_%s" % (factory_name, fe_username, entry)
        apfJobsList = [{'cid': "job.%s.%s" % (clusterId, procId),
                        'label': entry,
                        'factory': self._factoryId,
                        'queue': entry,
                        'localqueue': entry, # maybe schedd?
                        'nick': entry}
                       for clusterId, procId in jobslist]

        data = json.dumps(apfJobsList)
        logSupport.log.info("Sending %s to APF" % data)
        url = self._APFMonUrl + "jobs"

        try:
            _ = self._httpPut(url, data)
        except urllib2.HTTPError, h:
            if h.code == 201:
                logSupport.log.info("sendJobIDs success")
            else:
                raise h
        except Exception, e:
            logSupport.log.exception("sendJobIDs failure")

