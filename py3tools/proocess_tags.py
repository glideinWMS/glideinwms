#!/usr/bin/env python3
"""%(scriptName)s - Convert format for GlideinWMS release TAGs

Usage: %(scriptName)s [ACTION [INFILE [OUTFILE]]]
Parameters:
    ACTION: IN_FORMAT2OUT_FORMAT (Default: yaml2txt), 2 is the separator
            Supported IN_FORMAT: yaml, txt
            Supported OUT_FORMAT: yaml, txt, print, dict, history
    INFILE: inout file name (Default: tags.IN_FORMAT)
    OUTFILE: output file name (Default: tags.OUT_FORMAT)

"""

# #!/bin/env python3

import yaml
import sys
import os
from collections import defaultdict

# String constants for possible keys in the tag lines, to avoid typos
SERIES = 'Series'
DEVELOPMENT = 'Development'
PRODUCTION = 'Production'
NAME = 'Name'
DATE = 'Date'
TARBALL = 'Tarball'
FEATURE = 'Feature'
BACKPORT = 'Backport'
BUGFIX = 'Bug fix'
BUGFIX_ALIASES = [BUGFIX, 'Bug Fix', 'BUG FIX']
NOTE = 'NOTE'
NOTE_FACTORY = 'NOTE-FACTORY'
NOTE_FRONTEND = 'NOTE-FRONTEND'
NOT_BACKWARD_COMPATIBLE = 'NOT BACKWARD COMPATIBLE'
KNOWN_ISSUE = 'KNOWN ISSUE'
KNOWN_ISSUE_ALIASES = [KNOWN_ISSUE, 'KNOWN ISSUES']
NOT_FOR_TAGS = [SERIES, NAME, TARBALL, DATE]
# PROCESSED_TAGS = [FEATURE, BACKPORT, NOTE] + BUGFIX_ALIASES + NOT_FOR_TAGS
# BUGFIX aliases are not in the dictionary
PROCESSED_TAGS = [FEATURE, BACKPORT, NOTE, BUGFIX] + NOT_FOR_TAGS
FROM_TAG_FILE = [BUGFIX, BACKPORT, NOTE, NOTE_FACTORY, NOTE_FRONTEND, NOT_BACKWARD_COMPATIBLE, KNOWN_ISSUE]
FROM_TAG_FILE_EXT = [BACKPORT, NOTE, NOTE_FACTORY, NOTE_FRONTEND, NOT_BACKWARD_COMPATIBLE] + \
                    BUGFIX_ALIASES + KNOWN_ISSUE_ALIASES
TAG_ALIAS = {
    BACKPORT: BACKPORT,
    NOTE: NOTE,
    NOTE_FACTORY: NOTE_FACTORY,
    NOTE_FRONTEND: NOTE_FRONTEND,
    NOT_BACKWARD_COMPATIBLE: NOT_BACKWARD_COMPATIBLE,
    KNOWN_ISSUE: KNOWN_ISSUE,
    'KNOWN ISSUES': KNOWN_ISSUE,
    BUGFIX: BUGFIX,
    'Bug Fix': BUGFIX,
    'BUG FIX': BUGFIX
}


class ParameterException(Exception):
    def __init__(self):
        super()

    def __init__(self, message):
        super()
        self.message = message


# Not used in python3
def add_default(dest, default):
    """Add default values to dest. default must have simple values (no deepcopy)

    Args:
        dest: dictionary to complete
        default: dictionary w/ default values

    Returns:
        dest with added default values from default
    """
    res = default.copy()
    res.update(dest)
    return dest


def dump_txt(release_tags, fname=None, versions=None):
    """Write to a file (stdout by default) the release tags, separated by a blank line

    Args:
        release_tags: dictionary of release tags {release_version: tags,}
        fname: output file, sys.stdout by default
        versions: list of release versions to be printed in order

    """
    if not versions:
        versions = list(release_tags)
        versions.sort(reverse=True)
    if fname:
        fd = open(fname, 'w')
    else:
        fd = None
    try:
        for v in versions:
            # TODO: add better formatting for multiline tags
            print(v, file=fd)
            for i in release_tags[v].get(FEATURE, []):
                print("\t%s" % (i,), file=fd)
            for i in release_tags[v].get(BACKPORT, []):
                print("\t%s: %s" % (BACKPORT, i), file=fd)
            for i in release_tags[v].get(BUGFIX, []):
                print("\t%s: %s" % (BUGFIX, i), file=fd)
            for i in release_tags[v].get(NOTE, []):
                print("\t%s: %s" % (NOTE, i), file=fd)
            for k in [k for k in release_tags[v] if k not in PROCESSED_TAGS]:
                for i in release_tags[v][k]:
                    print("\t%s: %s" % (k, i), file=fd)
            print()
    finally:
        if fd:
            fd.close()


