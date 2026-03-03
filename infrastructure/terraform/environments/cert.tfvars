# Certification Environment Configuration

environment = "cert"
aws_region  = "us-east-1"

# Networking
vpc_cidr           = "10.1.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]
nat_gateway_count  = 1 # Can be increased to 2 for higher availability

# ECS Configuration
ecs_task_cpu           = 1024 # 1 vCPU
ecs_task_memory        = 2048 # 2 GB
ecs_task_desired_count = 2
ecs_task_min_capacity  = 2
ecs_task_max_capacity  = 8
container_port         = 5000
log_retention_days     = 14

# Auto-scaling
cpu_target_utilization    = 70
memory_target_utilization = 80

# Monitoring
alarm_email            = "devops@example.com" # Replace with your email
cpu_alarm_threshold    = 90
memory_alarm_threshold = 90
error_rate_threshold   = 5

# Health Check
health_check_path                = "/health"
health_check_interval            = 30
health_check_timeout             = 5
health_check_healthy_threshold   = 2
health_check_unhealthy_threshold = 3

# Tags
common_tags = {
  Project     = "Streaver-Challenge"
  Environment = "cert"
  ManagedBy   = "Terraform"
  CostCenter  = "Engineering"
}
