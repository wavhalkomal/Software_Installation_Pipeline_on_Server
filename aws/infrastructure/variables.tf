variable "aws_region" {
  description = "AWS region containing the target and orchestration resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "linux-software-installation"
}

variable "target_instance_id" {
  description = "Existing RHEL EC2 instance ID"
  type        = string
}

variable "integration_api_secret_arn" {
  description = "Secrets Manager ARN containing the ServiceNow-to-AWS API key"
  type        = string
}

variable "servicenow_secret_arn" {
  description = "Optional Secrets Manager ARN containing ServiceNow callback credentials"
  type        = string
  default     = ""
}

variable "attach_instance_profile" {
  description = "Associate the managed-node instance profile with the existing EC2 instance"
  type        = bool
  default     = true
}

