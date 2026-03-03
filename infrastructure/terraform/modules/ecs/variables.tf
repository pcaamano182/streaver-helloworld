variable "project_name" {
  description = "Project name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "ID of the VPC"
  type        = string
}

variable "public_subnet_ids" {
  description = "IDs of public subnets for ALB"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "IDs of private subnets for ECS tasks"
  type        = list(string)
}

variable "task_cpu" {
  description = "CPU units for ECS task"
  type        = number
}

variable "task_memory" {
  description = "Memory for ECS task in MB"
  type        = number
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks"
  type        = number
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks"
  type        = number
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
}

variable "cpu_target_utilization" {
  description = "Target CPU utilization for auto-scaling"
  type        = number
}

variable "memory_target_utilization" {
  description = "Target memory utilization for auto-scaling"
  type        = number
}

variable "health_check_path" {
  description = "Health check path"
  type        = string
}

variable "health_check_interval" {
  description = "Health check interval in seconds"
  type        = number
}

variable "health_check_timeout" {
  description = "Health check timeout in seconds"
  type        = number
}

variable "health_check_healthy_threshold" {
  description = "Healthy threshold count"
  type        = number
}

variable "health_check_unhealthy_threshold" {
  description = "Unhealthy threshold count"
  type        = number
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}
