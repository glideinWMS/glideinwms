#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

#
# Project:
#   glideinWMS
#
# Description:
#   unit test for factory/glideFactoryLogParser.py
#
# Author:
#   Marco Mascheroni
#


import unittest

import xmlrunner

from glideinwms.factory.glideFactoryLogParser import extractLogData


class TestUtils(unittest.TestCase):
    def test_extractLogData(self):
        out = extractLogData("fixtures/factory/log/client/glideFactoryLogParser_glidein_stdout.out")
        # Expected output is:
        # {'condor_started': 1, 'validation_duration': 63, 'glidein_duration': 8376, 'activations_claims': 34, 'condor_duration': 8307, 'stats': {}}
        self.assertEquals(out['condor_started'], 1)
        self.assertEquals(out['validation_duration'], 63)
        self.assertEquals(out['glidein_duration'], 8376)
        self.assertEquals(out['activations_claims'], 34)
        self.assertEquals(out['condor_duration'], 8307)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
