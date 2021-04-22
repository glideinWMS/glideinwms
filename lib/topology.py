# TODO Taken from TopologyMatch.py in osg-flock; factor stuff out and move into a common repo
from __future__ import print_function

import logging
import re
import sys
import time
import xml.etree.ElementTree as ET


if sys.version_info[0] >= 3:
    from urllib.request import urlopen  # Python 3
else:
    from urllib2 import urlopen  # Python 2

try:
    from typing import Dict, List, Optional, Tuple, Union  # Python 3 or Python 2 + typing module
except ImportError:
    pass  # only used for linting


#
#
# Public
#
#


TOPOLOGY = "https://topology.opensciencegrid.org"
PROJECTS_CACHE_LIFETIME = 300.0


class TopologyData(object):
    def __init__(self, topology_host=TOPOLOGY, cache_lifetime=PROJECTS_CACHE_LIFETIME):
        self.topology_host = topology_host
        self.projects_cache = _CachedData(cache_lifetime=cache_lifetime, retry_delay=30.0)

    def get_projects(self):  # type: () -> Optional[ET.Element]
        if not self.projects_cache.should_update():
            _log.debug("Cache lifetime / retry delay not expired, returning cached data (if any)")
            return self.projects_cache.data

        try:
            # Python 2 does not have a context manager for urlopen
            response = urlopen(self.topology_host + "/miscproject/xml")
            try:
                xml_text = response.read()  # type: Union[bytes, str]
            finally:
                response.close()
        except EnvironmentError as err:
            _log.warning("Topology projects query failed: %s", err)
            self.projects_cache.try_again()
            if self.projects_cache.data:
                _log.debug("Returning cached data")
                return self.projects_cache.data
            else:
                _log.error("Failed to update and no cached data")
                return None

        if not xml_text:
            _log.warning("Topology projects query returned no data")
            self.projects_cache.try_again()
            if self.projects_cache.data:
                _log.debug("Returning cached data")
                return self.projects_cache.data
            else:
                _log.error("Failed to update and no cached data")
                return None

        try:
            element = ET.fromstring(xml_text)  # fromstring accepts both bytes and str
        except (ET.ParseError, UnicodeDecodeError) as err:
            _log.warning("Topology projects query couldn't be parsed: %s", err)
            self.projects_cache.try_again()
            if self.projects_cache.data:
                _log.debug("Returning cached data")
                return self.projects_cache.data
            else:
                _log.error("Failed to update and no cached data")
                return None

        _log.debug("Caching and returning new data")
        self.projects_cache.update(element)
        return self.projects_cache.data

    def get_project_allocations(self):  # type: () -> Dict[str, List[Tuple[str, str]]]
        """Returns a dict keyed by ProjectName of lists of (ResourceGroup, LocalAllocationID)"""
        ret = {}
        projects_tree = self.get_projects()
        if projects_tree:
            for project in projects_tree.findall("./Project"):
                project_name = _safe_element_text(project.find("./Name"))
                if not project_name:
                    continue
                ret[project_name] = ids = []
                for rg in project.findall("./ResourceAllocation/XRAC/ResourceGroups/ResourceGroup"):
                    name = _safe_element_text(rg.find("./Name"))
                    local_allocation_id = _safe_element_text(rg.find("./LocalAllocationID"))
                    if name and local_allocation_id:
                        ids.append((name, local_allocation_id))
        return ret

    def get_project_element(self, projects_tree, project_name):  # type: (Optional[ET.Element], str) -> Optional[ET.Element]
        if re.search(r"[\t\r\n']", project_name):
            _log.error("Invalid character in project name %s", project_name)
            return None

        if projects_tree is None or len(projects_tree) < 1:
            # _get_projects() has already warned us
            return None

        project_element = projects_tree.find("./Project/[Name='%s']" % project_name)
        if project_element is None or len(project_element) < 1:
            _log.warning("Project with name %s not found", project_name)
            return None

        return project_element
#
#
# Internal
#
#


_log = logging.getLogger(__name__)


# took this code from Topology
class _CachedData(object):
    def __init__(self, data=None, timestamp=0.0, force_update=True, cache_lifetime=60.0*15,
                 retry_delay=60.0):
        self.data = data
        self.timestamp = timestamp
        self.force_update = force_update
        self.cache_lifetime = cache_lifetime
        self.retry_delay = retry_delay
        self.next_update = self.timestamp + self.cache_lifetime

    def should_update(self):
        return self.force_update or not self.data or time.time() > self.next_update

    def try_again(self):
        self.next_update = time.time() + self.retry_delay

    def update(self, data):
        self.data = data
        self.timestamp = time.time()
        self.next_update = self.timestamp + self.cache_lifetime
        self.force_update = False


def _safe_element_text(element):  # type: (Optional[ET.Element]) -> str
    return getattr(element, "text", "").strip()
