class osg_client::packages {

    package { 'epel-release.noarch':
      ensure   => 'installed',
      provider => 'rpm',
      source   => "$osg_client::vars::epel_url",
    }

    package { 'osg-release.noarch':
      ensure   => 'installed',
      provider => 'rpm',
      source   => "$osg_client::vars::osg_url",
      notify   => Exec['yum-clean-all'],
    }

    exec { 'yum-clean-all':
      command => '/usr/bin/yum clean all',
    }

    package { 'fermilab-util_kx509.noarch' :
      ensure => 'present',
    }

    package { 'fetch-crl' :
      ensure => 'present',
    }


    package {'git': ensure => present}
    package { 'cvmfs-config-osg': ensure => present}
    package { 'cvmfs':
      ensure => present,
      require => Package['cvmfs-config-osg'],
    }



    package { 'condor':
      ensure          => present,
      install_options => '--enablerepo=osg',
    }


    package { 'voms-clients-cpp':
      install_options => '--enablerepo=osg',
    }

    package { 'osg-ca-scripts':
      ensure          => present,
      install_options => '--enablerepo=osg',
    }
  

    package { 'osg-wn-client':
      ensure          => present,
      install_options => '--enablerepo=osg',
    }
}
