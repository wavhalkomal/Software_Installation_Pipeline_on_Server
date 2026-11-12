locals {
  tags = {
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

data "aws_caller_identity" "current" {}

resource "aws_dynamodb_table" "requests" {
  name         = "${var.project_name}-requests"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  global_secondary_index {
    name            = "IdempotencyIndex"
    hash_key        = "idempotency_key"
    projection_type = "ALL"
  }

  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
  tags = local.tags
}

resource "aws_s3_bucket" "playbooks" {
  bucket_prefix = "${var.project_name}-playbooks-"
  force_destroy = true
  tags          = local.tags
}

resource "aws_s3_bucket_public_access_block" "playbooks" {
  bucket                  = aws_s3_bucket.playbooks.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "playbooks" {
  bucket = aws_s3_bucket.playbooks.id
  versioning_configuration { status = "Enabled" }
}

data "archive_file" "playbooks" {
  type        = "zip"
  source_dir  = "${path.module}/../../ansible"
  output_path = "${path.module}/ansible-playbooks.zip"
}

resource "aws_s3_object" "playbooks" {
  bucket = aws_s3_bucket.playbooks.id
  key    = "ansible/ansible-playbooks.zip"
  source = data.archive_file.playbooks.output_path
  etag   = data.archive_file.playbooks.output_md5
}

resource "aws_cloudwatch_log_group" "commands" {
  name              = "/${var.project_name}/ssm"
  retention_in_days = 30
  tags              = local.tags
}

resource "aws_iam_role" "managed_node" {
  name = "${var.project_name}-managed-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "managed_node_core" {
  role       = aws_iam_role.managed_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "managed_node_playbooks" {
  name = "read-playbook-bucket"
  role = aws_iam_role.managed_node.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:GetObjectVersion"]
      Resource = "${aws_s3_bucket.playbooks.arn}/*"
    }]
  })
}

resource "aws_iam_instance_profile" "managed_node" {
  name = "${var.project_name}-managed-node"
  role = aws_iam_role.managed_node.name
}

resource "aws_iam_role" "lambda" {
  name = "${var.project_name}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "orchestration"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = [aws_dynamodb_table.requests.arn, "${aws_dynamodb_table.requests.arn}/index/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:SendCommand", "ssm:GetCommandInvocation"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["scheduler:CreateSchedule", "scheduler:DeleteSchedule"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = aws_iam_role.scheduler.arn
      },
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = compact([var.integration_api_secret_arn, var.servicenow_secret_arn])
      }
    ]
  })
}

resource "aws_iam_role" "scheduler" {
  name = "${var.project_name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.tags
}

resource "aws_scheduler_schedule_group" "installations" {
  name = var.project_name
  tags = local.tags
}

data "archive_file" "request" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/request_handler"
  output_path = "${path.module}/request-handler.zip"
}

data "archive_file" "execution" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/execution_handler"
  output_path = "${path.module}/execution-handler.zip"
}

data "archive_file" "callback" {
  type        = "zip"
  source_dir  = "${path.module}/../lambdas/callback_handler"
  output_path = "${path.module}/callback-handler.zip"
}

resource "aws_lambda_function" "execution" {
  function_name    = "${var.project_name}-execution"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.execution.output_path
  source_code_hash = data.archive_file.execution.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      TABLE_NAME        = aws_dynamodb_table.requests.name
      PLAYBOOK_S3_URL   = "https://${aws_s3_bucket.playbooks.bucket_regional_domain_name}/${aws_s3_object.playbooks.key}"
      COMMAND_LOG_GROUP = aws_cloudwatch_log_group.commands.name
    }
  }
  tags = local.tags
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "invoke-execution-lambda"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.execution.arn
    }]
  })
}

resource "aws_lambda_function" "request" {
  function_name    = "${var.project_name}-request"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.request.output_path
  source_code_hash = data.archive_file.request.output_base64sha256
  timeout          = 30

  environment {
    variables = {
      TABLE_NAME             = aws_dynamodb_table.requests.name
      API_KEY_SECRET_ARN     = var.integration_api_secret_arn
      EXECUTION_FUNCTION_ARN = aws_lambda_function.execution.arn
      SCHEDULER_ROLE_ARN     = aws_iam_role.scheduler.arn
      SCHEDULE_GROUP_NAME    = aws_scheduler_schedule_group.installations.name
    }
  }
  tags = local.tags
}

resource "aws_iam_role_policy" "request_invoke" {
  name = "invoke-execution-lambda"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.execution.arn
    }]
  })
}

resource "aws_lambda_function" "callback" {
  function_name    = "${var.project_name}-status"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "handler.handler"
  filename         = data.archive_file.callback.output_path
  source_code_hash = data.archive_file.callback.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      TABLE_NAME            = aws_dynamodb_table.requests.name
      COMMAND_LOG_GROUP     = aws_cloudwatch_log_group.commands.name
      SERVICENOW_SECRET_ARN = var.servicenow_secret_arn
    }
  }
  tags = local.tags
}

resource "aws_cloudwatch_event_rule" "status" {
  name                = "${var.project_name}-status"
  schedule_expression = "rate(1 minute)"
  tags                = local.tags
}

resource "aws_cloudwatch_event_target" "status" {
  rule = aws_cloudwatch_event_rule.status.name
  arn  = aws_lambda_function.callback.arn
}

resource "aws_lambda_permission" "status" {
  statement_id  = "AllowEventBridgeStatusCheck"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.callback.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.status.arn
}

resource "aws_apigatewayv2_api" "installations" {
  name          = var.project_name
  protocol_type = "HTTP"
  cors_configuration {
    allow_headers = ["content-type", "x-api-key"]
    allow_methods = ["POST"]
    allow_origins = ["*"]
  }
  tags = local.tags
}

resource "aws_apigatewayv2_integration" "request" {
  api_id                 = aws_apigatewayv2_api.installations.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.request.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "request" {
  api_id    = aws_apigatewayv2_api.installations.id
  route_key = "POST /installations"
  target    = "integrations/${aws_apigatewayv2_integration.request.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.installations.id
  name        = "$default"
  auto_deploy = true
  tags        = local.tags
}

resource "aws_lambda_permission" "api" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.request.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.installations.execution_arn}/*/*"
}

