# Selecting Ubuntu 18:04 as the base OS, current default in GitHub (evaluate switching to 20.04) 
FROM ubuntu:18.04 
MAINTAINER The GlideinWMS team "glideinwms-support@fnal.gov"
LABEL description="This is custom Docker Image for running GitHub actions locally"
 
# Install the required packages to be a runner for GitHub actions
# https://github.com/actions/virtual-environments/blob/main/images/linux/Ubuntu1804-README.md

# Update Ubuntu Software repository
RUN apt update

RUN apt install -y git curl python python3
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
