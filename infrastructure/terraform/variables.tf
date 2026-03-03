# Core variables
variable "environment" {
  description = "Environment name (dev, cert, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "cert", "prod"], var.environment)
    error_message = "Environment must be dev, cert, or prod."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "streaver-helloworld"
}

# Networking variables
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
}

variable "nat_gateway_count" {
  description = "Number of NAT Gateways (1 for dev, 2 for prod HA)"
  type        = number
  default     = 1
  validation {
    condition     = var.nat_gateway_count >= 1 && var.nat_gateway_count <= 3
    error_message = "NAT Gateway count must be between 1 and 3."
  }
}

# ECS variables
variable "ecs_task_cpu" {
  description = "CPU units for ECS task (256, 512, 1024, 2048, 4096)"
  type        = number
}

variable "ecs_task_memory" {
  description = "Memory for ECS task in MB"
  type        = number
}

variable "ecs_task_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_task_min_capacity" {
  description = "Minimum number of ECS tasks for auto-scaling"
  type        = number
}

variable "ecs_task_max_capacity" {
  description = "Maximum number of ECS tasks for auto-scaling"
  type        = number
}

variable "container_port" {
  description = "Port exposed by the container"
  type        = number
  default     = 5000
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

# Auto-scaling variables
variable "cpu_target_utilization" {
  description = "Target CPU utilization percentage for auto-scaling"
  type        = number
  default     = 70
}

variable "memory_target_utilization" {
  description = "Target memory utilization percentage for auto-scaling"
  type        = number
  default     = 80
}

# Monitoring variables
variable "alarm_email" {
  description = "Email address for CloudWatch alarms"
  type        = string
}

variable "cpu_alarm_threshold" {
  description = "CPU utilization threshold for alarm"
  type        = number
  default     = 90
}

variable "memory_alarm_threshold" {
  description = "Memory utilization threshold for alarm"
  type        = number
  default     = 90
}

variable "error_rate_threshold" {
  description = "Error rate percentage threshold for alarm"
  type        = number
  default     = 5
}

# Health check variables
variable "health_check_path" {
  description = "Health check path for ALB target group"
  type        = string
  default     = "/health"
}

variable "health_check_interval" {
  description = "Health check interval in seconds"
  type        = number
  default     = 30
}

variable "health_check_timeout" {
  description = "Health check timeout in seconds"
  type        = number
  default     = 5
}

variable "health_check_healthy_threshold" {
  description = "Number of consecutive successful health checks"
  type        = number
  default     = 2
}

variable "health_check_unhealthy_threshold" {
  description = "Number of consecutive failed health checks"
  type        = number
  default     = 3
}

# Tags
variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
