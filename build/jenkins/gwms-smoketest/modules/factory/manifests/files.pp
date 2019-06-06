class factory::files{
  $condor_tarball_version = $factory::vars::condor_tarball_version
  

  file { '/etc/gwms-factory/config.d':
    ensure  => directory,
    owner   => 'gfactory',
    mode    => '0755',
    require => Package['glideinwms-factory'],
  }

  file { '/etc/condor/privsep_config':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('factory/etc.condor.privsep_config.erb'),
  }

  file { '/etc/condor/certs/condor_mapfile':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('factory/etc.condor.certs.condor_mapfile.erb'),
  }

  file { '/etc/gwms-factory/config.d/Condor_Tarballs.xml':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('factory/Condor_Tarballs.xml.erb'),
  }

  file { '/etc/gwms-factory/config.d/Dev_Sites2.xml':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('factory/Dev_Sites2.xml.erb'),
  }

  file { '/etc/gwms-factory/config.d/Dev_Sites3.xml':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('factory/Dev_Sites3.xml.erb'),
  }

  file { "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat6-stripped.tar.gz":
    ensure  => present, 
    owner   => 'gfactory',
    mode    => '0644',
    require => Package['glideinwms-factory'],
    source => "https://jobsub.fnal.gov/other/condor-${condor_tarball_version}-x86_64_RedHat6-stripped.tar.gz",
  }

  file { "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat6-stripped":
    ensure  => present,
    owner   => 'gfactory',
    mode    => '0755',
    require  => Exec['unwind_tarball_6'],
  }

  exec { 'unwind_tarball_6':
    command => "tar -xvf /var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat6-stripped.tar.gz -C /var/lib/gwms-factory/condor",
    path => [ '/bin', '/usr/bin'],
    subscribe => File["/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat6-stripped.tar.gz"],
    creates => "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat6-stripped", 
  }

  file { "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat7-stripped":
    ensure  => present,
    owner   => 'gfactory',
    mode    => '0755',
    require    => Exec['unwind_tarball_7'],
  }

  exec { 'unwind_tarball_7':
    command => "tar -xvf /var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat7-stripped.tar.gz -C /var/lib/gwms-factory/condor/",
    path => [ '/bin', '/usr/bin'],
    subscribe => File["/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat7-stripped.tar.gz"],
    creates => "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat7-stripped", 
  }

  file { "/var/lib/gwms-factory/condor/condor-${condor_tarball_version}-x86_64_RedHat7-stripped.tar.gz":
    ensure  => present,
    owner   => 'gfactory',
    mode    => '0644',
    require => Package['glideinwms-factory'],
    source => "https://jobsub.fnal.gov/other/condor-${condor_tarball_version}-x86_64_RedHat7-stripped.tar.gz",
  }

}


