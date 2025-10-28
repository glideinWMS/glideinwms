#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""
Project:
    glideinWMS
Purpose:
    unit test for factory/tools/OSG_autoconf.py
Author:
    Marco Mascheroni, marco.mascheroni@cern.ch
"""


import copy
import unittest

import xmlrunner

# from unittest.mock import patch


try:
    from glideinwms.unittests.unittest_utils import TestImportError
except ImportError:

    class TestImportError(Exception):
        pass


try:
    from glideinwms.factory.tools.OSG_autoconf import create_missing_file_internal, get_information_internal, get_pilot
    from glideinwms.lib.config_util import BEST_FIT_TAG
except ImportError as err:
    raise TestImportError(str(err))


class TestOSGAutoconf(unittest.TestCase):
    def setUp(self):
        self.maxDiff = 1000000000
        self.input_info = {
            "Name": "hosted-ce36.opensciencegrid.org",
            "OSG_Resource": "AMNH-HEL",
            "OSG_ResourceGroup": "AMNH",
            "OSG_ResourceCatalog": [{"Memory": 65536, "MaxWallTime": 2880, "CPUs": 8}],
        }
        self.out_data = {
            "AMNH": {
                "hosted-ce36.opensciencegrid.org": {
                    BEST_FIT_TAG: {
                        "DEFAULT_ENTRY": {
                            "gridtype": "condor",
                            "attrs": {
                                "GLIDEIN_Site": {"value": "AMNH"},
                                "GLIDEIN_CPUS": {"value": 8},
                                "GLIDEIN_Max_Walltime": {"value": 171000},
                                "GLIDEIN_ResourceName": {"value": "AMNH"},
                                "GLIDEIN_MaxMemMBs": {"value": 65536},
                            },
                            "submit_attrs": {"+maxWallTime": 2880, "+xcount": 8, "+maxMemory": 65536},
                        }
                    }
                }
            }
        }
        self.res = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_Site": {"value": "AMNH"},
                "GLIDEIN_ResourceName": {
                    "value": {
                        "Name": "hosted-ce36.opensciencegrid.org",
                        "OSG_Resource": "AMNH-HEL",
                        "OSG_ResourceGroup": "AMNH",
                        "OSG_ResourceCatalog": [{"Memory": 65536, "MaxWallTime": 2880, "CPUs": 8}],
                    }
                },
            },
            "submit_attrs": {},
        }

    def test_get_pilot(self):
        self.assertEqual(get_pilot("AMNH", self.input_info, "SLURM", self.out_data), self.res)
        self.res["work_dir"] = "Condor"
        self.assertEqual(get_pilot("AMNH", self.input_info, "CONDOR", self.out_data), self.res)

    def test_get_information_internal(self):
        # The infotmation as retrieved from the OSG_Collector
        info = [
            {
                "Name": "hosted-ce36.opensciencegrid.org",
                "OSG_Resource": "AMNH-HEL",  # Currently not used, an attribute will be added in the future
                "OSG_ResourceGroup": "AMNH",
                "OSG_ResourceCatalog": [{"Memory": 65536, "MaxWallTime": 2880, "CPUs": 8}],
            }
        ]
        expected_out = {
            "AMNH": {
                "hosted-ce36.opensciencegrid.org": {
                    BEST_FIT_TAG: {
                        "DEFAULT_ENTRY": {
                            "gridtype": "condor",
                            "attrs": {
                                "GLIDEIN_Site": {"value": "AMNH"},
                                "GLIDEIN_CPUS": {"value": 8},
                                "GLIDEIN_Max_Walltime": {"value": 171000},
                                "GLIDEIN_ResourceName": {"value": "AMNH-HEL"},
                                "GLIDEIN_MaxMemMBs": {"value": 65536},
                            },
                            "submit_attrs": {"+maxWallTime": 2880, "+xcount": 8, "+maxMemory": 65536},
                        }
                    }
                }
            }
        }
        # Basic check
        self.assertEqual(get_information_internal(info), expected_out)

        # Add a different CE, same resource group
        info.append(
            {
                "Name": "hosted-ce37.opensciencegrid.org",
                "OSG_Resource": "AMNH-ARES",
                "OSG_ResourceGroup": "AMNH",
                "OSG_ResourceCatalog": [{"Memory": 32768, "MaxWallTime": 1440, "CPUs": 4}],
            }
        )
        expected_out["AMNH"]["hosted-ce37.opensciencegrid.org"] = {
            BEST_FIT_TAG: {
                "DEFAULT_ENTRY": {
                    "gridtype": "condor",
                    "attrs": {
                        "GLIDEIN_Site": {"value": "AMNH"},
                        "GLIDEIN_CPUS": {"value": 4},
                        "GLIDEIN_Max_Walltime": {"value": 84600},
                        "GLIDEIN_ResourceName": {"value": "AMNH-ARES"},
                        "GLIDEIN_MaxMemMBs": {"value": 32768},
                    },
                    "submit_attrs": {"+maxWallTime": 1440, "+xcount": 4, "+maxMemory": 32768},
                }
            }
        }
        self.assertEqual(get_information_internal(info), expected_out)

        # Add another resource to the OSG_ResourceCatalog for ce37. This is to check "Best Fit pilot" algorithm
        info[1]["OSG_ResourceCatalog"].append({"Memory": 2000, "MaxWallTime": 1000, "CPUs": 6})
        expected_out["AMNH"]["hosted-ce37.opensciencegrid.org"][BEST_FIT_TAG]["DEFAULT_ENTRY"]["attrs"][
            "GLIDEIN_MaxMemMBs"
        ] = {
            "value": 2000
        }  # The minimum memory
        expected_out["AMNH"]["hosted-ce37.opensciencegrid.org"][BEST_FIT_TAG]["DEFAULT_ENTRY"]["attrs"][
            "GLIDEIN_Max_Walltime"
        ] = {
            "value": 1000 * 60 - 1800
        }  # The minimum walltime
        expected_out["AMNH"]["hosted-ce37.opensciencegrid.org"][BEST_FIT_TAG]["DEFAULT_ENTRY"]["attrs"][
            "GLIDEIN_CPUS"
        ] = {
            "value": 2
        }  # The GCD (greater common divisor)
        expected_out["AMNH"]["hosted-ce37.opensciencegrid.org"][BEST_FIT_TAG]["DEFAULT_ENTRY"]["submit_attrs"] = {
            "+maxWallTime": 1000,
            "+xcount": 2,
            "+maxMemory": 2000,
        }
        self.assertEqual(get_information_internal(info), expected_out)

        # Now check the "IsPilotEntry = true" case
        info.append(
            {
                "Name": "hosted-ce29.grid.uchicago.edu",
                "OSG_Resource": "OSG_US_LSU_QB2",
                "OSG_ResourceGroup": "LSU",
                "OSG_ResourceCatalog": [
                    {
                        "WholeNode": False,
                        "MaxPilots": 1000,
                        "IsPilotEntry": True,
                        "RequireSingularity": True,
                        "SendTests": True,
                        "CPUs": 1,
                        "AllowedVOs": ["icecube"],
                        "MaxWallTime": 2880,
                        "Memory": 8192,
                        "GPUs": 2,
                        "Name": "GPU",
                    },
                    {
                        "CPUs": 20,
                        "AllowedVOs": ["ligo"],
                        "MaxWallTime": 1440,
                        "Memory": 65536,
                    },  # No IsPilotEntry, ignored
                    {
                        "WholeNode": True,
                        "Name": "WholeNode",
                        "IsPilotEntry": True,
                        "MaxPilots": 1000,
                        "SendTests": True,
                        "RequireSingularity": True,
                        "AllowedVOs": ["atlas"],
                        "MaxWallTime": 1440,
                    },
                    {
                        "WholeNode": True,
                        "Name": "WholeNodeCpus",
                        "IsPilotEntry": True,
                        "MaxPilots": 1000,
                        "SendTests": True,
                        "RequireSingularity": True,
                        "AllowedVOs": ["atlas"],
                        "MaxWallTime": 1440,
                        "EstimatedCPUs": 48,
                    },
                    {
                        "WholeNode": False,
                        "MaxPilots": 1000,
                        "IsPilotEntry": True,
                        "RequireSingularity": False,
                        "SendTests": True,
                        "CPUs": 8,
                        "AllowedVOs": ["osg", "cms"],
                        "MaxWallTime": 1440,
                        "Memory": 32768,
                        "OS": "rhel6",
                        "Name": "default",
                    },
                ],
            }
        )
        expected_out["LSU"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["GPU"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["GPU"]["DEFAULT_ENTRY"] = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_ResourceName": {"value": "OSG_US_LSU_QB2"},
                "GLIDEIN_Site": {"value": "LSU"},
                "GLIDEIN_MaxMemMBs": {"value": 8192},
                "GLIDEIN_Max_Walltime": {"value": 171000},
                "GLIDEIN_CPUS": {"value": 1},
                "GLIDEIN_Supported_VOs": {"value": "IceCubeGPU"},
            },
            "submit_attrs": {"+maxWallTime": 2880, "+xcount": 1, "+maxMemory": 8192, "Request_GPUs": 2},
            "limits": {"entry": {"glideins": 1000}},
        }
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["WholeNode"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["WholeNode"]["DEFAULT_ENTRY"] = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_ResourceName": {"value": "OSG_US_LSU_QB2"},
                "GLIDEIN_Site": {"value": "LSU"},
                "GLIDEIN_Max_Walltime": {"value": 84600},
                "GLIDEIN_Supported_VOs": {"value": "ATLAS"},
            },
            "submit_attrs": {"+WantWholeNode": True, "+maxWallTime": 1440},
            "limits": {"entry": {"glideins": 1000}},
        }
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["WholeNodeCpus"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["WholeNodeCpus"]["DEFAULT_ENTRY"] = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_ResourceName": {"value": "OSG_US_LSU_QB2"},
                "GLIDEIN_Site": {"value": "LSU"},
                "GLIDEIN_Max_Walltime": {"value": 84600},
                "GLIDEIN_Supported_VOs": {"value": "ATLAS"},
                "GLIDEIN_ESTIMATED_CPUS": {"value": 48},
            },
            "submit_attrs": {"+WantWholeNode": True, "+maxWallTime": 1440},
            "limits": {"entry": {"glideins": 1000}},
        }
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["default"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["default"]["DEFAULT_ENTRY"] = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_ResourceName": {"value": "OSG_US_LSU_QB2"},
                "GLIDEIN_Site": {"value": "LSU"},
                "GLIDEIN_MaxMemMBs": {"value": 32768},
                "GLIDEIN_Max_Walltime": {"value": 84600},
                "GLIDEIN_CPUS": {"value": 8},
                "GLIDEIN_Supported_VOs": {"value": "CMS,OSGVO"},
                "GLIDEIN_REQUIRED_OS": {"value": "rhel6"},
            },
            "submit_attrs": {"+maxWallTime": 1440, "+xcount": 8, "+maxMemory": 32768},
            "limits": {"entry": {"glideins": 1000}},
        }
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["BEST_FIT"] = {}
        expected_out["LSU"]["hosted-ce29.grid.uchicago.edu"]["BEST_FIT"]["DEFAULT_ENTRY"] = {
            "gridtype": "condor",
            "attrs": {
                "GLIDEIN_CPUS": {"value": 20},
                "GLIDEIN_MaxMemMBs": {"value": 65536},
                "GLIDEIN_Max_Walltime": {"value": 84600},
                "GLIDEIN_ResourceName": {"value": "OSG_US_LSU_QB2"},
                "GLIDEIN_Site": {"value": "LSU"},
                "GLIDEIN_Supported_VOs": {"value": "LIGO"},
            },
            "submit_attrs": {"+maxMemory": 65536, "+maxWallTime": 1440, "+xcount": 20},
        }
        self.assertEqual(get_information_internal(info), expected_out)

    def test_create_missing_file_internal(self):
        # 2 sites, three CEs
        info = {
            "SITE_NAME": {
                "ce01.sitename.edu": {
                    BEST_FIT_TAG: {
                        "DEFAULT_ENTRY": {
                            "gridtype": "condor",
                            "attrs": {
                                "GLIDEIN_Site": {"value": "SITE_NAME"},
                                "GLIDEIN_CPUS": {"value": 8},
                                "GLIDEIN_ResourceName": {"value": "SITE_NAME"},
                                "GLIDEIN_Supported_VOs": {"value": "OSGVO,DUNE,CMS"},
                                "GLIDEIN_MaxMemMBs": {"value": 16000},
                                "GLIDEIN_Max_Walltime": {"value": 256200},
                            },
                            "submit_attrs": {"+maxMemory": 16000, "+maxWallTime": 4300, "+xcount": 8},
                        }
                    }
                },
                "ce02.sitename.edu": {
                    BEST_FIT_TAG: {
                        "DEFAULT_ENTRY": {
                            "gridtype": "condor",
                            "attrs": {
                                "GLIDEIN_Site": {"value": "SITE_NAME"},
                                "GLIDEIN_CPUS": {"value": 1},
                                "GLIDEIN_ResourceName": {"value": "SITE_NAME"},
                                "GLIDEIN_Supported_VOs": {"value": "CMS"},
                                "GLIDEIN_MaxMemMBs": {"value": 3968},
                                "GLIDEIN_Max_Walltime": {"value": 256200},
                            },
                            "submit_attrs": {"+maxMemory": 3968, "+maxWallTime": 4300, "+xcount": 1},
                        }
                    }
                },
            },
            "ANOTHER_SITE": {
                "ce01.othersite.edu": {
                    BEST_FIT_TAG: {
                        "DEFAULT_ENTRY": {
                            "gridtype": "condor",
                            "attrs": {
                                "GLIDEIN_Site": {"value": "OTHER_NAME"},
                                "GLIDEIN_CPUS": {"value": 4},
                                "GLIDEIN_ResourceName": {"value": "OTHER_NAME"},
                                "GLIDEIN_Supported_VOs": {"value": "OSGVO,DUNE,CMS"},
                                "GLIDEIN_MaxMemMBs": {"value": 8000},
                                "GLIDEIN_Max_Walltime": {"value": 84600},
                            },
                            "submit_attrs": {"+maxMemory": 8000, "+maxWallTime": 4300, "+xcount": 4},
                        }
                    }
                }
            },
        }

        missing_info = {}  # Info from the old missing.yml file
        osg_info = copy.deepcopy(info)  # Information as in the old OSG.yml file (old=from the previous run)
        whitelist_info = {"ANOTHER_SITE": {"ce01.othersite.edu": {}}}  # The operator's override file
        osg_collector_data = copy.deepcopy(info)  # Information from the OSG collector. Just fetched.
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # One of the site is now missing from the collector data
        del osg_collector_data["ANOTHER_SITE"]
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["ANOTHER_SITE"],
            info["ANOTHER_SITE"],
        )

        # Now what happens if it is also missing from the old data?
        del osg_info["ANOTHER_SITE"]
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Now let's pretend it was in the missing yaml
        missing_info["ANOTHER_SITE"] = copy.deepcopy(info["ANOTHER_SITE"])
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["ANOTHER_SITE"],
            info["ANOTHER_SITE"],
        )

        # And if it is both in the missing file and the collector (CE is back up)? Missing should be empty.
        osg_collector_data = copy.deepcopy(info)  # Information from the OSG collector. Just fetched.
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Let's test a bit what happens when just a CE is missing
        missing_info = {}
        osg_info = copy.deepcopy(info)  # Information as in the old OSG.yml file (old=from the previous run)
        whitelist_info = {"SITE_NAME": {"ce01.sitename.edu": {}}}
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # CE missing from the collector: Restored from old OSG YAML
        del osg_collector_data["SITE_NAME"]["ce01.sitename.edu"]
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["SITE_NAME"][
                "ce01.sitename.edu"
            ],
            info["SITE_NAME"]["ce01.sitename.edu"],
        )

        # CE missing from the collector and can't be restored
        del osg_info["SITE_NAME"]["ce01.sitename.edu"]
        self.assertEqual(create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data), {})

        # Now let's pretend it was in the missing yaml
        missing_info.setdefault("SITE_NAME", {})["ce01.sitename.edu"] = copy.deepcopy(
            info["SITE_NAME"]["ce01.sitename.edu"]
        )
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["SITE_NAME"][
                "ce01.sitename.edu"
            ],
            info["SITE_NAME"]["ce01.sitename.edu"],
        )

        # The WHITELIST YAML file is now containing ce02 as well, which is now missing from the OSG collector
        whitelist_info["SITE_NAME"]["ce02.sitename.edu"] = {}
        del osg_collector_data["SITE_NAME"]["ce02.sitename.edu"]
        # restored from the OSG YAML
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["SITE_NAME"],
            info["SITE_NAME"],
        )
        # restored from the missing file
        del osg_info["SITE_NAME"]["ce02.sitename.edu"]
        missing_info["SITE_NAME"]["ce02.sitename.edu"] = copy.deepcopy(info["SITE_NAME"]["ce02.sitename.edu"])
        self.assertEqual(
            create_missing_file_internal(missing_info, osg_info, whitelist_info, osg_collector_data)["SITE_NAME"],
            info["SITE_NAME"],
        )

        # The following lines need python3


#       with patch('sys.stdout', new = StringIO()) as fake_out:
#           self.assertEqual(fake_out.getvalue(), expected_out)


if __name__ == "__main__":
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output="unittests-reports"))
