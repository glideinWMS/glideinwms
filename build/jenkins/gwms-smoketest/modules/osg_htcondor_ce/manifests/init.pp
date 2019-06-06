# == Class: osg_htcondor_ce
#
# Full description of class osg_htcondor_ce here.
#
# === Parameters
#
# Document parameters here.
#
# [*sample_parameter*]
#   Explanation of what this parameter affects and what it defaults to.
#   e.g. "Specify one or more upstream ntp servers as an array."
#
# === Variables
#
# Here you should define a list of variables that this module would require.
#
#
# Author Name <author@domain.com>
#
# === Copyright
#
# Copyright 2016 Your name here, unless otherwise noted.
#
class osg_htcondor_ce {
    class { 'osg_htcondor_ce::vars' : }
    class { 'osg_htcondor_ce::packages' : }
    class { 'osg_htcondor_ce::files' : }
    class { 'osg_htcondor_ce::services' : }
}

