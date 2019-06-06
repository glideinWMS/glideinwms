class osg_htcondor_ce::files{

#
#for F in $('ls templates/'); do FN=$('echo $F| sed -e 's/.erb//' -e 's/etc./\/etc\//' -e 's/sysconfig./sysconfig\//' -e 's/osg.config.d./osg\/config.d\//' ');  echo "  file { \"$FN\" :" ; echo "    ensure => file,"; echo "    owner   => 'root',";echo "    mode    => '0644',"; echo "    content => template('osg_htcondor_ce/$F'),"; echo "  }"; echo;  done
#
  file { "/etc/blah.config" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.blah.config.erb'),
  }

  file { "/etc/osg/config.d/01-squid.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.01-squid.ini.erb'),
  }

  file { "/etc/osg/config.d/10-gateway.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.10-gateway.ini.erb'),
  }

  file { "/etc/osg/config.d/10-misc.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.10-misc.ini.erb'),
  }

  file { "/etc/osg/config.d/10-storage.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.10-storage.ini.erb'),
  }

  file { "/etc/osg/config.d/20-condor.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.20-condor.ini.erb'),
  }

  file { "/etc/osg/config.d/30-gip.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.30-gip.ini.erb'),
  }

  file { "/etc/osg/config.d/30-gratia.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.30-gratia.ini.erb'),
  }

  file { "/etc/osg/config.d/30-infoservices.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.30-infoservices.ini.erb'),
  }

  file { "/etc/osg/config.d/40-localsettings.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.40-localsettings.ini.erb'),
  }

  file { "/etc/osg/config.d/40-siteinfo.ini" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.osg.config.d.40-siteinfo.ini.erb'),
  }

  file { "/etc/sysconfig/condor-ce" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.sysconfig.condor-ce.erb'),
  }

  file { "/etc/condor/config.d/99-condor-ce.conf" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.condor.config.d.99-condor-ce.conf.erb'),
  }

  file { "/etc/condor-ce/config.d/99-local.conf" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.condor-ce.config.d.99-local.conf.erb'),
  }

  file { "/etc/lcmaps.db" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.lcmaps.db.erb'),
  }
  file { "/etc/grid-security/grid-mapfile" :
    ensure => file,
    owner   => 'root',
    mode    => '0644',
    content => template('osg_htcondor_ce/etc.grid-security.grid-mapfile.erb'),
  }

  file { '/etc/sysconfig/iptables' :
    ensure  => file,
    notify  => Service['iptables'],
    owner   => root,
    group   => root,
    mode    => '0600',
    content => template('osg_htcondor_ce/etc.sysconfig.iptables.erb'),
  }



  file { "/opt/osg" :
    ensure => directory,
    owner   => 'root',
    mode    => '0755',
  }
  file { "/opt/osg/app" :
    ensure => directory,
    owner   => 'root',
    mode    => '0777',
  }
  file { "/opt/osg/app/etc" :
    ensure => directory,
    owner   => 'root',
    mode    => '0777',
  }

  group{ 'fermilab': ensure=> present, }
  user { 'fermilab': ensure => present, require => Group['fermilab'], }
  group{ 'osg': ensure=> present, }
  user { 'osg': ensure => present, require => Group['osg'], }
}
