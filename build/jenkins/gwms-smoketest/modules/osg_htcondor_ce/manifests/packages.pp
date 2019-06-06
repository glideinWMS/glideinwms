class osg_htcondor_ce::packages {

    package { 'osg-ce-condor' :
      ensure => 'present',
    }
    package{ 'osg-wn-client' :
      ensure => 'present',
    }
    package { 'llrun' :
      ensure => 'present',
    }
    package { 'lcmaps' :
      ensure => 'present',
    }
    package { 'vo-client-lcmaps-voms' :
      ensure => 'present',
    }
    package { 'osg-configure-misc' :
      ensure => 'present',
    }
}