def print_dicts(release_tags, versions=None):
    """Print to stdout the release tags as dict representations, separated by a blank line

    Args:
        release_tags: dictionary of release tags {release_version: tags,}
        versions: list of release versions to be printed in order

    """
    if not versions:
        versions = list(release_tags)
        versions.sort(reverse=True)
    for v in versions:
        print(v)
        print(release_tags[v])
        print()


def make_rel_dict(lines):
    """Make a dict containing release information out of the tag lines

    Args:
        lines: tag lines

    Returns:
        dictionary with all release tags sorted

    """
    ret = defaultdict(list)
    i: str
    for i in lines:
        for k in FROM_TAG_FILE_EXT:
            prefix = "%s: " % k
            if i.startswith(prefix):
                ret[TAG_ALIAS[k]].append(i[len(prefix):])
                break
        else:
            ret[FEATURE].append(i)
    return dict(ret)


def load_txt(infile):
    """Load the release tags (and other information) from a text file

    Args:
        infile: text input file with tags

    Returns:
        the dictionary of releases

    """
    rel_dict = {}
    with open(infile, 'r') as lines:
        fdb = open('/tmp/mmdb.txt', 'w')
        rel_lines = []
        version = None
        try:
            current: str = next(lines).rstrip('\n')
            while True:
                fdb.write("%s\n" % current)
                if not current or current.startswith('#') or current.isspace():
                    current = next(lines).rstrip('\n')
                    continue
                if current.startswith('v'):
                    # New release tag
                    try:
                        version, rel_line = current.split(maxsplit=1)
                    except ValueError:
                        version = current.split(maxsplit=1)[0]
                        rel_line = ''
                    rel_lines = []
                    block_indent = 0
                    while True:
                        # in release tag
                        current = next(lines).rstrip('\n')
                        if not current or current.startswith('v') or current.isspace():
                            rel_lines.append(rel_line)
                            break
                        indent = len(current) - len(current.lstrip())
                        if block_indent == 0:
                            # first line after the release line
                            block_indent = indent
                            if rel_line:
                                # new TAG file version has release version alone on one line, old one has item
                                rel_lines.append(rel_line)
                            rel_line = current.lstrip()
                            continue
                        elif indent > block_indent:
                            # continue previous item
                            rel_line = "%s\n%s" % (rel_line, current.lstrip())
                            continue
                        elif indent < block_indent:
                            raise Exception("Error parsing TAG file %s: malformed indentation: %s" % (infile, current))
                        # indent == block_indent (new item)
                        rel_lines.append(rel_line)
                        rel_line = current.lstrip()
                    rel_dict[version] = make_rel_dict(rel_lines)
                    print("MMDB added %s" % version)
        except StopIteration:
            if version is not None and version not in rel_dict:
                # ended w/o empty line
                if rel_lines and rel_lines[-1] != rel_line:
                    rel_lines.append(rel_line)
                rel_dict[version] = make_rel_dict(rel_lines)
    return rel_dict


def dump_yaml(release_tags, outfile, versions=None):
    """Write the release tags to a YAML file

    Args:
        release_tags: dictionary with tags for all releases {release_number: tags}
        outfile: YAML output file
        versions: list of release numbers to output in order

    """
    if not versions:
        versions = list(release_tags)
        versions.sort(reverse=True)
    if outfile is None:
        for v in versions:
            yaml.safe_dump({v: release_tags[v]}, sys.stdout)
            sys.stdout.write('\n')
    else:
        with open(outfile, 'w') as out:
            for v in versions:
                yaml.safe_dump({v: release_tags[v]}, out)
                out.write('\n')


