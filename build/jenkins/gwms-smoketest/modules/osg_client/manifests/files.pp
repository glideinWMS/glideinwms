class osg_client::files{
  


  $esg = '/etc/grid-security'
  exec { 'setupCA':
    command => '/usr/sbin/osg-ca-manage setupCA --location root --url osg',
    require => [ Package['osg-ca-scripts'] ],
  }

    
  file { '/etc/sysconfig/iptables' :
    ensure  => file,
    notify  => Service['iptables'],
    owner   => root,
    group   => root,
    mode    => '0600',
    content => template('osg_client/etc.sysconfig.iptables.erb'),
  }

  file { '/etc/cvmfs/default.local':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    require => Package['cvmfs'],
    content => template('osg_client/etc.cvmfs.default.local.erb'),
  }



}
