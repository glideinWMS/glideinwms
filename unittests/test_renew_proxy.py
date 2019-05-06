#!/usr/bin/env python

import re
import unittest2 as unittest
import xmlrunner

from glideinwms.frontend import gwms_renew_proxies as proxy

VOMSES = '''
"GLOW" "glow-voms.cs.wisc.edu" "15001" "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=glow-voms.cs.wisc.edu" "GLOW"
"osg" "voms.grid.iu.edu" "15027" "/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=voms.grid.iu.edu" "osg"
"osg" "voms1.opensciencegrid.org" "15027" "/DC=org/DC=incommon/C=US/ST=WI/L=Madison/O=University of Wisconsin-Madison/OU=OCIS/CN=voms1.opensciencegrid.org" "osg"
"xenon.biggrid.nl" "voms.grid.sara.nl" "30008" "/O=dutchgrid/O=hosts/OU=sara.nl/CN=voms.grid.sara.nl" "xenon.biggrid.nl"
'''


class TestUtils(unittest.TestCase):
    """Test utility functions in gwms_renew_proxies
    """

    def test_parse_vomses(self):
        name_map, uri_map = proxy.parse_vomses(VOMSES)
        for nocap, canonical in [('osg', 'osg'), ('glow', 'GLOW'), ('xenon.biggrid.nl', 'xenon.biggrid.nl')]:
            self.assertEqual(name_map[nocap], canonical)
        for dn, uri in [('/O=dutchgrid/O=hosts/OU=sara.nl/CN=voms.grid.sara.nl',
                         'voms.grid.sara.nl:30008'),
                        ('/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=voms.grid.iu.edu',
                         'voms.grid.iu.edu:15027'),
                        ('/DC=org/DC=incommon/C=US/ST=WI/L=Madison/O=University of Wisconsin-Madison/OU=OCIS/CN=voms1.opensciencegrid.org',
                         'voms1.opensciencegrid.org:15027'),
                        ('/DC=org/DC=opensciencegrid/O=Open Science Grid/OU=Services/CN=glow-voms.cs.wisc.edu',
                         'glow-voms.cs.wisc.edu:15001')]:
            self.assertEqual(uri_map[dn], uri)

class TestVo(unittest.TestCase):

    def assertVomsAttr(self, vo, vo_name, cmd):
        self.assertEqual(vo.fqan, '/%s%s' % (vo_name, cmd))
        self.assertEqual(vo.voms, '%s:/%s%s' % (vo_name, vo_name, cmd))

    def test_fqan_vo_prefix(self):
        vo_name = 'glideinwms'
        cmd = '/Role=NULL/Capability=NULL'
        vo = proxy.VO(vo_name, '/%s%s' % (vo_name, cmd))
        self.assertVomsAttr(vo, vo_name, cmd)

    def test_fqan_without_vo_prefix(self):
        vo_name = 'glideinwms'
        cmd = '/Role=NULL/Capability=NULL'
        vo = proxy.VO(vo_name, cmd)
        self.assertVomsAttr(vo, vo_name, cmd)

    def test_fqan_malformed(self):
        vo_name = 'glideinwms'
        self.assertRaises(ValueError, proxy.VO, vo_name, vo_name)


if __name__ == '__main__':
    ofl = 'unittests-reports'
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output=ofl))
