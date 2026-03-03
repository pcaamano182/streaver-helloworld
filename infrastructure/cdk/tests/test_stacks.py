"""
Unit tests for CDK stacks.

Tests verify that stacks are created with correct resources and configurations.
"""

import pytest
import yaml
import os
from aws_cdk import App, assertions
from stacks import NetworkStack, EcsStack, MonitoringStack


@pytest.fixture
def dev_config():
    """Load development environment configuration."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "dev.yaml"
    )
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def app():
    """Create a CDK App for testing."""
    return App()


class TestNetworkStack:
    """Tests for Network Stack."""

    def test_vpc_created(self, app, dev_config):
        """Test that VPC is created with correct CIDR."""
        stack = NetworkStack(app, "TestNetwork", config=dev_config)
        template = assertions.Template.from_stack(stack)

        # Verify VPC is created
        template.resource_count_is("AWS::EC2::VPC", 1)

        # Verify VPC has correct CIDR
        template.has_resource_properties(
            "AWS::EC2::VPC",
            {
                "CidrBlock": dev_config["vpc"]["cidr"],
                "EnableDnsHostnames": True,
                "EnableDnsSupport": True,
            }
        )

    def test_subnets_created(self, app, dev_config):
        """Test that subnets are created."""
        stack = NetworkStack(app, "TestNetwork", config=dev_config)
        template = assertions.Template.from_stack(stack)

        # Should have public and private subnets (2 AZs * 2 types = 4 subnets)
        expected_subnets = dev_config["vpc"]["max_azs"] * 2
        template.resource_count_is("AWS::EC2::Subnet", expected_subnets)

    def test_nat_gateway_created(self, app, dev_config):
        """Test that NAT Gateway is created."""
        stack = NetworkStack(app, "TestNetwork", config=dev_config)
        template = assertions.Template.from_stack(stack)

        # Verify NAT Gateway count
        template.resource_count_is(
            "AWS::EC2::NatGateway",
            dev_config["vpc"]["nat_gateways"]
        )

    def test_internet_gateway_created(self, app, dev_config):
        """Test that Internet Gateway is created."""
        stack = NetworkStack(app, "TestNetwork", config=dev_config)
        template = assertions.Template.from_stack(stack)

        # Verify Internet Gateway
        template.resource_count_is("AWS::EC2::InternetGateway", 1)


class TestEcsStack:
    """Tests for ECS Stack."""

    def test_ecr_repository_created(self, app, dev_config):
        """Test that ECR repository is created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify ECR repository
        template.has_resource_properties(
            "AWS::ECR::Repository",
            {
                "ImageScanningConfiguration": {"ScanOnPush": True},
            }
        )

    def test_ecs_cluster_created(self, app, dev_config):
        """Test that ECS cluster is created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify ECS cluster
        template.resource_count_is("AWS::ECS::Cluster", 1)

    def test_ecs_service_created(self, app, dev_config):
        """Test that ECS service is created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify ECS service
        template.has_resource_properties(
            "AWS::ECS::Service",
            {
                "LaunchType": "FARGATE",
                "DesiredCount": dev_config["ecs"]["task"]["desired_count"],
            }
        )

    def test_task_definition_created(self, app, dev_config):
        """Test that task definition is created with correct CPU and memory."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify task definition
        template.has_resource_properties(
            "AWS::ECS::TaskDefinition",
            {
                "Cpu": str(dev_config["ecs"]["task"]["cpu"]),
                "Memory": str(dev_config["ecs"]["task"]["memory"]),
                "NetworkMode": "awsvpc",
                "RequiresCompatibilities": ["FARGATE"],
            }
        )

    def test_alb_created(self, app, dev_config):
        """Test that Application Load Balancer is created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify ALB
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::LoadBalancer",
            {
                "Scheme": "internet-facing",
                "Type": "application",
            }
        )

    def test_target_group_health_check(self, app, dev_config):
        """Test that target group has correct health check configuration."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify target group health check
        template.has_resource_properties(
            "AWS::ElasticLoadBalancingV2::TargetGroup",
            {
                "HealthCheckPath": dev_config["alb"]["health_check"]["path"],
                "HealthCheckIntervalSeconds": dev_config["alb"]["health_check"]["interval"],
                "HealthCheckTimeoutSeconds": dev_config["alb"]["health_check"]["timeout"],
                "HealthyThresholdCount": dev_config["alb"]["health_check"]["healthy_threshold"],
                "UnhealthyThresholdCount": dev_config["alb"]["health_check"]["unhealthy_threshold"],
            }
        )

    def test_security_groups_created(self, app, dev_config):
        """Test that security groups are created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Should have security groups for ALB and ECS tasks
        template.resource_count_is("AWS::EC2::SecurityGroup", 2)

    def test_autoscaling_configured(self, app, dev_config):
        """Test that auto-scaling is configured."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Verify scalable target
        template.has_resource_properties(
            "AWS::ApplicationAutoScaling::ScalableTarget",
            {
                "MinCapacity": dev_config["ecs"]["task"]["min_capacity"],
                "MaxCapacity": dev_config["ecs"]["task"]["max_capacity"],
            }
        )

        # Should have scaling policies (CPU and Memory)
        template.resource_count_is(
            "AWS::ApplicationAutoScaling::ScalingPolicy", 2
        )

    def test_iam_roles_created(self, app, dev_config):
        """Test that IAM roles are created with least privilege."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        template = assertions.Template.from_stack(ecs_stack)

        # Should have task role and task execution role
        template.resource_count_is("AWS::IAM::Role", 2)


class TestMonitoringStack:
    """Tests for Monitoring Stack."""

    def test_sns_topic_created(self, app, dev_config):
        """Test that SNS topic is created for alarms."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        monitoring_stack = MonitoringStack(
            app,
            "TestMonitoring",
            ecs_service=ecs_stack.service,
            alb=ecs_stack.alb,
            target_group=ecs_stack.target_group,
            config=dev_config,
        )
        template = assertions.Template.from_stack(monitoring_stack)

        # Verify SNS topic
        template.resource_count_is("AWS::SNS::Topic", 1)

    def test_cloudwatch_alarms_created(self, app, dev_config):
        """Test that CloudWatch alarms are created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        monitoring_stack = MonitoringStack(
            app,
            "TestMonitoring",
            ecs_service=ecs_stack.service,
            alb=ecs_stack.alb,
            target_group=ecs_stack.target_group,
            config=dev_config,
        )
        template = assertions.Template.from_stack(monitoring_stack)

        # Should have multiple alarms (CPU, Memory, Unhealthy Tasks, 5XX, Response Time)
        template.resource_count_is("AWS::CloudWatch::Alarm", 5)

    def test_dashboard_created(self, app, dev_config):
        """Test that CloudWatch dashboard is created."""
        network_stack = NetworkStack(app, "TestNetwork", config=dev_config)
        ecs_stack = EcsStack(
            app, "TestECS", vpc=network_stack.vpc, config=dev_config
        )
        monitoring_stack = MonitoringStack(
            app,
            "TestMonitoring",
            ecs_service=ecs_stack.service,
            alb=ecs_stack.alb,
            target_group=ecs_stack.target_group,
            config=dev_config,
        )
        template = assertions.Template.from_stack(monitoring_stack)

        # Verify dashboard
        template.resource_count_is("AWS::CloudWatch::Dashboard", 1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
