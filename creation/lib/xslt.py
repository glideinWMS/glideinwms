import os
import subprocess
# pylint: disable=no-name-in-module
from distutils.spawn import find_executable
# pylint: enable=no-name-in-module

def xslt_xml(old_xmlfile, xslt_plugin_dir):
    ''' Take an XML file, transform it via any XSLT in the
    xslt_plugin_dir, and return the output.'''

    old_xml_fd = open(old_xmlfile)
    if not xslt_plugin_dir:
        return old_xml_fd.read()

    try:
        plugins = [os.path.join(xslt_plugin_dir, f) for f in os.listdir(xslt_plugin_dir)]
    except OSError as e:
        print "Error opening %s directory: %s" % (xslt_plugin_dir, e.strerror)
        return old_xml_fd.read()

    plugins.sort()

    procs = [subprocess.Popen(["cat", "%s" % old_xmlfile], stdout=subprocess.PIPE)]

    if plugins and not find_executable('xsltproc'):
        raise RuntimeError('Cannot reconfig: plugins defined but xsltproc not in path')

    for i, plugin in enumerate(plugins):
        previous_stdout = procs[i].stdout
        procs.append(subprocess.Popen(["xsltproc", "%s" % plugin, "-"], stdin=previous_stdout, stdout=subprocess.PIPE))
        previous_stdout.close()

    output = procs[-1].communicate()[0]
    return output
