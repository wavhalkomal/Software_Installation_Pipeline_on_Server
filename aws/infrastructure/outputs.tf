output "api_endpoint" {
  value = "${aws_apigatewayv2_api.installations.api_endpoint}/installations"
}

output "request_table" {
  value = aws_dynamodb_table.requests.name
}

output "playbook_bucket" {
  value = aws_s3_bucket.playbooks.bucket
}

output "managed_node_instance_profile" {
  value = aws_iam_instance_profile.managed_node.name
}

