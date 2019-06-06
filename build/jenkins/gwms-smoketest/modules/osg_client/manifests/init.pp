# == Class: osg_client
#
# Full description of class osg_client here.
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
class osg_client($osg_version='3.4')  {
    class { 'osg_client::vars' : }
    class { 'osg_client::packages' : }
    class { 'osg_client::files' : }
    class { 'osg_client::services' : }

}

