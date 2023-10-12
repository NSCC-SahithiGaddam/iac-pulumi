# iac-pulumi
### git clone git@github.com:sahithir27/iac-pulumi.git

## Installations
### Install AWS-CLI
- curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o "AWSCLIV2.pkg"
- sudo installer -pkg AWSCLIV2.pkg -target /

### Install pulumi
- brew install pulumi/tap/pulumi
- pip install pulumi-aws

## Setup

### Select Stacks
-dev : pulumi stack select dev
-demo : pulumi stack select demo

### Create infra
-pulumi up

### Delete infra
-pulumi destroy




