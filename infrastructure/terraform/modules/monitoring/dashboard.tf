# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}"

  dashboard_body = jsonencode({
    widgets = [
      # ECS Service Metrics
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", { stat = "Average", label = "CPU Utilization" }],
            [".", "MemoryUtilization", { stat = "Average", label = "Memory Utilization" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Service - CPU and Memory"
          period  = 300
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }
        }
      },
      # ECS Task Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "RunningTaskCount", { stat = "Average", label = "Running Tasks" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ECS Service - Running Tasks"
          period  = 60
        }
      },
      # ALB Request Count
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", { stat = "Sum", label = "Total Requests" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB - Request Count"
          period  = 300
        }
      },
      # ALB HTTP Response Codes
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_Target_2XX_Count", { stat = "Sum", label = "2XX" }],
            [".", "HTTPCode_Target_4XX_Count", { stat = "Sum", label = "4XX" }],
            [".", "HTTPCode_Target_5XX_Count", { stat = "Sum", label = "5XX" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB - HTTP Response Codes"
          period  = 300
        }
      },
      # ALB Response Time
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average", label = "Average" }],
            ["...", { stat = "p99", label = "p99" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB - Target Response Time"
          period  = 300
        }
      },
      # Healthy/Unhealthy Targets
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ApplicationELB", "HealthyHostCount", { stat = "Average", label = "Healthy" }],
            [".", "UnHealthyHostCount", { stat = "Average", label = "Unhealthy" }]
          ]
          view    = "timeSeries"
          stacked = false
          region  = var.aws_region
          title   = "ALB - Target Health"
          period  = 60
        }
      }
    ]
  })
}
