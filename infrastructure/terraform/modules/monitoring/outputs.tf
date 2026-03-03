output "sns_topic_arn" {
  description = "ARN of the SNS topic for alarms"
  value       = aws_sns_topic.alarms.arn
}

output "dashboard_name" {
  description = "Name of the CloudWatch dashboard"
  value       = aws_cloudwatch_dashboard.main.dashboard_name
}

output "alarm_names" {
  description = "Names of CloudWatch alarms"
  value = [
    aws_cloudwatch_metric_alarm.ecs_cpu.alarm_name,
    aws_cloudwatch_metric_alarm.ecs_memory.alarm_name,
    aws_cloudwatch_metric_alarm.alb_5xx.alarm_name,
    aws_cloudwatch_metric_alarm.target_response_time.alarm_name,
    aws_cloudwatch_metric_alarm.unhealthy_targets.alarm_name,
  ]
}
