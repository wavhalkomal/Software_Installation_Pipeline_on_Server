"""Start the approved Ansible installation through AWS Systems Manager."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import boto3


dynamodb = boto3.resource("dynamodb")
ssm = boto3.client("ssm")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def update_failure(request_id: str, message: str) -> None:
    table.update_item(
        Key={"request_id": request_id},
        UpdateExpression="SET execution_status=:status, error_message=:error, updated_at=:updated",
        ExpressionAttributeValues={
            ":status": "failed",
            ":error": message[:4000],
            ":updated": datetime.now(timezone.utc).isoformat(),
        },
    )


def handler(event, _context):
    request_id = event["request_id"]
    item = table.get_item(Key={"request_id": request_id}, ConsistentRead=True).get("Item")
    if not item:
        raise ValueError(f"Request {request_id} was not found")
    if item["execution_status"] in {"running", "successful"}:
        return {"request_id": request_id, "execution_status": item["execution_status"]}

    extra_variables = json.dumps(
        {
            "request_id": request_id,
            "package_name": item["package_name"],
            "package_version": item["package_version"],
            "approved_checksum": item.get("checksum_sha256", ""),
            "reboot_permitted": bool(item.get("reboot_permitted", False)),
        },
        separators=(",", ":"),
    )

    try:
        command = ssm.send_command(
            InstanceIds=[item["instance_id"]],
            DocumentName="AWS-ApplyAnsiblePlaybooks",
            TimeoutSeconds=3600,
            Parameters={
                "SourceType": ["S3"],
                "SourceInfo": [json.dumps({"path": os.environ["PLAYBOOK_S3_URL"]})],
                "InstallDependencies": ["True"],
                "PlaybookFile": ["playbooks/install_approved_software.yml"],
                "ExtraVariables": [extra_variables],
                "Check": ["False"],
                "Verbose": ["-v"],
                "TimeoutSeconds": ["3600"],
            },
            CloudWatchOutputConfig={
                "CloudWatchLogGroupName": os.environ["COMMAND_LOG_GROUP"],
                "CloudWatchOutputEnabled": True,
            },
            Comment=f"Approved Linux installation {request_id}",
        )
    except Exception as error:
        update_failure(request_id, str(error))
        raise

    command_id = command["Command"]["CommandId"]
    started_at = datetime.now(timezone.utc).isoformat()
    table.update_item(
        Key={"request_id": request_id},
        UpdateExpression=(
            "SET execution_status=:status, ansible_job_id=:command, "
            "execution_started=:started, updated_at=:updated"
        ),
        ExpressionAttributeValues={
            ":status": "running",
            ":command": command_id,
            ":started": started_at,
            ":updated": started_at,
        },
    )
    return {"request_id": request_id, "execution_status": "running", "command_id": command_id}

