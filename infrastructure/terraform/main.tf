# Networking Module
module "networking" {
  source = "./modules/networking"

  project_name       = var.project_name
  environment        = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  nat_gateway_count  = var.nat_gateway_count
  tags               = var.common_tags
}

# ECS Module
module "ecs" {
  source = "./modules/ecs"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.networking.vpc_id
  public_subnet_ids  = module.networking.public_subnet_ids
  private_subnet_ids = module.networking.private_subnet_ids

  task_cpu                         = var.ecs_task_cpu
  task_memory                      = var.ecs_task_memory
  desired_count                    = var.ecs_task_desired_count
  min_capacity                     = var.ecs_task_min_capacity
  max_capacity                     = var.ecs_task_max_capacity
  container_port                   = var.container_port
  log_retention_days               = var.log_retention_days
  cpu_target_utilization           = var.cpu_target_utilization
  memory_target_utilization        = var.memory_target_utilization
  health_check_path                = var.health_check_path
  health_check_interval            = var.health_check_interval
  health_check_timeout             = var.health_check_timeout
  health_check_healthy_threshold   = var.health_check_healthy_threshold
  health_check_unhealthy_threshold = var.health_check_unhealthy_threshold

  tags = var.common_tags

  depends_on = [module.networking]
}

# Monitoring Module
module "monitoring" {
  source = "./modules/monitoring"

  project_name            = var.project_name
  environment             = var.environment
  aws_region              = var.aws_region
  cluster_name            = module.ecs.cluster_name
  service_name            = module.ecs.service_name
  alb_arn_suffix          = split("/", module.ecs.alb_arn)[1]
  target_group_arn_suffix = split(":", module.ecs.target_group_arn)[5]
  alarm_email             = var.alarm_email
  cpu_alarm_threshold     = var.cpu_alarm_threshold
  memory_alarm_threshold  = var.memory_alarm_threshold

  tags = var.common_tags

  depends_on = [module.ecs]
}