def load_yaml(fname):
    """Load the release tags (and other information) from a YAML file

    Args:
        fname: YAML input file

    Returns:
        the dictionary of releases

    """
    with open(fname, 'r') as stream:
        release_tags = yaml.safe_load(stream)
    default = {}
    try:
        default = release_tags['default']
        del release_tags['default']
    except KeyError:
        pass
    to_delete = [v for v in release_tags if v.startswith('template')]
    for v in to_delete:
        del release_tags[v]
    versions = list(release_tags)
    # py2.7:  release_tags = {v: add_default(release_tags[v], default) for v in release_tags}
    release_tags = {v: {**default, NAME: v, **release_tags[v]} for v in release_tags}
    return release_tags


""" source example
    <h3>Stable Series</h3>
    <ul>
      <li>
        <b>v3_5_1</b> released on September 18, 2019 (<a href="http://glideinwms.fnal.gov/doc.v3_5_1/index.html">Manual</a>,<a href="http://glideinwms.fnal.gov/doc.v3_5_1/install.html">Installation instructions</a>,<a href="http://glideinwms.fnal.gov/glideinWMS_v3_5_1.tgz">Tarball</a>)<br>
        <ul>
		<li>Including all 3.4.6 features</li>
	<li>Updated SW and docs for the change in OSG factories</li>
        <li>Updated all the obsolete links to HTCondor manual in GlideinWMS website</li>
        <li>Set up an ITB Frontend for GWMS and FIFE testing</li>
        <li>Updated gitattributes to resolve conflicts w/ checksum files</li>
        <li>Added editorconfig and default encoding</li>
        <li>GlideinWMS code will use now Google docstring format </li>
        <li>Advertise if a Glidein can use privileged or unprivileged Singularity</li>
        <li>Check if single user factory migration script has been run before startup</li>
        <li>Bug fix: pip errors in nightly CI</li>
        <li>Bug fix: Unittest failing at times on SL7</li>
        <li>Bug fix: Factory could start also w/ a GT2 entry enabled</li>
        </ul>
      </li>
"""

def release2html(v, tags):
    """

    Args:
        v:
        tags:

    Returns:

    """
    tar_string = ""
    if tags['Tarball']:
        tar_string = ',<a href="http://glideinwms.fnal.gov/glideinWMS_%s.tgz">Tarball</a>' % tags['Name']
    tmp = """<li>
  <b>{Name}</b> released on {Date} (<a href="http://glideinwms.fnal.gov/doc.{Name}/index.html">Manual</a>,
  <a href="http://glideinwms.fnal.gov/doc.{Name}/install.html">Installation instructions</a>%s)<br>  
    <ul>""" % tar_string
    lines = [tmp.format(**tags)]
    for i in tags.get(FEATURE, []):
        lines.append("    <li>%s</li>" % i)
    for i in tags.get(BACKPORT, []):
        lines.append("    <li>%s: %s</li>" % (BACKPORT, i))
    for i in tags.get(BUGFIX, []):
        lines.append("    <li>%s: %s</li>" % (BUGFIX, i))
    for i in tags.get(NOTE, []):
        lines.append("    <li>%s: %s</li>" % (NOTE, i))
    for k in [k for k in tags if k not in PROCESSED_TAGS]:
        for i in release_tags[v][k]:
            lines.append("    <li>%s: %s</li>" % (k, i))
    lines.append("""    </ul>
</li>
""")
    return '\n'.join(lines)


def dump_html(release_tags, outfile, versions=None, append=False):
    """

    Args:
        release_tags:
        outfile:
        versions:

    Returns:

    """

    if not versions:
        versions = list(release_tags)
        versions.sort(reverse=True)
    if outfile is None:
        raise Exception("html to stdout is not supported")
    if append:
        file_flag = 'a'
    else:
        file_flag = 'w'
    with open(outfile, file_flag) as out:
        for v in versions:
            out.write(release2html(v, release_tags[v]))


