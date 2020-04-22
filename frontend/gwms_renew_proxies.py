#!/usr/bin/env python
# Code and configuration files contributed by Brian Lin, OSG Software
"""Automatical renewal of proxies necessary for a glideinWMS frontend
"""
from __future__ import print_function
from __future__ import absolute_import

import ConfigParser
import os
import pwd
import re
import subprocess
import sys
import tempfile

from glideinwms.lib import x509Support
from glideinwms.lib.util import safe_boolcomp

CONFIG = '/etc/gwms-frontend/proxies.ini'

DEFAULTS = {'use_voms_server': 'false',
            'fqan': '/Role=NULL/Capability=NULL',
            'frequency': '1',
            'lifetime': '24',
            'path-length': '20',
            'rfc': 'true',
            'owner': 'frontend'}


class ConfigError(BaseException):
    """Catch-all class for errors in proxies.ini or system VO configuration
    """
    pass


class Proxy(object):
    """Class for holding information related to the proxy
    """
    def __init__(self, cert, key, output, lifetime, uid=0, gid=0, rfc=True, pathlength='20'):
        self.cert = cert
        self.key = key
        self.tmp_output_fd = tempfile.NamedTemporaryFile(dir=os.path.dirname(output), delete=False)
        self.output = output
        self.lifetime = lifetime
        self.uid = uid
        self.gid = gid
        self.rfc = rfc
        self.pathlength = pathlength

    def _voms_proxy_info(self, *opts):
        """Run voms-proxy-info. Returns stdout, stderr, and return code of voms-proxy-info
        """
        cmd = ['voms-proxy-info', '-file', self.output] + list(opts)
        return _run_command(cmd)

    def write(self):
        """Move output proxy from temp location to its final destination
        """
        self.tmp_output_fd.flush()
        os.fsync(self.tmp_output_fd)
        self.tmp_output_fd.close()
        os.chown(self.tmp_output_fd.name, self.uid, self.gid)
        os.rename(self.tmp_output_fd.name, self.output)

    def timeleft(self):
        """Safely return the remaining lifetime of the proxy, in seconds (returns 0 if unexpected stdout)
        """
        return _safe_int(self._voms_proxy_info('-timeleft')[0])

    def actimeleft(self):
        """Safely return the remaining lifetime of the proxy's VOMS AC, in seconds (returns 0 if unexpected stdout)
        """
        return _safe_int(self._voms_proxy_info('-actimeleft')[0])

    def cleanup(self):
        """Cleanup temporary proxy files
        """
        os.remove(self.tmp_output_fd.name)


class VO(object):
    """Class for holding information related to VOMS attributes
    """
    def __init__(self, vo, fqan):
        """vo - name of the Virtual Organization. Case should match folder names in /etc/grid-security/vomsdir/
        fqan - VOMS attribute FQAN with format "/vo/command" (/osg/Role=NULL/Capability=NULL) or
               "command" (Role=NULL/Capability=NULL)
        cert - path to VOMS server certificate used to sign VOMS attributes (for use with voms_proxy_fake)
        key - path to key associated with the cert argument
        uri - hostname and port of the VO's VOMS Admin Server, e.g. voms.opensciencegrid.org:15001
        """
        self.name = vo
        if fqan.startswith('/%s/Role=' % vo):
            pass
        elif fqan.startswith('/%s/' % vo):
            pass
        elif fqan.startswith('/Role='):
            fqan = '/%s%s' % (vo, fqan)
        else:
            raise ValueError('Malformed FQAN does not begin with "/%s/Role=" or "/Role=". Verify %s.' % (vo, CONFIG))
        self.fqan = fqan
        # intended argument for -voms option "vo:command" format, see voms-proxy-init man page
        self.voms = ':'.join([vo, fqan])
        self.cert = None
        self.key = None
        self.uri = None

def _safe_int(string_var):
    """Convert a string to an integer. If the string cannot be cast, return 0.
    """
    try:
        return int(string_var)
    except ValueError:
        return 0


