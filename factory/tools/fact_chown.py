from __future__ import print_function

import os
import sys
import grp
import pwd
import logging
import tarfile
import argparse
from contextlib import closing  # python 2.6 tarfile does not support with

from glideinwms.creation.lib import factoryXmlConfig

def parse_opts():
    """ Parse the command line options for this command
    """
    description = 'Change the ownership of frontend directories to the specified user\n\n'

    parser = argparse.ArgumentParser(
        description=description)

    parser.add_argument(
        '--user', type=str, action='store', dest='user',
        help='User to use when chowning the files')

    parser.add_argument(
        '--group', type=str, action='store', dest='group',
        help='Group to use when cowning the files')

    parser.add_argument(
        '--backup', action='store_true', dest='backup',
        default=False,
        help='Back up the directories into the cwd before chwon everything')

    parser.add_argument(
        '--debug', action='store_true', dest='debug',
        default=False,
        help='Enable debug logging')

    parser.add_argument(
        '--test', action='store_true', dest='test',
        default=False,
        help='Run the script but do not change permissions')

    options = parser.parse_args()

    if options.user is None:
        logging.error('Missing required option "--user"')
        sys.exit(1)

    if options.group is None:
        logging.error('Missing required option "--group"')
        sys.exit(1)

    # Initialize logging
    if options.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    return options


def find_ownerid(filename):
    return getpwuid(os.stat(filename).st_uid).pw_name


def backup_dir(output_filename, source_dir):
    with closing(tarfile.open(output_filename, "w:gz")) as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


def mychown(path, uid, gid, fuid, test):
        cid = os.stat(path).st_uid  # current id
        if cid != fuid:
            logging.warning("Not changing %s since it's owner id is not %s" % (path, fuid))
        if test:
            logging.info("Test mode: not changing %s" % path)
        else:
            os.chown(path, uid, gid)


def chown_dir(path, uid, gid, fuid, test):
    mychown(path, uid, gid, fuid, test)
    for dirpath, dirnames, filenames in os.walk(path):
        for dname in dirnames:
            mychown(os.path.join(dirpath, dname), uid, gid, fuid, test)
            pass
        for fname in filenames:
            mychown(os.path.join(dirpath, fname), uid, gid, fuid, test)
            pass


def main():
    options = parse_opts()

    conf_file = '/etc/gwms-factory/glideinWMS.xml' #TODO
    logging.info('Loading configuration file %s' % conf_file)
    conf = factoryXmlConfig.parse(conf_file)
    uid = pwd.getpwnam(options.user).pw_uid
    gid = grp.getgrnam(options.group)[2]

    dir_dicts = [ conf.get_client_log_dirs(), conf.get_client_proxy_dirs() ]

    for client_dir_dict in dir_dicts:
        for fe_user, fe_client_dir in client_dir_dict.items():
            logging.info('Working on %s: changing ownership from %s to %s' % (fe_client_dir, fe_user, options.user))
            if options.backup:
                logging.info('Backing it up in the current directory first')
                backup_dir(fe_user + '.tar.gz', fe_client_dir)
            fuid = pwd.getpwnam(fe_user).pw_uid
            chown_dir(fe_client_dir, uid, gid, fuid, options.test)


if __name__ == '__main__':
    main()
