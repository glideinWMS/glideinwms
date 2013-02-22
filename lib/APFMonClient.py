import json
import urllib2
from glideinwms.factory import glideFactoryConfig
from glideinwms.lib import logSupport
import traceback
import sys

class APFMonClient:
    def __init__(self, BaseUrl='http://cms-xen43.fnal.gov/factory/',
                 APFMonUrl="http://cms-xen45.fnal.gov:8000/api/"):
        config = glideFactoryConfig.GlideinDescript()
        self._factoryId=config.data['FactoryName']
        self._Tag=config.data['GlideinName']
        self._APFMonUrl = APFMonUrl
        # todo: add config for these
        self._Owner="CMS"
        self._BaseUrl = BaseUrl
        self._Email="burt@fnal.gov"

        import glideinwms.factory.glideFactoryLib as gfl
        self.log_files = gfl.log_files

    def registerFactory(self):
        self.log_files.logActivity("Registering factory to %s" % self._APFMonUrl)
        attrs = {
            'url' : self._BaseUrl,
            'email' : self._Email,
            'version' : self._Tag,
            'type': 'glideinWMS' # choices: glideinWMS or AutoPyFactory
            }

        data = json.write(attrs)
        url = self._APFMonUrl + "factories/%s" % self._factoryId
        try:
            _ = self._httpPut(url, data)
        except:
            self.log_files.logError("Unable to register factory to %s" % self._APFMonUrl)

    def _httpPut(self, url, data):
        # urllib only does GET and POST
        # from http://stackoverflow.com/questions/111945/is-there-any-way-to-do-http-put-in-python
        opener = urllib2.build_opener(urllib2.HTTPHandler)
        request = urllib2.Request(url, data)
        request.get_method = lambda: 'PUT'
        result = opener.open(request)
        return result

    def sendJobIDs(self, entry, jobslist):
        # jobslist is list of (clusterId, ProcId) tuples
        self.log_files.logActivity("in sendJobIDs")
        entry = "entry_%s" % entry
        apfJobsList = [{'cid': "job.%s.%s" % (clusterId, procId),
                        'label': entry,
                        'factory': self._factoryId,
                        'queue': entry,
                        'localqueue': entry, # maybe schedd?
                        'nick': entry}
                       for clusterId, procId in jobslist]

        data = json.write(apfJobsList)
        self.log_files.logActivity("Sending %s to APF" % data)
        url = self._APFMonUrl + "jobs"

        try:
            _ = self._httpPut(url, data)
        except urllib2.HTTPError, h:
            if h.code == 201:
                self.log_files.logActivity("sendJobIDs success")
            else:
                raise h
        except Exception, e:
            self.log_files.logError("sendJobIDs failure")
            tb = traceback.format_exception(sys.exc_info()[0],sys.exc_info()[1],
                                            sys.exc_info()[2])
            self.log_files.logError(tb)