def _run_command(command):
    """Runs the specified command, specified as a list. Returns stdout, stderr and return code
    """
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return stdout, stderr, proc.returncode


def parse_vomses(vomses_contents):
    """Parse the contents of a vomses file with the the following format per line:
    "<VO ALIAS> " "<VOMS ADMIN HOSTNAME>" "<VOMS ADMIN PORT>" "<VOMS CERT DN>" "<VO NAME>"
    And return two mappings:
    1. Case insensitive VO name to their canonical versions
    2. VO certificate DN to URI, i.e. HOSTNAME:PORT
    """
    vo_info = re.findall(r'"[\w\.]+"\s+"([^"]+)"\s+"(\d+)"\s+"([^"]+)"\s+"([\w\.]+)"', vomses_contents, re.IGNORECASE)
    # VO names are case-sensitive but we don't expect users to get the case right in proxies.ini
    vo_names = dict([(vo[3].lower(), vo[3]) for vo in vo_info])
    # A mapping between VO certificate subject DNs and VOMS URI of the form "<HOSTNAME>:<PORT>"
    # We had to separate this out from the VO name because a VO could have multiple vomses entries
    vo_uris = dict([(vo[2], vo[0] + ':' + vo[1]) for vo in vo_info])
    return vo_names, vo_uris


def voms_proxy_init(proxy, voms_attr=None):
    """Create a proxy using voms-proxy-init, using the proxy information and optionally VOMS attribute.
    Returns stdout, stderr, and return code of voms-proxy-init
    """
    cmd = ['voms-proxy-init',
           '-debug',
           '-old',
           '-cert', proxy.cert,
           '-key', proxy.key,
           '-out', proxy.tmp_output_fd.name,
           '-valid', '%s:00' % proxy.lifetime]

    if voms_attr:
        # Some VOMS servers don't support capability/role/group selection so we just use the VO name when making
        # the request. We don't handle this in the VO class because voms-proxy-fake requires the full VO name
        # and command string.
        if voms_attr.voms.endswith('/Role=NULL/Capability=NULL'):
            voms = voms_attr.name
        else:
            voms = voms_attr.voms
            # We specify '-order' because some European CEs care about VOMS AC order
            # The '-order' option chokes if a Capability is specified but we want to make sure we request it
            # in '-voms' because we're not sure if anything is looking for it
        fqan = re.sub(r'\/Capability=\w+$', '', voms_attr.fqan)
        cmd += ['-voms', voms,
                '-order', fqan]

    return _run_command(cmd)


def voms_proxy_fake(proxy, vo_info):
    """ Create a valid proxy without contacting a VOMS Admin server. VOMS attributes are created from user config.
    Returns stdout, stderr, and return code of voms-proxy-fake
    """
    cmd = ['voms-proxy-fake', '--debug',
           '-cert', proxy.cert,
           '-key', proxy.key,
           '-out', proxy.tmp_output_fd.name,
           '-hours', proxy.lifetime,
           '-voms', vo_info.name,
           '-hostcert', vo_info.cert,
           '-hostkey', vo_info.key,
           '-uri', vo_info.uri,
           '-fqan', vo_info.fqan,
           '-path-length', proxy.pathlength]
    if proxy.rfc:
        cmd.append('-rfc')
    return _run_command(cmd)