def dump_history(release_tags, h_file="doc/history.html"):
    """Write the history.html.new file from history.html and the release tags

    Stable and development list should be delimited by the following lines respectively:
    <!-- start stable --> <!-- end stable -->
    <!-- start development --> <!-- end development -->
    Args:
        release_tags: release tags dictionary
        h_file: history file (Default: doc/history.html)

    Returns:

    """
    # copy first part
    release_all = list(release_tags)
    release_all.sort(reverse=True)
    if not h_file:
        h_file = "doc/history.html"
    with open(h_file, 'r') as h_old:
        with open("%s.new.html" % h_file, 'w') as h_new:
            end_string = None
            for line in h_old:
                if line.strip() == "<!-- start stable -->" or line.strip() == "<!-- start development -->":
                    if line.strip() == "<!-- start stable -->":
                        # stable series list
                        # From 3.4 on
                        release = [ r for r in release_all if r.startswith("v3_") and int(r[3]) % 2 == 0]
                        end_string = "<!-- end stable -->"
                    elif line.strip() == "<!-- start development -->":
                        # for development
                        # From 3.3 on
                        release = [ r for r in release_all if r.startswith("v3_") and int(r[3]) % 2 == 1]
                        end_string = "<!-- end development -->"
                    else:
                        # There are only 2 option
                        raise Exception("Wrong line format (%s)" % line.strip())
                    h_new.write(line)
                    continue
                if end_string:
                    if line.strip() == end_string:
                        for v in release:
                            h_new.write(release2html(v, release_tags[v]))
                        h_new.write(line)
                        end_string = None
                        release = []
                else:
                    h_new.write(line)
    # closing both files
    if release or end_string:
        raise Exception("Wrong history.html file format, section not closed (%s)" % end_string)


def test(release_tags):
    versions = list(release_tags)
    versions.sort(reverse=True)
    stable = []
    development = []
    for version in versions:
        r = release_tags[version]
        if r[SERIES] == DEVELOPMENT:
            development.append(r)
        else:
            stable.append(r)
    dump_txt(release_tags, versions)


def main(fname='tags.yml'):
    """

    Args:
        fname: YAML input file

    Returns:

    """
    with open(fname, 'r') as stream:
        release_tags = yaml.safe_load(stream)
    default = {}
    try:
        default = release_tags['default']
        del release_tags['default']
    except KeyError:
        pass
    delete = [v for v in release_tags if v.startswith('template')]
    for v in delete:
        del release_tags[v]
    versions = list(release_tags)
    versions.sort(reverse=True)
    # py2.7:  release_tags = {v: add_default(release_tags[v], default) for v in release_tags}
    release_tags = {v: {**default, NAME: v, **release_tags[v]} for v in release_tags}
    stable = []
    development = []
    for version in versions:
        r = release_tags[version]
        if r[SERIES] == DEVELOPMENT:
            development.append(r)
        else:
            stable.append(r)
    dump_txt(release_tags, versions)


if __name__ == "__main__":
    action = 'yaml2txt'
    infile = 'tags.'
    outfile = 'tags.'
    arg_len = len(sys.argv)
    try:
        try:
            action = sys.argv[1]
            infile = sys.argv[2]
            outfile = sys.argv[3]
        except IndexError:
            try:
                action_in, action_out = action.split('2')
            except:
                raise ParameterException("Invalid argument %s" % action)
            outfile += action_out
            if arg_len < 3:
                infile += action_in
        else:
            action_in, action_out = action.split('2')
        if action_in == 'txt':
            release_tags = load_txt(infile)
        elif action_in == 'yaml':
            release_tags = load_yaml(infile)
        else:
            raise ParameterException("Unsupported input format: %s" % action_in)
        if outfile == '-' or outfile == 'stdout':
            outfile = None
        elif outfile == 'tags.history':
            outfile = "doc/history.html"
        if action_out == 'tag':
            dump_txt(release_tags, outfile)
        elif action_out == 'print':
            dump_txt(release_tags)
        elif action_out == 'dict':
            print_dicts(release_tags)
        elif action_out == 'yaml':
            dump_yaml(release_tags, outfile)
        elif action_out == 'html':
            dump_html(release_tags, outfile)
        elif action_out == 'history':
            dump_history(release_tags, outfile)
        else:
            raise ParameterException("Unsupported output format: %s" % action_out)
    except ParameterException as e:
        print("Error invoking %s:" % sys.argv[0])
        print(str(e))
        print(__doc__ % {'scriptName' : sys.argv[0].split("/")[-1]})
        sys.exit(1)
    sys.exit()
