class factory::packages {


    package { 'glideinwms-factory' :
      ensure => 'present',
    }

    package { 'glideinwms-factory-condor' :
      ensure => 'present',
    }

  

}
