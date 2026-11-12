"""Monitor Systems Manager commands and send terminal status to ServiceNow."""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import boto3


dynamodb = boto3.resource("dynamodb")
ssm = boto3.client("ssm")
secrets = boto3.client("secretsmanager")
table = dynamodb.Table(os.environ["TABLE_NAME"])

SUCCESS = {"Success"}
FAILURE = {"Cancelled", "TimedOut", "Failed", "Cancelling", "Undeliverable", "Terminated"}


def running_requests() -> list[dict]:
    result = table.scan(
        FilterExpression="execution_status = :running",
        ExpressionAttributeValues={":running": "running"},
    )
    return result.get("Items", [])


def service_now_secret() -> dict | None:
    arn = os.environ.get("SERVICENOW_SECRET_ARN", "")
    if not arn:
        return None
    value = secrets.get_secret_value(SecretId=arn)["SecretString"]
    return json.loads(value)


def notify_service_now(item: dict, fields: dict) -> None:
    secret = service_now_secret()
    if not secret or not item.get("servicenow_sys_id"):
        return

    table_name = secret.get("table", "x_2276806_linux_0_installation_request")
    endpoint = (
        f"{secret['instance_url'].rstrip('/')}/api/now/table/{table_name}/"
        f"{item['servicenow_sys_id']}"
    )
    credentials = base64.b64encode(
        f"{secret['username']}:{secret['password']}".encode("utf-8")
    ).decode("ascii")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(fields).encode("utf-8"),
        method="PATCH",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(f"ServiceNow callback returned {response.status}")
    except urllib.error.URLError as error:
        raise RuntimeError(f"ServiceNow callback failed: {error}") from error


def handler(_event, _context):
    processed = []
    for item in running_requests():
        request_id = item["request_id"]
        try:
            invocation = ssm.get_command_invocation(
                CommandId=item["ansible_job_id"],
                InstanceId=item["instance_id"],
            )
        except ssm.exceptions.InvocationDoesNotExist:
            continue

        status = invocation["Status"]
        if status not in SUCCESS | FAILURE:
            continue

        completed_at = datetime.now(timezone.utc).isoformat()
        execution_status = "successful" if status in SUCCESS else "failed"
        error_message = "" if status in SUCCESS else (
            invocation.get("StandardErrorContent") or invocation.get("StatusDetails", status)
        )[:4000]
        log_url = (
            f"https://console.aws.amazon.com/cloudwatch/home?region={item.get('aws_region', 'us-east-1')}"
            f"#logsV2:log-groups/log-group/{os.environ['COMMAND_LOG_GROUP'].replace('/', '$252F')}"
        )

        table.update_item(
            Key={"request_id": request_id},
            UpdateExpression=(
                "SET execution_status=:status, execution_completed=:completed, "
                "error_message=:error, execution_log_url=:log, updated_at=:updated"
            ),
            ExpressionAttributeValues={
                ":status": execution_status,
                ":completed": completed_at,
                ":error": error_message,
                ":log": log_url,
                ":updated": completed_at,
            },
        )
        callback_fields = {
            "execution_status": execution_status,
            "ansible_job_id": item["ansible_job_id"],
            "execution_started": item.get("execution_started", ""),
            "execution_completed": completed_at,
            "installed_version": item.get("package_version", "") if execution_status == "successful" else "",
            "installation_changed_server": execution_status == "successful",
            "error_message": error_message,
            "execution_log_url": log_url,
            "callback_received": True,
        }
        notify_service_now(item, callback_fields)
        processed.append({"request_id": request_id, "execution_status": execution_status})

    return {"processed": processed}

