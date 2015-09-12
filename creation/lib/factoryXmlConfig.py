import os
from xml.dom.minidom import parse

ENTRY_INDENT = 6
ENTRY_DIR = 'entries.d'

class FactoryXmlConfig:
    def __init__(self, file):
        self.file = file
        self.dom = None

    def parse(self):
        d1 = parse(self.file)
        entry_dir_path = os.path.join(os.path.dirname(self.file), ENTRY_DIR)
        if not os.path.exists(entry_dir_path):
            self.dom = d1
            return

        entries = d1.getElementsByTagName(u'entry')

        found_entries = {}
        for e in entries:
            found_entries[e.getAttribute(u'name')] = e

        files = sorted(os.listdir(entry_dir_path))
        for f in files:
            if f.endswith('.xml'):
                d2 = parse(os.path.join(entry_dir_path, f))
                merge_entries(d1, d2, found_entries)
                d2.unlink()

        self.dom = d1

#######################
#
# Utility functions
#
######################

def merge_entries(d1, d2, found_entries):
    entries1 = d1.getElementsByTagName(u'entries')[0]
    entries2 = d2.getElementsByTagName(u'entries')[0]

    for e in entries2.getElementsByTagName(u'entry'):
        entry_name = e.getAttribute(u'name')
        entry_clone = d1.importNode(e, True)
        if entry_name in found_entries:
            entries1.replaceChild(entry_clone, found_entries[entry_name])
        else:
            line_break = d1.createTextNode(u'\n%*s' % (ENTRY_INDENT,' '))
            entries1.insertBefore(line_break, entries1.lastChild)
            entries1.insertBefore(entry_clone, entries1.lastChild)
            found_entries[entry_name] = entry_clone

