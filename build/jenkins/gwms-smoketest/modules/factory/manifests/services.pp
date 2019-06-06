class factory::services{


  $release_major = $facts['os']['release']['major']

  case $release_major{
     '6': {
       $upgrade_factory_command = '/sbin/service gwms-factory upgrade'
       $reconfig_factory_command = '/sbin/service gwms-factory reconfig'
     }
     '7': {
       $upgrade_factory_command = '/usr/sbin/gwms-factory upgrade'
       $reconfig_factory_command = '/sbin/systemctl reload  gwms-factory'
     }
     'default': {
       $upgrade_factory_command = '/sbin/service gwms-factory upgrade'
       $reconfig_factory_command = '/sbin/service gwms-factory reconfig'
     }
   }

  service{'condor':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }


  service{'gwms-factory':
    ensure     => stopped,
    enable     => false,
    hasstatus  => true,
    hasrestart => true,
    notify => Exec['upgrade-factory'],
  }


  exec{'upgrade-factory':
     command => $upgrade_factory_command,
     notify => Exec['start-factory'],
     require => Service['gwms-factory'],
   }

   exec { 'start-factory':
     command => '/sbin/service gwms-factory start',
     notify => Exec['reconfig-factory'],
   }

  exec { 'reconfig-factory' :
    command => $reconfig_factory_command,
  }

  service{'httpd':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }

}

