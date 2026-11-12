# Controlled Linux Software Installation Pipeline

An enterprise-style proof of concept for installing approved RPM software on
RHEL servers through ServiceNow approvals, AWS orchestration, Ansible, and JFrog
Artifactory.

## Business problem

Direct software installation from public repositories creates security,
licensing, audit, and operational risks. This project makes the request,
approval, package source, execution window, installer, and result traceable.

## Runtime flow

1. A requester selects an approved package and target server in ServiceNow.
2. An approver accepts or rejects the request.
3. ServiceNow sends an authenticated JSON request to API Gateway.
4. Lambda validates and stores the request in DynamoDB.
5. EventBridge Scheduler invokes the execution Lambda at the approved time.
6. The execution Lambda starts `AWS-ApplyAnsiblePlaybooks` through Systems
   Manager on the target RHEL node.
7. Ansible installs the exact package version from the JFrog virtual RPM
   repository and verifies the installed version.
8. A status Lambda records completion and updates ServiceNow.

## Components

| Directory | Purpose |
|---|---|
| `rpm/` | Linux inventory agent source and RPM packaging |
| `ansible/` | Idempotent installation and inventory playbooks |
| `aws/lambdas/` | Request, execution, and completion handlers |
| `aws/infrastructure/` | Terraform for AWS resources |
| `servicenow/` | ServiceNow integration scripts and setup guide |
| `scripts/` | Local bootstrap and validation utilities |
| `tests/` | Automated unit tests |
| `docs/` | Architecture, operations, and handoff documentation |

## Security controls

- Exact version installation; never `latest`
- JFrog virtual repository as the approved package source
- Idempotency protection for duplicate requests
- Secrets Manager for integration credentials
- Systems Manager instead of inbound automation SSH
- DynamoDB audit state and CloudWatch logs
- No credentials, private keys, tokens, or local inventories in Git

## Quick start

1. Read [`docs/deployment-guide.md`](docs/deployment-guide.md).
2. Build and publish the RPM using [`rpm/linux-inventory-agent/build.sh`](rpm/linux-inventory-agent/build.sh).
3. Bootstrap the existing RHEL target with [`scripts/bootstrap-rhel-target.sh`](scripts/bootstrap-rhel-target.sh).
4. Create required secrets and apply Terraform.
5. Complete the ServiceNow configuration in [`servicenow/README.md`](servicenow/README.md).

## Current development target

The sanitized server handoff is in [`docs/server-handoff.md`](docs/server-handoff.md).
Actual IP addresses and key paths belong only in ignored local files.

