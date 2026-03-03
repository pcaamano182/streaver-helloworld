"""
Monitoring Stack for Streaver Hello World Application.

Creates CloudWatch alarms, dashboards, and SNS topics for alerting.
"""

from aws_cdk import (
    Stack,
    Duration,
    Tags,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_ecs as ecs,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct
from typing import Dict, Any


class MonitoringStack(Stack):
    """
    Monitoring Stack that provisions observability infrastructure.

    Creates:
    - SNS topic for alarm notifications
    - CloudWatch alarms for service health
    - CloudWatch dashboard for metrics visualization
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        ecs_service: ecs.FargateService,
        alb: elbv2.ApplicationLoadBalancer,
        target_group: elbv2.ApplicationTargetGroup,
        config: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Initialize the Monitoring Stack.

        Args:
            scope: CDK scope
            construct_id: Unique identifier for this stack
            ecs_service: ECS service to monitor
            alb: Application Load Balancer to monitor
            target_group: ALB target group to monitor
            config: Configuration dictionary from YAML
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        env_name = config["environment"]
        monitoring_config = config["monitoring"]
        alarms_config = monitoring_config["alarms"]

        # SNS Topic for alarms
        alarm_topic = sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"streaver-alarms-{env_name}",
            display_name=f"Streaver Hello World Alarms ({env_name})",
        )

        # Add email subscription
        alarm_topic.add_subscription(
            sns_subs.EmailSubscription(monitoring_config["alarm_email"])
        )

        # Alarm action
        alarm_action = cw_actions.SnsAction(alarm_topic)

        # === ECS Service Alarms ===

        # Alarm: ECS Service CPU Utilization
        cpu_alarm = cloudwatch.Alarm(
            self,
            "CpuAlarm",
            alarm_name=f"streaver-{env_name}-high-cpu",
            metric=ecs_service.metric_cpu_utilization(
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=alarms_config["cpu_threshold"],
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description=f"Triggers when CPU utilization exceeds {alarms_config['cpu_threshold']}%",
        )
        cpu_alarm.add_alarm_action(alarm_action)

        # Alarm: ECS Service Memory Utilization
        memory_alarm = cloudwatch.Alarm(
            self,
            "MemoryAlarm",
            alarm_name=f"streaver-{env_name}-high-memory",
            metric=ecs_service.metric_memory_utilization(
                period=Duration.minutes(5),
                statistic="Average",
            ),
            threshold=alarms_config["memory_threshold"],
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description=f"Triggers when memory utilization exceeds {alarms_config['memory_threshold']}%",
        )
        memory_alarm.add_alarm_action(alarm_action)

        # Alarm: Unhealthy Tasks
        unhealthy_tasks_alarm = cloudwatch.Alarm(
            self,
            "UnhealthyTasksAlarm",
            alarm_name=f"streaver-{env_name}-unhealthy-tasks",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="HealthyHostCount",
                dimensions_map={
                    "ServiceName": ecs_service.service_name,
                    "ClusterName": ecs_service.cluster.cluster_name,
                },
                period=Duration.minutes(1),
                statistic="Minimum",
            ),
            threshold=1,
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.BREACHING,
            alarm_description="Triggers when no healthy tasks are running",
        )
        unhealthy_tasks_alarm.add_alarm_action(alarm_action)

        # === ALB Alarms ===

        # Alarm: ALB 5XX Errors
        alb_5xx_alarm = cloudwatch.Alarm(
            self,
            "Alb5xxAlarm",
            alarm_name=f"streaver-{env_name}-alb-5xx-errors",
            metric=alb.metrics.http_code_target(
                code=elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
                period=Duration.minutes(5),
                statistic="Sum",
            ),
            threshold=10,  # More than 10 errors in 5 minutes
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description="Triggers when target returns excessive 5XX errors",
        )
        alb_5xx_alarm.add_alarm_action(alarm_action)

        # Alarm: ALB Target Response Time
        response_time_alarm = cloudwatch.Alarm(
            self,
            "ResponseTimeAlarm",
            alarm_name=f"streaver-{env_name}-high-response-time",
            metric=alb.metrics.target_response_time(
                period=Duration.minutes(5),
                statistic="p99",
            ),
            threshold=alarms_config["target_response_time_p99"] / 1000,  # Convert to seconds
            evaluation_periods=2,
            datapoints_to_alarm=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            alarm_description=f"Triggers when p99 response time exceeds {alarms_config['target_response_time_p99']}ms",
        )
        response_time_alarm.add_alarm_action(alarm_action)

        # === CloudWatch Dashboard ===

        dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"streaver-helloworld-{env_name}",
        )

        # Service Overview Widget
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ECS Service - CPU and Memory",
                left=[
                    ecs_service.metric_cpu_utilization(
                        label="CPU Utilization",
                        period=Duration.minutes(5),
                        statistic="Average",
                    ),
                ],
                right=[
                    ecs_service.metric_memory_utilization(
                        label="Memory Utilization",
                        period=Duration.minutes(5),
                        statistic="Average",
                    ),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="ECS Service - Task Count",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ECS",
                        metric_name="RunningTaskCount",
                        dimensions_map={
                            "ServiceName": ecs_service.service_name,
                            "ClusterName": ecs_service.cluster.cluster_name,
                        },
                        label="Running Tasks",
                        period=Duration.minutes(1),
                        statistic="Average",
                    ),
                ],
                width=12,
            ),
        )

        # ALB Metrics Widget
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ALB - Request Count",
                left=[
                    alb.metrics.request_count(
                        label="Request Count",
                        period=Duration.minutes(5),
                        statistic="Sum",
                    ),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="ALB - HTTP Response Codes",
                left=[
                    alb.metrics.http_code_target(
                        code=elbv2.HttpCodeTarget.TARGET_2XX_COUNT,
                        label="2XX",
                        period=Duration.minutes(5),
                        statistic="Sum",
                    ),
                    alb.metrics.http_code_target(
                        code=elbv2.HttpCodeTarget.TARGET_4XX_COUNT,
                        label="4XX",
                        period=Duration.minutes(5),
                        statistic="Sum",
                    ),
                    alb.metrics.http_code_target(
                        code=elbv2.HttpCodeTarget.TARGET_5XX_COUNT,
                        label="5XX",
                        period=Duration.minutes(5),
                        statistic="Sum",
                    ),
                ],
                width=12,
            ),
        )

        # Response Time Widget
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ALB - Target Response Time",
                left=[
                    alb.metrics.target_response_time(
                        label="Average",
                        period=Duration.minutes(5),
                        statistic="Average",
                    ),
                    alb.metrics.target_response_time(
                        label="p99",
                        period=Duration.minutes(5),
                        statistic="p99",
                    ),
                ],
                width=24,
            ),
        )

        # Alarm Status Widget
        dashboard.add_widgets(
            cloudwatch.AlarmStatusWidget(
                title="Alarm Status",
                alarms=[
                    cpu_alarm,
                    memory_alarm,
                    unhealthy_tasks_alarm,
                    alb_5xx_alarm,
                    response_time_alarm,
                ],
                width=24,
            ),
        )

        # Apply tags
        for key, value in config["tags"].items():
            Tags.of(alarm_topic).add(key, value)
            Tags.of(dashboard).add(key, value)

        # Store outputs
        self.alarm_topic_arn = alarm_topic.topic_arn
        self.dashboard_url = f"https://console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard.dashboard_name}"
