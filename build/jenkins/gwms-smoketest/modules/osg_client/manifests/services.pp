class osg_client::services{

  service{ 'fetch-crl-cron':
    ensure => true,
    enable => true,
    hasstatus => true,
    hasrestart => true,
    require => Package['fetch-crl'],
  }

  #service{ 'fetch-crl-boot':
  #  ensure => true,
  #  enable => true,
  #  hasstatus => true,
  #  hasrestart => true,
  #  require => Package['fetch-crl'],
  #}

  service{ 'osg-update-certs-cron':
    ensure => true,
    enable => true,
    hasstatus => true,
    hasrestart => true,
    require => Package['osg-ca-scripts'],
  }

  service{'condor':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }

  service{'iptables':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }

  service{'autofs':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
    require => Package['cvmfs'],
    notify => Exec['start-cvmfs'],
  }

  exec { 'start-cvmfs':
    command => '/usr/bin/cvmfs_config setup',
  }

}

