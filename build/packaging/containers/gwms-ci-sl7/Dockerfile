# Selecting SL7 as the base OS 
FROM scientificlinux/sl:7 
MAINTAINER The GlideinWMS team "glideinwms-support@fnal.gov"

# Install the quired RPMS and clean yum

# Base OSG 3.5 packages
RUN yum install -y wget sed git;\
    yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm;\
    yum install -y yum-priorities;\
    yum install -y https://repo.opensciencegrid.org/osg/3.5/osg-3.5-el7-release-latest.rpm;\
    yum install -y osg-ca-certs

# yum dep program needs to be added
ADD shared/yumalldeps.sh /usr/bin/yumalldeps.sh

# Specific dependencies for GlideinWMS will be added 
# Python 3 version is in osg-contrib
RUN /usr/bin/yumalldeps.sh -i -y "--enablerepo=osg-contrib" glideinwms-factory glideinwms-vofrontend
# Production version (Python 2)
RUN /usr/bin/yumalldeps.sh -i glideinwms-factory glideinwms-vofrontend

# Other sw needed by CI
RUN yum install -y bats

# Cleaning caches to reduce size of image
RUN yum clean all

# Default entry point 
CMD ["/bin/bash"] 


# build info
RUN echo "Source: mambelli/gwms-ci-sl7" > /image-source-info.txt
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt
