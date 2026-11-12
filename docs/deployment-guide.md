# Deployment Guide

## 1. Prerequisites

- AWS CLI authenticated to the intended account
- Terraform 1.6 or newer
- Docker Desktop
- JFrog Artifactory RPM repositories:
  - local: `linux-approved-local`
  - virtual: `linux-approved-virtual`
- Existing RHEL 9 target
- ServiceNow personal developer instance

## 2. Build the inventory-agent RPM

```bash
cd rpm/linux-inventory-agent
chmod +x build.sh
./build.sh
```

The result is written under `dist/`. Upload the RPM to
`linux-approved-local`, then recalculate the repository index. Record its
SHA-256 value in the ServiceNow Approved Software table.

## 3. Bootstrap the RHEL target

Copy the bootstrap script to the node and run it with sudo:

```bash
scp -i /path/to/key.pem scripts/bootstrap-rhel-target.sh ec2-user@PUBLIC_IP:/tmp/
ssh -i /path/to/key.pem ec2-user@PUBLIC_IP
sudo bash /tmp/bootstrap-rhel-target.sh
```

Attach the instance profile created by Terraform, then verify:

```bash
sudo systemctl status amazon-ssm-agent
free -h
swapon --show
```

## 4. Create secrets

Create these Secrets Manager entries before Terraform apply:

- Integration API secret containing the single API-key string.
- ServiceNow secret containing JSON:

```json
{
  "instance_url": "https://INSTANCE.service-now.com",
  "username": "integration.user",
  "password": "replace-me",
  "table": "x_scope_installation_request"
}
```

Do not commit secret values.

## 5. Deploy AWS resources

```bash
cd aws/infrastructure
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init
terraform fmt -check
terraform validate
terraform plan -out=deployment.tfplan
terraform apply deployment.tfplan
```

Terraform creates the API, Lambdas, DynamoDB table, Scheduler role, S3 playbook
bucket, log group, and managed-node IAM profile association.

## 6. Configure JFrog on RHEL

Use a read-only JFrog service credential. Create
`/etc/yum.repos.d/linux-approved.repo` with permissions `0600`:

```ini
[linux-approved-virtual]
name=Approved Linux Software
baseurl=https://JFROG_HOST/artifactory/api/yum/linux-approved-virtual
enabled=1
gpgcheck=0
sslverify=1
```

`gpgcheck=0` is acceptable only for this POC until RPM signing is configured.
Production must use signed RPMs and `gpgcheck=1`.

## 7. Configure ServiceNow

Follow `servicenow/README.md`, using the Terraform `api_endpoint` output.

## 8. End-to-end acceptance test

1. Create an Approved Software record.
2. Create a Linux Server record with the current instance details.
3. Submit an Installation Request.
4. Approve it.
5. Confirm DynamoDB status changes from `approved` to `scheduled`, `running`,
   and `successful`.
6. Confirm the exact RPM version is installed on RHEL.
7. Confirm ServiceNow receives the completion fields.

