# Selecting Ubuntu 18:04 as the base OS, current default in GitHub (evaluate switching to 20.04) 
FROM ubuntu:18.04 
MAINTAINER The GlideinWMS team "glideinwms-support@fnal.gov"
LABEL description="This is custom Docker Image for running GitHub actions locally"
 
# Install the required packages to be a runner for GitHub actions
# https://github.com/actions/virtual-environments/blob/main/images/linux/Ubuntu1804-README.md

# Update Ubuntu Software repository
RUN apt update

RUN apt install -y curl

# To get the latest git (2.29.2 as of 2020-12-20), git-lfs, git-ftp
RUN apt-get update &&\
    apt-get install software-properties-common &&\
    add-apt-repository ppa:git-core/ppa -y &&\
    apt-get update &&\
    apt-get install git -y ;\
    curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash ;\
    apt-get install -y --no-install-recommends git-lfs ;\
    apt-get install git-ftp -y
    
RUN apt-get install -y --no-install-recommends python python-dev python-pip python3 python3-dev python3-pip python3-venv;\
    export PIPX_BIN_DIR=/opt/pipx_bin;\
    export PIPX_HOME=/opt/pipx;\
    python3 -m pip install pipx;\
    python3 -m pipx ensurepath;\
    setEtcEnvironmentVariable "PIPX_BIN_DIR" $PIPX_BIN_DIR;\
    setEtcEnvironmentVariable "PIPX_HOME" $PIPX_HOME;\
    prependEtcEnvironmentPath $PIPX_BIN_DIR

RUN curl -sL https://deb.nodesource.com/setup_14.x | bash - &&\
    apt -y install nodejs &&\
    apt -y install gcc g++ make

RUN curl -sL https://dl.yarnpkg.com/debian/pubkey.gpg | apt-key add - &&\
    echo "deb https://dl.yarnpkg.com/debian/ stable main" | tee /etc/apt/sources.list.d/yarn.list &&\
    apt update && apt install yarn


# Default entry point 
CMD ["/bin/bash"] 


# build info
RUN echo "Source: glideinwms/gwms-actions" > /image-source-info.txt
RUN echo "Timestamp:" `date --utc` | tee /image-build-info.txt
