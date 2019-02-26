#!/usr/bin/env python
# Code and configuration files contributed by Brian Lin, OSG Software
"""Automatical renewal of proxies necessary for a glideinWMS frontend
"""
from __future__ import print_function

import ConfigParser
import os
import pwd
import re
import subprocess
import sys
import tempfile

from glideinwms.lib import x509Support

CONFIG = '/etc/gwms-frontend/proxies.ini'

DEFAULTS = {'use_voms_server': 'false',
            'fqan': '/Role=NULL/Capability=NULL',
            'frequency': '1',
            'lifetime': '24',
            'owner': 'frontend'}


class Proxy(object):
    """Class for holding information related to the proxy
    """
    def __init__(self, cert, key, output, lifetime, uid=0, gid=0):
        self.cert = cert
        self.key = key
        self.tmp_output_fd = tempfile.NamedTemporaryFile(dir=os.path.dirname(output), delete=False)
        self.output = output
        self.lifetime = lifetime
        self.uid = uid
        self.gid = gid

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


class VO(object):
    """Class for holding information related to VOMS attributes
    """
    def __init__(self, vo, fqan, cert=None, key=None):
        """vo - name of the Virtual Organization. Case should match folder names in /etc/grid-security/vomsdir/
        fqan - VOMS attribute FQAN with format "/vo/command" (/osg/Role=NULL/Capability=NULL) or
               "command" (Role=NULL/Capability=NULL)
        cert - path to VOMS server certificate used to sign VOMS attributes (for use with voms_proxy_fake)
        key - path to key associated with the cert argument
        """
        self.name = vo
        if fqan.startswith('/%s/Role=' % vo):
            pass
        elif fqan.startswith('/Role='):
            fqan = '/%s%s' % (vo, fqan)
        else:
            raise ValueError('Malformed FQAN does not begin with "/%s/Role=" or "/Role=". Verify %s.' % (vo, CONFIG))
        self.fqan = fqan
        # intended argument for -voms option "vo:command" format, see voms-proxy-init man page
        self.voms = ':'.join([vo, fqan])
        self.cert = cert
        self.key = key


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


def voms_proxy_init(proxy, *args):
    """Create a proxy using voms-proxy-init. Without any additional args, it generates a proxy without VOMS attributes.
    Returns stdout, stderr, and return code of voms-proxy-init
    """
    cmd = ['voms-proxy-init', '--debug',
           '-cert', proxy.cert,
           '-key', proxy.key,
           '-out', proxy.tmp_output_fd.name,
           '-valid', '%s:00' % proxy.lifetime] + list(args)
    return _run_command(cmd)


def voms_proxy_fake(proxy, vo_info, voms_uri):
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
    if proxies.count('COMMON') != 1:
        raise RuntimeError("there must be only one [COMMON] section in %s" % CONFIG)
    if len([x for x in proxies if x.startswith('PILOT')]) < 1:
        raise RuntimeError("there must be at least one [PILOT] section in %s" % CONFIG)

    # Proxies need to be owned by the 'frontend' user
    try:
        fe_user = pwd.getpwnam(config.get('COMMON', 'owner'))
    except KeyError:
        raise RuntimeError("missing 'frontend' user")

    # Load VOMS Admin server info for case-sensitive VO name and for faking the VOMS Admin server URI
    with open(os.getenv('VOMS_USERCONF', '/etc/vomses'), 'r') as _:
        vo_info = re.findall(r'"(\w+)"\s+"([^"]+)"\s+"(\d+)"\s+"([^"]+)"', _.read(), re.IGNORECASE)
        # VO names are case-sensitive but we don't expect users to get the case right in the proxies.ini
        vo_name_map = {vo[0].lower(): vo[0] for vo in vo_info}
        # A mapping between VO certificate subject DNs and VOMS URI of the form "<HOSTNAME>:<PORT>"
        # We had to separate this out from the VO name because a VO could have multiple vomses entries
        vo_uri_map = {vo[3]: vo[1] + ':' + vo[2] for vo in vo_info}

    retcode = 0
    # Proxy renewals
    proxies.remove('COMMON')  # no proxy renewal info in the COMMON section
    for proxy_section in proxies:
        proxy_config = dict(config.items(proxy_section))
        proxy = Proxy(proxy_config['proxy_cert'], proxy_config['proxy_key'],
                      proxy_config['output'], proxy_config['lifetime'],
                      fe_user.pw_uid, fe_user.pw_gid)

        # Users used to be able to control the frequency of the renewal when they were instructed to write their own
        # script and cronjob. Since the automatic proxy renewal cron/timer runs every hour, we allow the users to
        # control this via the 'frequency' config option. If more than 'frequency' hours have elapsed in a proxy's
        # lifetime, renew it. Otherwise, skip the renewal.
        def has_time_left(time_remaining):
            return int(proxy.lifetime)*3600 - time_remaining < int(proxy_config['frequency'])*3600

        if proxy_section == 'FRONTEND':
            if has_time_left(proxy.timeleft()):
                print('Skipping renewal of %s: time remaining within the specified frequency' % proxy.output)
                os.remove(proxy.tmp_output_fd.name)
                continue
            stdout, stderr, client_rc = voms_proxy_init(proxy)
        elif proxy_section.startswith('PILOT'):
            if has_time_left(proxy.timeleft()) and has_time_left(proxy.actimeleft()):
                print('Skipping renewal of %s: time remaining within the specified frequency' % proxy.output)
                os.remove(proxy.tmp_output_fd.name)
                continue

            vo_attr = VO(vo_name_map[proxy_config['vo'].lower()], proxy_config['fqan'])

            if proxy_config['use_voms_server'].lower() == 'true':
                # we specify '-order' because some European CEs care about VOMS AC order
                # The '-order' option chokes if a Capability is specified but we want to make sure we request it
                # in '-voms' because we're not sure if anything is looking for it
                fqan = re.sub(r'\/Capability=\w+$', '', vo_attr.fqan)
                stdout, stderr, client_rc = voms_proxy_init(proxy, '-voms', vo_attr.voms, '-order', fqan)
            else:
                vo_attr.cert = proxy_config['vo_cert']
                vo_attr.key = proxy_config['vo_key']
                voms_ac_issuer = x509Support.extract_DN(vo_attr.cert)
                stdout, stderr, client_rc = voms_proxy_fake(proxy, vo_attr, vo_uri_map[voms_ac_issuer])
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
            os.remove(proxy.tmp_output_fd.name)

    return retcode


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print("ERROR: " + str(exc))
        sys.exit(1)
