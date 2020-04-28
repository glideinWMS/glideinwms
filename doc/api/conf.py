extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.autosummary',
]
# The src directories are linked in this directory
# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
#sys.path.insert(0, u'/Users/marcom/prog/repos/git-gwms/gwms191003/glideinwms/doc/api/glideinwms')
sys.path.insert(0, os.path.abspath('.'))

# To add summaries:
autosummary_generate = True

# The name of the entry point, without the ".rst" extension.
# By convention this will be "index"
master_doc = "index"
# This values are all used in the generated documentation.
# Usually, the release and version are the same,
# but sometimes we want to have the release have an "rc" tag.
project = "GlideinWMS"
copyright = "2020, The GlideinWMS Team, Fermilab"
author = "The GlideinWMS Team"
version = release = "3.6.2"

