#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 3 ]]; then
  echo "Usage: $0 INSTANCE_ID INSTANCE_PROFILE_NAME AWS_REGION" >&2
  exit 1
fi

instance_id="$1"
profile_name="$2"
aws_region="$3"

current_association="$({
  aws ec2 describe-iam-instance-profile-associations \
    --region "${aws_region}" \
    --filters "Name=instance-id,Values=${instance_id}" \
    --query 'IamInstanceProfileAssociations[0].AssociationId' \
    --output text
} 2>/dev/null || true)"

if [[ -n "${current_association}" && "${current_association}" != "None" ]]; then
  echo "The instance already has an IAM profile association: ${current_association}" >&2
  echo "Review its permissions before replacing it. No change was made." >&2
  exit 2
fi

aws ec2 associate-iam-instance-profile \
  --region "${aws_region}" \
  --instance-id "${instance_id}" \
  --iam-instance-profile "Name=${profile_name}"

