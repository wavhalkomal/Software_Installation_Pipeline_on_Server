# Architecture

```mermaid
flowchart TD
    SN[ServiceNow request and approval] --> APIGW[API Gateway]
    APIGW --> REQ[Request Lambda]
    REQ --> DB[(DynamoDB audit ledger)]
    REQ --> SCH[EventBridge Scheduler]
    SCH --> EXEC[Execution Lambda]
    EXEC --> SSM[AWS Systems Manager]
    SSM --> ANS[Ansible playbook on RHEL]
    ANS --> JF[JFrog virtual RPM repository]
    JF --> RHEL[RHEL target server]
    MON[Status Lambda] --> SSM
    MON --> DB
    MON --> SN
    RHEL --> CW[CloudWatch logs]
```

## Trust boundaries

| Boundary | Control |
|---|---|
| ServiceNow to AWS | HTTPS plus integration API key stored in Secrets Manager |
| AWS to RHEL | Systems Manager managed-node identity and IAM |
| RHEL to JFrog | HTTPS and a read-only repository credential |
| Developer to GitHub | Feature branch, pull request, and automated validation |

## Why Systems Manager runs Ansible

`AWS-ApplyAnsiblePlaybooks` downloads the versioned playbook bundle from S3 and
runs Ansible locally on the managed node. This avoids a permanent Ansible
controller and inbound automation SSH while retaining readable, idempotent
Ansible automation.

