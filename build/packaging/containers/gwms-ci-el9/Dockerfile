# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

# Selecting AlmaLinux 9 as the base OS - x86_64 platform
FROM almalinux:9
MAINTAINER The GlideinWMS team "glideinwms-support@fnal.gov"

# Install the required RPMS and clean yum

# Base OSG 23 packages
RUN dnf install -y epel-release wget sed git yum-utils \
    https://repo.opensciencegrid.org/osg/23-main/osg-23-main-el9-release-latest.rpm && \
    dnf config-manager --set-enabled crb && \
    /bin/sed -i '/^enabled=1/a priority=99' /etc/yum.repos.d/epel.repo && \
    dnf -y install osg-ca-certs

# python3-devel required by rpmbuild and other sw needed by CI
# swig is used by pip to install m2crypto (TravisCI)
# Missing from base image: ps bc, cpp, bzip, sudo, which, pylint, python3-pycodestyle python3-m2crypto
RUN dnf -y install apptainer python3-rrdtool bats cpp swig procps bc bzip2 sudo which pylint python3-pycodestyle python3-m2crypto


# yum dep program needs to be added
# adding a GH actions runner for the ci tests
ADD shared/yumalldeps.sh shared/gha_ci_runner.sh shared/gha_build.sh /

# Specific dependencies for GlideinWMS will be added
# Devel version is in osg-contrib
# RUN /usr/bin/yumalldeps.sh -i -y "--enablerepo=osg-contrib" glideinwms-factory glideinwms-vofrontend
# Production version (Python 3.9, EL9)
RUN /yumalldeps.sh -i glideinwms-factory glideinwms-vofrontend

# Cleaning caches to reduce size of image
RUN yum clean all

# Adding test user
RUN useradd gwmsciuser

# Default entry point
CMD ["/bin/bash"]


# build info
RUN echo "Source: glideinwms/gwms-ci-el9" > /image-source-info.txt
RUN echo "Timestamp: $(date -u +'%Y-%m-%dT%H:%M:%SZ')" | tee /image-build-info.txt