def main():
    """Main entrypoint
    """
    config = ConfigParser.ConfigParser(DEFAULTS)
    config.read(CONFIG)
    proxies = config.sections()

    # Verify config sections
    if proxies.count('COMMON') != 1:
        raise ConfigError("there must be only one [COMMON] section in %s" % CONFIG)
    if len([x for x in proxies if x.startswith('PILOT')]) < 1:
        raise ConfigError("there must be at least one [PILOT] section in %s" % CONFIG)

    # Proxies need to be owned by the 'frontend' user
    try:
        fe_user = pwd.getpwnam(config.get('COMMON', 'owner'))
    except KeyError:
        raise RuntimeError("missing 'frontend' user")

    # Load VOMS Admin server info for case-sensitive VO name and for faking the VOMS Admin server URI
    vomses = os.getenv('VOMS_USERCONF', '/etc/vomses')
    with open(vomses, 'r') as _:
        vo_name_map, vo_uri_map = parse_vomses(_.read())

    retcode = 0
    # Proxy renewals
    proxies.remove('COMMON')  # no proxy renewal info in the COMMON section
    for proxy_section in proxies:
        proxy_config = dict(config.items(proxy_section))
        if 'rfc' not in proxy_config:
            proxy_config['rfc'] = True
        else:
            if safe_boolcomp(proxy_config['rfc'], False):
                proxy_config['rfc'] = False
            else:
                proxy_config['rfc'] = True
        if 'path_length' not in proxy_config:
             proxy_config['path_length'] = '20'
        proxy = Proxy(proxy_config['proxy_cert'], proxy_config['proxy_key'],
                      proxy_config['output'], proxy_config['lifetime'],
                      fe_user.pw_uid, fe_user.pw_gid, proxy_config['rfc'], proxy_config['path_length'])

        # Users used to be able to control the frequency of the renewal when they were instructed to write their own
        # script and cronjob. Since the automatic proxy renewal cron/timer runs every hour, we allow the users to
        # control this via the 'frequency' config option. If more than 'frequency' hours have elapsed in a proxy's
        # lifetime, renew it. Otherwise, skip the renewal.
        def has_time_left(time_remaining):
            return int(proxy.lifetime)*3600 - time_remaining < int(proxy_config['frequency'])*3600

        if proxy_section == 'FRONTEND':
            if has_time_left(proxy.timeleft()):
                print('Skipping renewal of %s: time remaining within the specified frequency' % proxy.output)
                proxy.cleanup()
                continue
            stdout, stderr, client_rc = voms_proxy_init(proxy)
        elif proxy_section.startswith('PILOT'):
            if has_time_left(proxy.timeleft()) and has_time_left(proxy.actimeleft()):
                print('Skipping renewal of %s: time remaining within the specified frequency' % proxy.output)
                proxy.cleanup()
                continue

            vo_attr = VO(vo_name_map[proxy_config['vo'].lower()], proxy_config['fqan'])

            if safe_boolcomp(proxy_config['use_voms_server'], True):
                stdout, stderr, client_rc = voms_proxy_init(proxy, vo_attr)
            else:
                vo_attr.cert = proxy_config['vo_cert']
                vo_attr.key = proxy_config['vo_key']
                try:
                    vo_attr.uri = vo_uri_map[x509Support.extract_DN(vo_attr.cert)]
                except KeyError:
                    retcode = 1
                    print("ERROR: Failed to renew proxy {0}: ".format(proxy.output) +
                          "Could not find entry in {0} for {1}. ".format(vomses, vo_attr.cert) +
                          "Please verify your VO data installation.")
                    proxy.cleanup()
                    continue
                stdout, stderr, client_rc = voms_proxy_fake(proxy, vo_attr)
        else:
            print("WARNING: Unrecognized configuration section %s found in %s.\n" % (proxy, CONFIG) +
                  "Valid configuration sections: 'FRONTEND' or 'PILOT'.")
            client_rc = -1
            stderr = "Unrecognized configuration section '%s', renewal not attempted." % proxy_section
            stdout = ""

        if client_rc == 0:
            proxy.write()
            print("Renewed proxy from '%s' to '%s'." % (proxy.cert, proxy.output))
        else:
            retcode = 1
            # don't raise an exception here to continue renewing other proxies
            print("ERROR: Failed to renew proxy %s:\n%s%s" % (proxy.output, stdout, stderr))
            proxy.cleanup()

    return retcode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ConfigError, ValueError) as exc:
        print("ERROR: " + str(exc))
        sys.exit(1)
