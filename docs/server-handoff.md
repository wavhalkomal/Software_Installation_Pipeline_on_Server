# RHEL Target Server Handoff

| Property | Value |
|---|---|
| Instance name | TF-Instance |
| AWS region | us-east-1 |
| Availability Zone | us-east-1b |
| Operating system | Red Hat Enterprise Linux 9.8 |
| Architecture | x86_64 |
| Instance type | t2.micro |
| SSH user | ec2-user |
| Root disk | 30 GiB encrypted gp3 |
| Provisioning | Jenkins and Terraform |
| Environment | Development |

The instance ID, public IP, security-group ID, and private-key path are excluded
from this public repository. Store those values in ignored local configuration.

## Known prerequisite

The node previously had about 761 MiB usable RAM and no swap. DNF metadata
processing was killed by the kernel. Run `scripts/bootstrap-rhel-target.sh`
before installation testing; it creates and activates a 2 GiB swap file and
enables the Systems Manager agent.

