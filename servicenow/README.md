# ServiceNow Configuration

## Completed foundation

- Scoped application: Linux Software Installation Pipeline
- Roles: user, approver, admin
- Tables: Approved Software, Linux Server, Installation Request
- Approval group: Linux Software Approvers

## Required completion steps

1. Add a Linux Server record for the active RHEL EC2 target.
2. Add an Approved Software record for the published RPM and its SHA-256.
3. Create system properties:
   - `x_2276806_linux_0.aws_api_endpoint`
   - `x_2276806_linux_0.aws_api_key` (encrypted property)
4. Create a Flow Designer action named `Submit Approved Linux Installation`.
5. Add inputs matching the fields used in `outbound_rest_action.js`.
6. Add a Script step and paste `outbound_rest_action.js`.
7. Create a record-triggered flow for Installation Request:
   - trigger when a request is created
   - ask the Approval Group for approval
   - on rejection set Approval and Execution Status to rejected
   - on approval set Execution Status to approved
   - execute `Submit Approved Linux Installation`
   - store the returned AWS request ID and schedule name
8. Configure an integration user whose credentials are stored only in AWS
   Secrets Manager. Give it update access only to the Installation Request table.

## Callback fields

The AWS status Lambda updates:

- `execution_status`
- `ansible_job_id`
- `execution_started`
- `execution_completed`
- `installed_version`
- `installation_changed_server`
- `error_message`
- `execution_log_url`
- `callback_received`

## Developer-instance limitation

Some personal developer instances do not include paid IntegrationHub spokes.
The supplied scripted REST action uses the built-in `RESTMessageV2` API and does
not depend on a paid spoke.

