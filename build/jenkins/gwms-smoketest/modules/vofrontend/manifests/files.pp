class vofrontend::files{
  
  user {'frontend':
    ensure => present,
  }

  $thome = '/var/lib/testuser'
  $tdir = "${thome}/testjobs"
  $tout = "${tdir}/joboutput"
  $t_dirs = [ $thome, $tdir, $tout, ]

  user {'testuser':
    ensure => present,
    home => $thome,
  }


  file { $t_dirs :
    ensure => directory,
    owner => 'testuser',
    mode => '0644',
    require => User['testuser'],
  }


  file { "${tdir}/testjob.singularity.jdf":
    ensure => file,
    owner => 'testuser',
    mode => '0644',
    content => template('vofrontend/var.lib.testjobs.testjob.singularity.jdf.erb'),
    require => File[$tdir],
  }

  $jobfiles = [ "${tdir}/el6_osg33.sh" ,"${tdir}/el7_osg33.sh", "${tdir}/el6_osg34.sh" ,"${tdir}/el7_osg34.sh", ]

  file { $jobfiles:
    ensure => file,
    owner => 'testuser',
    mode => '0755',
    content => template('vofrontend/system-info.sh.erb'),
    require => File[$tdir],
  }

  file { '/etc/sysconfig/iptables':
    ensure => file,
    owner  => root,
    content => template('vofrontend/etc.sysconfig.iptables.erb')
  }

  file { '/etc/condor/certs/condor_mapfile':
    ensure  => file,
    owner   => 'root',
    mode    => '0644',
    content => template('vofrontend/etc.condor.certs.condor_mapfile.erb'),
  }

  file { '/etc/gwms-frontend/frontend.xml':
    ensure  => file,
    owner   => 'frontend',
    mode    => '0644',
    content => template('vofrontend/frontend.xml.erb'),
    require => Package['glideinwms-vofrontend'],
  }

  file { '/tmp/vo_proxy':
    ensure  => file,
    owner   => 'frontend',
    mode    => '0600',
  }

  file { '/tmp/frontend_proxy':
    ensure  => file,
    owner   => 'frontend',
    mode    => '0600',
  }

  file { '/tmp/grid_proxy':
    ensure  => file,
    owner   => 'testuser',
    mode    => '0600',
  }

}


