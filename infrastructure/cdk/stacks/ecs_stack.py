"""
ECS Stack for Streaver Hello World Application.

Creates ECS cluster, service, task definition, ALB, and auto-scaling policies.
"""

from aws_cdk import (
    Stack,
    Duration,
    Tags,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_elasticloadbalancingv2 as elbv2,
    aws_iam as iam,
    aws_logs as logs,
    aws_applicationautoscaling as appscaling,
    RemovalPolicy,
)
from constructs import Construct
from typing import Dict, Any


class EcsStack(Stack):
    """
    ECS Stack that provisions containerized application infrastructure.

    Creates:
    - ECR repository for Docker images
    - ECS Fargate cluster
    - Task definition with IAM roles
    - ECS service with auto-scaling
    - Application Load Balancer
    - Security groups
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        config: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Initialize the ECS Stack.

        Args:
            scope: CDK scope
            construct_id: Unique identifier for this stack
            vpc: VPC from NetworkStack
            config: Configuration dictionary from YAML
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        env_name = config["environment"]
        ecs_config = config["ecs"]
        alb_config = config["alb"]
        autoscaling_config = config["autoscaling"]

        # ECR Repository for container images
        self.ecr_repository = ecr.Repository(
            self,
            "Repository",
            repository_name=f"streaver-helloworld-{env_name}",
            image_scan_on_push=True,  # Security: scan images for vulnerabilities
            removal_policy=RemovalPolicy.DESTROY if env_name == "dev" else RemovalPolicy.RETAIN,
            empty_on_delete=env_name == "dev",  # Only auto-delete in dev
        )

        # ECS Cluster
        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            cluster_name=ecs_config["cluster_name"],
            vpc=vpc,
            container_insights=True,  # Enable CloudWatch Container Insights
        )

        # Task Execution Role (for ECS agent)
        task_execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ],
            description=f"Task execution role for {env_name} environment",
        )

        # Task Role (for application)
        task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            description=f"Task role for {env_name} environment",
        )

        # Map log retention days to RetentionDays enum
        retention_map = {
            1: logs.RetentionDays.ONE_DAY,
            3: logs.RetentionDays.THREE_DAYS,
            5: logs.RetentionDays.FIVE_DAYS,
            7: logs.RetentionDays.ONE_WEEK,
            14: logs.RetentionDays.TWO_WEEKS,
            30: logs.RetentionDays.ONE_MONTH,
            60: logs.RetentionDays.TWO_MONTHS,
            90: logs.RetentionDays.THREE_MONTHS,
            180: logs.RetentionDays.SIX_MONTHS,
            365: logs.RetentionDays.ONE_YEAR,
        }
        retention_days = ecs_config["container"]["log_retention_days"]
        retention = retention_map.get(retention_days, logs.RetentionDays.ONE_WEEK)

        # CloudWatch Log Group
        log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/{ecs_config['cluster_name']}",
            retention=retention,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Grant task role permissions for CloudWatch Logs
        task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[f"{log_group.log_group_arn}:*"],
            )
        )

        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"{ecs_config['service_name']}-task",
            cpu=ecs_config["task"]["cpu"],
            memory_limit_mib=ecs_config["task"]["memory"],
            task_role=task_role,
            execution_role=task_execution_role,
        )

        # Container Definition
        container = task_definition.add_container(
            "AppContainer",
            container_name=ecs_config["container"]["name"],
            # Use ECR repository (will be populated by CI/CD)
            image=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.11-slim"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ecs",
                log_group=log_group,
            ),
            environment={
                "ENVIRONMENT": env_name,
                "PORT": str(ecs_config["container"]["port"]),
            },
            # Health check
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:5000/health').read()\" || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                retries=3,
                start_period=Duration.seconds(60),
            ),
        )

        # Port mapping
        container.add_port_mappings(
            ecs.PortMapping(
                container_port=ecs_config["container"]["port"],
                protocol=ecs.Protocol.TCP,
            )
        )

        # Security Group for ALB
        alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=vpc,
            description="Security group for ALB",
            allow_all_outbound=True,
        )

        # Allow HTTP traffic from internet
        alb_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(80),
            description="Allow HTTP from internet",
        )

        # Security Group for ECS Tasks
        ecs_security_group = ec2.SecurityGroup(
            self,
            "EcsSecurityGroup",
            vpc=vpc,
            description="Security group for ECS tasks",
            allow_all_outbound=True,
        )

        # Allow traffic from ALB to ECS tasks
        ecs_security_group.add_ingress_rule(
            peer=alb_security_group,
            connection=ec2.Port.tcp(ecs_config["container"]["port"]),
            description="Allow traffic from ALB",
        )

        # Application Load Balancer
        self.alb = elbv2.ApplicationLoadBalancer(
            self,
            "ALB",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name=alb_config["name"],
            security_group=alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # Target Group
        self.target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=vpc,
            port=ecs_config["container"]["port"],
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path=alb_config["health_check"]["path"],
                interval=Duration.seconds(alb_config["health_check"]["interval"]),
                timeout=Duration.seconds(alb_config["health_check"]["timeout"]),
                healthy_threshold_count=alb_config["health_check"]["healthy_threshold"],
                unhealthy_threshold_count=alb_config["health_check"]["unhealthy_threshold"],
            ),
            deregistration_delay=Duration.seconds(30),
        )

        # Listener
        listener = self.alb.add_listener(
            "Listener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self.target_group],
        )

        # ECS Service
        self.service = ecs.FargateService(
            self,
            "Service",
            cluster=self.cluster,
            task_definition=task_definition,
            service_name=ecs_config["service_name"],
            desired_count=ecs_config["task"]["desired_count"],
            security_groups=[ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            assign_public_ip=False,  # Security: tasks in private subnet
            health_check_grace_period=Duration.seconds(60),
            circuit_breaker=ecs.DeploymentCircuitBreaker(rollback=True),  # Auto-rollback on failures
        )

        # Attach service to target group
        self.service.attach_to_application_target_group(self.target_group)

        # Auto Scaling Configuration
        scalable_target = self.service.auto_scale_task_count(
            min_capacity=ecs_config["task"]["min_capacity"],
            max_capacity=ecs_config["task"]["max_capacity"],
        )

        # CPU-based auto-scaling
        scalable_target.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=autoscaling_config["cpu"]["target_utilization"],
            scale_in_cooldown=Duration.seconds(autoscaling_config["cpu"]["scale_in_cooldown"]),
            scale_out_cooldown=Duration.seconds(autoscaling_config["cpu"]["scale_out_cooldown"]),
        )

        # Memory-based auto-scaling
        scalable_target.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=autoscaling_config["memory"]["target_utilization"],
            scale_in_cooldown=Duration.seconds(autoscaling_config["memory"]["scale_in_cooldown"]),
            scale_out_cooldown=Duration.seconds(autoscaling_config["memory"]["scale_out_cooldown"]),
        )

        # Apply tags
        for key, value in config["tags"].items():
            Tags.of(self.cluster).add(key, value)
            Tags.of(self.service).add(key, value)
            Tags.of(self.alb).add(key, value)

        # Store outputs
        self.alb_dns = self.alb.load_balancer_dns_name
        self.service_name = self.service.service_name
