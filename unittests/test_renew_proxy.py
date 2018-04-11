#!/bin/env python

from frontend import gwms_renew_proxies as proxy
import unittest

class TestVo(unittest.TestCase):

    def assertVomsAttr(self, vo, vo_name, cmd):
        self.assertEqual(vo.fqan, "/%s/%s" % (vo_name, cmd))
        self.assertEqual(vo.voms, '%s:%s' % (vo_name, cmd))

    def test_fqan_vo_prefix(self):
        vo_name = 'glideinwms'
        cmd = 'Role=NULL/Capability=NULL'
        vo = proxy.VO(vo_name, '/%s/%s' % (vo_name, cmd))
        self.assertVomsAttr(vo, vo_name, cmd)

    def test_fqan_without_vo_prefix(self):
        vo_name = 'glideinwms'
        cmd = 'Role=NULL/Capability=NULL'
        vo = proxy.VO(vo_name, '/' + cmd)
        self.assertVomsAttr(vo, vo_name, cmd)

    def test_fqan_malformed(self):
        vo_name = 'glideinwms'
        self.assertRaises(ValueError, proxy.VO, vo_name, vo_name)

if __name__ == '__main__':
    unittest.main()
