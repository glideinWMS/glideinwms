class osg_htcondor_ce::services{
  service{'condor-ce':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
    require => Package['osg-ce-condor'],
    notify => Exec['osg-configure'],
  }

  exec { 'osg-configure':
    command => '/usr/sbin/osg-configure -c',
  }

  service{'iptables':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }

}

