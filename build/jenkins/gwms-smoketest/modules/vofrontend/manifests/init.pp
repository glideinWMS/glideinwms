# == Class:vofrontend 
#
# Full description of class vofrontend here.
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
class vofrontend($fact_fqdn='FIXME', 
                  $vofe_fqdn='FIXME', 
                  $vofe_dn='FIXME', 
                  $dn_rt='/DC=org/DC=incommon/C=US/ST=IL/L=Batavia/O=Fermi Research Alliance/OU=Fermilab')  {
    class { 'vofrontend::vars' : }
    class { 'vofrontend::packages' : }
    class { 'vofrontend::files' : }
    class { 'vofrontend::services' : }


}

