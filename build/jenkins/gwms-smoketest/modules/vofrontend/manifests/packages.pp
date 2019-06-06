class vofrontend::packages {


    package { 'glideinwms-vofrontend' :
      ensure => 'present',
    }

    package { 'condor-python' :
      ensure => 'present',
    }
}
