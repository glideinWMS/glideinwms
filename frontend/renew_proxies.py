#!/usr/bin/env python
"""Automatical renewal of proxies necessary for a glideinWMS frontend
"""

import ConfigParser
import os
import pwd
import re
import subprocess
import sys

CONFIG = '/etc/gwms-frontend/proxies.ini'

DEFAULTS = {'use_voms_admin': 'false',
            'fqan': '/Role=NULL/Capability=NULL',
            'frequency': '1',
            'lifetime': '24'}

class Proxy(object):
    """Class for holding information related to the proxy
    """
    def __init__(self, cert, key, output, lifetime):
        self.cert = cert
        self.key = key
        self.output = output
        self.lifetime = lifetime

    def write(self):
        """Move output proxy from temp location to its final destination
        """
        os.rename(self.output + '.new', self.output)

    def timeleft(self):
        """Returns the remaining lifetime of the proxy in seconds
        """
        stdout, _, _ = _run_command(['voms-proxy-info', '-file', self.output, '-timeleft'])
        try:
            return int(stdout)
        except ValueError:
            return 0

class VO(object):
    """Class for holding information related to VOMS attributes
    """
    def __init__(self, vo, command, cert=None, key=None):
        self.name = vo
        command = command.lstrip('/')
        self.fqan = '/%s/%s' % (vo, command)
        # intended argument for -voms option "vo:command" format, see voms-proxy-init man page
        self.voms = '%s:/%s' % (vo, command)
        self.cert = cert
        self.key = key

def _run_command(command):
    """Runs the specified command, specified as a list. Returns stdout, stderr and return code
    """
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    return stdout, stderr, proc.returncode

def voms_proxy_init(proxy, *args):
    """Create a proxy using voms-proxy-init. Without any additional args, it generates a proxy without VOMS attributes.
    Returns stdout, stderr, and return code of voms-proxy-init
    """
    cmd = ['voms-proxy-init', '--debug',
           '-cert', proxy.cert,
           '-key', proxy.key,
           '-out', proxy.output + '.new',
           '-valid', '%s:00' % proxy.lifetime] + list(args)
    return _run_command(cmd)

def voms_proxy_fake(proxy, vo_info, voms_uri):
    """ Create a valid proxy without contacting a VOMS Admin server. VOMS attributes are created from user config.
    Returns stdout, stderr, and return code of voms-proxy-fake
    """
    cmd = ['voms-proxy-fake', '--debug',
           '-cert', proxy.cert,
           '-key', proxy.key,
           '-out', proxy.output + '.new',
           '-hours', proxy.lifetime,
           '-voms', vo_info.name,
           '-hostcert', vo_info.cert,
           '-hostkey', vo_info.key,
           '-uri', voms_uri,
           '-fqan', vo_info.fqan]
    return _run_command(cmd)

def main():
    """Main entrypoint
    """
    config = ConfigParser.ConfigParser(DEFAULTS)
    config.read(CONFIG)
    proxies = config.sections()

    # Verify config sections
    if proxies.count('FRONTEND') != 1:
        raise RuntimeError("ERROR: there must be only one [FRONTEND] section in %s" % CONFIG)
    if len([x for x in proxies if x.startswith('PILOT')]) < 1:
        raise RuntimeError("ERROR: there must be at least one [PILOT] section in %s" % CONFIG)

    # Proxies need to be owned by the 'frontend' user
    try:
        fe_user = pwd.getpwnam('frontend')
    except KeyError:
        raise RuntimeError("ERROR: missing 'frontend' user")

    # Load VOMS Admin server info for case-sensitive VO name and for faking the VOMS Admin server URI
    with open('/etc/vomses', 'r') as _:
        vo_info = re.findall(r'"(\w+)"\s+"([^"]+)"\s+"(\d+)"\s+"([^"]+)"', _.read(), re.IGNORECASE)
        vomses = dict([(vo[0].lower(), {'name': vo[0], 'uri': vo[1] + ':' + vo[2], 'subject': vo[3]}) for vo in vo_info])

    # Proxy renewals
    for proxy_section in proxies:
        proxy_config = dict(config.items(proxy_section))
        proxy = Proxy(proxy_config['proxy_cert'], proxy_config['proxy_key'],
                      proxy_config['output'], proxy_config['lifetime'])

        if int(proxy.lifetime)*3600 - proxy.timeleft() < int(proxy_config['frequency'])*3600:
            print 'Skipping renewal of %s: time remaining within the specified frequency' % proxy.output
            continue

        if proxy_section == 'FRONTEND':
            stdout, stderr, retcode = voms_proxy_init(proxy)
        elif proxy_section.startswith('PILOT'):
            voms_info = vomses[proxy_config['vo'].lower()]
            vo_attr = VO(voms_info['name'], proxy_config['fqan'])

            if proxy_config['use_voms_admin'].lower() == 'true':
                # we specify '-order' because some European CEs care about VOMS AC order
                stdout, stderr, retcode = voms_proxy_init(proxy, '-voms', vo_attr.voms, '-order', vo_attr.fqan)
            else:
                vo_attr.cert = proxy_config['vo_cert']
                vo_attr.key = proxy_config['vo_key']
                stdout, stderr, retcode = voms_proxy_fake(proxy, vo_attr, voms_info['uri'])
        else:
            print "WARNING: Unrecognized configuration section %s found in %s.\n" % (proxy, CONFIG) + \
                "Valid configuration sections: 'FRONTEND' or 'PILOT'."

        if retcode == 0:
            proxy.write()
            os.chown(proxy.output, fe_user.pw_uid, fe_user.pw_gid)
            print "Renewed proxy from '%s' to '%s'." % (proxy.cert, proxy.output)
        else:
            # don't raise an exception here to continue renewing other proxies
            print "ERROR: Failed to renew proxy %s:\n%s%s" % (proxy.output, stdout, stderr)

if __name__ == "__main__":
    try:
        main()
    except RuntimeError, exc:
        sys.exit(exc)
