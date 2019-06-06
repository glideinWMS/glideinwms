class vofrontend::services{

  $release_major = $facts['os']['release']['major']

  case $release_major{
     '6': {
       $upgrade_frontend_command = '/sbin/service gwms-frontend upgrade'
       $reconfig_frontend_command = '/sbin/service gwms-frontend reconfig'
     }
     '7': {
       $upgrade_frontend_command = 'gwms-frontend upgrade'
       $reconfig_frontend_command = 'systemctl reload gwms-frontend'
     }
     'default': {
       $upgrade_frontend_command = '/sbin/service gwms-frontend upgrade'
       $reconfig_frontend_command = '/sbin/service gwms-frontend reconfig'
     }
   }

  service{'condor':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
    requires => File['/etc/condor/certs/condor_mapfile'],
  }

  service {'iptables':
    ensure => true,
    enable => true,
    hasrestart => true,
    requires => File['/etc/sysconfig/iptables'],
  }

  service{'gwms-frontend':
    ensure     => stopped,
    enable     => false,
    hasstatus  => true,
    hasrestart => true,
    require => Package['glideinwms-vofrontend'],
    notify => Exec['upgrade-frontend'],
  }


  exec{'upgrade-frontend':
     command => $upgrade_frontend_command,
     notify => Exec['start-frontend'],
     require => Service['gwms-frontend'],
   }

   exec{ 'start-frontend':
     command => '/sbin/service gwms-frontend start',
     notify => Exec['reconfig-frontend'],
   }

  exec{'reconfig-frontend':
    command => $reconfig_frontend_command,
  }

  service{'httpd':
    ensure     => true,
    enable     => true,
    hasstatus  => true,
    hasrestart => true,
  }

}

