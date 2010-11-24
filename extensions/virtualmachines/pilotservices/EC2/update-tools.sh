#!/bin/bash
# Version : $Rev: 45328 $

# Update ec2-ami-tools autmatically.
[ -f ec2-ami-tools.noarch.rpm ] && rm -f ec2-ami-tools.noarch.rpm
echo "Attempting ami-utils update from S3"|logger -s -t "ec2"
(wget --quiet http://s3.amazonaws.com/ec2-downloads/ec2-ami-tools.noarch.rpm && echo "Retreived ec2-ami-tools from S3" || echo "Unable to retreive ec2-ami-tools from S3")|logger -s -t "ec2" 2>/dev/null
(rpm -U ec2-ami-tools.noarch.rpm 2>/dev/null && echo "Updated ec2-ami-tools from S3" || echo "ec2-ami-tools already up to date")|logger -s -t "ec2"

