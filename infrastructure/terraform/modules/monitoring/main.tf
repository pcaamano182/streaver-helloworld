# SNS Topic for Alarms
resource "aws_sns_topic" "alarms" {
  name = "${var.project_name}-alarms-${var.environment}"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-alarms-topic-${var.environment}"
    }
  )
}

# SNS Topic Subscription
resource "aws_sns_topic_subscription" "alarms_email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# CloudWatch Alarm - ECS CPU Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_cpu" {
  alarm_name          = "${var.project_name}-${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = var.cpu_alarm_threshold
  alarm_description   = "Triggers when CPU utilization exceeds ${var.cpu_alarm_threshold}%"
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-cpu-alarm-${var.environment}"
    }
  )
}

# CloudWatch Alarm - ECS Memory Utilization
resource "aws_cloudwatch_metric_alarm" "ecs_memory" {
  alarm_name          = "${var.project_name}-${var.environment}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = 300
  statistic           = "Average"
  threshold           = var.memory_alarm_threshold
  alarm_description   = "Triggers when memory utilization exceeds ${var.memory_alarm_threshold}%"
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.cluster_name
    ServiceName = var.service_name
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-memory-alarm-${var.environment}"
    }
  )
}

# CloudWatch Alarm - ALB 5XX Errors
resource "aws_cloudwatch_metric_alarm" "alb_5xx" {
  alarm_name          = "${var.project_name}-${var.environment}-alb-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Triggers when target returns excessive 5XX errors"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-5xx-alarm-${var.environment}"
    }
  )
}

# CloudWatch Alarm - ALB Target Response Time
resource "aws_cloudwatch_metric_alarm" "target_response_time" {
  alarm_name          = "${var.project_name}-${var.environment}-high-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "Triggers when average response time exceeds 1 second"
  datapoints_to_alarm = 2
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-response-time-alarm-${var.environment}"
    }
  )
}

# CloudWatch Alarm - Unhealthy Target Count
resource "aws_cloudwatch_metric_alarm" "unhealthy_targets" {
  alarm_name          = "${var.project_name}-${var.environment}-unhealthy-targets"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "Triggers when there are unhealthy targets"
  datapoints_to_alarm = 2
  treat_missing_data  = "breaching"

  dimensions = {
    TargetGroup  = var.target_group_arn_suffix
    LoadBalancer = var.alb_arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-unhealthy-targets-alarm-${var.environment}"
    }
  )
}
