
export GROUP=$1
export EXPERIMENT=$1
unset X509_USER_PROXY
rm -f /tmp/x509up_u`id -u`
kx509

#supported_groups = 'admx annie argoneut captmnv cdf cdms chips coupp darkside des dune dzero fermilab genie gm2 icarus lar1 lar1nd lariat lsst marsaccel marsgm2 marslbne marsmu2e minerva miniboone minos mu2e numix noble nova patriot sbnd seaquest test uboone'

case $GROUP in 
    cdf|des|dune|fermilab|lsst)
        export VOMS="${GROUP}:/${GROUP}/Role=Analysis"
        ;;
    marsaccel)
        export VOMS="fermilab:/fermilab/mars/accel"
        ;;
    marsgm2)
        export VOMS="fermilab:/fermilab/mars/gm2"
        ;;
    marslbne)
        export VOMS="fermilab:/fermilab/mars/lbne"
        ;;
    marsmu2e)
        export VOMS="fermilab:/fermilab/mars/mu2e"
        ;;
    dzero)
        export VOMS="dzero:/dzero/users"
        ;;
    *)
        export VOMS="fermilab:/fermilab/${GROUP}/Role=Analysis"
        ;;
esac

voms-proxy-init -noregen -rfc -ignorewarn -valid 172:00 -bits 1024 -voms "$VOMS" -out "/tmp/${GROUP}_proxy"
export X509_USER_PROXY="/tmp/${GROUP}_proxy"
voms-proxy-info -all
