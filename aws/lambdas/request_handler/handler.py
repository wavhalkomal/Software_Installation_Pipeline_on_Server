"""Validate, deduplicate, persist, and schedule approved installation requests."""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key


dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
scheduler = boto3.client("scheduler")
secrets = boto3.client("secretsmanager")
table = dynamodb.Table(os.environ["TABLE_NAME"])

PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+\-]{0,127}$")
INSTANCE_PATTERN = re.compile(r"^i-[0-9a-f]{8,17}$")
REQUIRED_FIELDS = {
    "request_id",
    "idempotency_key",
    "servicenow_sys_id",
    "instance_id",
    "package_name",
    "package_version",
    "requested_execution_time",
    "approval_status",
}


def response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def parse_body(event: dict) -> dict:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    return json.loads(raw_body)


def expected_api_key() -> str:
    return secrets.get_secret_value(SecretId=os.environ["API_KEY_SECRET_ARN"])["SecretString"]


def validate(payload: dict) -> list[str]:
    errors = [f"missing field: {field}" for field in sorted(REQUIRED_FIELDS - payload.keys())]
    if payload.get("approval_status") != "approved":
        errors.append("approval_status must be approved")
    if payload.get("package_name") and not PACKAGE_PATTERN.fullmatch(payload["package_name"]):
        errors.append("package_name contains unsupported characters")
    if payload.get("package_version") and not PACKAGE_PATTERN.fullmatch(payload["package_version"]):
        errors.append("package_version contains unsupported characters")
    if payload.get("instance_id") and not INSTANCE_PATTERN.fullmatch(payload["instance_id"]):
        errors.append("instance_id is invalid")
    try:
        datetime.fromisoformat(payload.get("requested_execution_time", "").replace("Z", "+00:00"))
    except ValueError:
        errors.append("requested_execution_time must be ISO-8601")
    return errors


def handler(event, _context):
    headers = {key.lower(): value for key, value in (event.get("headers") or {}).items()}
    if headers.get("x-api-key") != expected_api_key():
        return response(401, {"error": "unauthorized"})

    try:
        payload = parse_body(event)
    except (ValueError, TypeError, json.JSONDecodeError):
        return response(400, {"error": "invalid JSON body"})

    errors = validate(payload)
    if errors:
        return response(400, {"error": "validation failed", "details": errors})

    duplicate = table.query(
        IndexName="IdempotencyIndex",
        KeyConditionExpression=Key("idempotency_key").eq(payload["idempotency_key"]),
        Limit=1,
    ).get("Items", [])
    if duplicate:
        return response(200, {"request_id": duplicate[0]["request_id"], "duplicate": True})

    execution_time = datetime.fromisoformat(payload["requested_execution_time"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    item = {
        **payload,
        "execution_status": "approved",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    table.put_item(Item=item, ConditionExpression="attribute_not_exists(request_id)")

    invoke_payload = {"request_id": payload["request_id"]}
    schedule_name = None
    if execution_time <= now:
        lambda_client.invoke(
            FunctionName=os.environ["EXECUTION_FUNCTION_ARN"],
            InvocationType="Event",
            Payload=json.dumps(invoke_payload).encode("utf-8"),
        )
        next_status = "queued"
    else:
        schedule_name = f"linux-install-{payload['request_id']}"[:64]
        scheduler.create_schedule(
            Name=schedule_name,
            GroupName=os.environ["SCHEDULE_GROUP_NAME"],
            Description=f"Approved Linux installation {payload['request_id']}",
            ScheduleExpression=f"at({execution_time.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')})",
            ScheduleExpressionTimezone="UTC",
            FlexibleTimeWindow={"Mode": "OFF"},
            ActionAfterCompletion="DELETE",
            Target={
                "Arn": os.environ["EXECUTION_FUNCTION_ARN"],
                "RoleArn": os.environ["SCHEDULER_ROLE_ARN"],
                "Input": json.dumps(invoke_payload),
                "RetryPolicy": {"MaximumRetryAttempts": 2, "MaximumEventAgeInSeconds": 3600},
            },
        )
        next_status = "scheduled"

    table.update_item(
        Key={"request_id": payload["request_id"]},
        UpdateExpression="SET execution_status=:status, eventbridge_schedule_name=:schedule, updated_at=:updated",
        ExpressionAttributeValues={
            ":status": next_status,
            ":schedule": schedule_name or "",
            ":updated": datetime.now(timezone.utc).isoformat(),
        },
    )
    return response(
        202,
        {
            "request_id": payload["request_id"],
            "execution_status": next_status,
            "eventbridge_schedule_name": schedule_name,
        },
    )

