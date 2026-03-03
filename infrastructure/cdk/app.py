#!/usr/bin/env python3
"""
AWS CDK Application for Streaver Hello World Challenge.

This application provisions infrastructure for a containerized Flask application
across multiple environments (dev, cert, prod) with proper networking, auto-scaling,
and monitoring.

Usage:
    export ENVIRONMENT=dev  # or cert, prod
    cdk synth
    cdk deploy --all
"""

import os
import yaml
from aws_cdk import App, Environment
from stacks import NetworkStack, EcsStack, MonitoringStack


def load_config(environment: str) -> dict:
    """
    Load configuration from YAML file for specified environment.

    Args:
        environment: Environment name (dev, cert, prod)

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If environment is invalid
    """
    valid_environments = ["dev", "cert", "prod"]
    if environment not in valid_environments:
        raise ValueError(
            f"Invalid environment: {environment}. "
            f"Must be one of: {', '.join(valid_environments)}"
        )

    config_path = os.path.join(
        os.path.dirname(__file__), "config", f"{environment}.yaml"
    )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def main():
    """Main function to create and deploy CDK stacks."""
    app = App()

    # Get environment from context or environment variable
    environment = app.node.try_get_context("environment") or os.getenv("ENVIRONMENT", "dev")

    # Load configuration
    try:
        config = load_config(environment)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error loading configuration: {e}")
        print("Please set ENVIRONMENT variable or pass --context environment=<env>")
        import sys
        sys.exit(1)

    # AWS Environment configuration
    env = Environment(
        account=config["account_id"],
        region=config["region"]
    )

    # Stack naming convention
    stack_prefix = f"Streaver-{environment.capitalize()}"

    # Create Network Stack
    network_stack = NetworkStack(
        app,
        f"{stack_prefix}-Network",
        config=config,
        env=env,
        description=f"Network infrastructure for Streaver Hello World ({environment})",
    )

    # Create ECS Stack (depends on Network Stack)
    ecs_stack = EcsStack(
        app,
        f"{stack_prefix}-ECS",
        vpc=network_stack.vpc,
        config=config,
        env=env,
        description=f"ECS infrastructure for Streaver Hello World ({environment})",
    )
    ecs_stack.add_dependency(network_stack)

    # Create Monitoring Stack (depends on ECS Stack)
    monitoring_stack = MonitoringStack(
        app,
        f"{stack_prefix}-Monitoring",
        ecs_service=ecs_stack.service,
        alb=ecs_stack.alb,
        target_group=ecs_stack.target_group,
        config=config,
        env=env,
        description=f"Monitoring infrastructure for Streaver Hello World ({environment})",
    )
    monitoring_stack.add_dependency(ecs_stack)

    # Add stack outputs
    from aws_cdk import CfnOutput

    CfnOutput(
        ecs_stack,
        "LoadBalancerDNS",
        value=ecs_stack.alb_dns,
        description="DNS name of the Application Load Balancer",
        export_name=f"{stack_prefix}-ALB-DNS",
    )

    CfnOutput(
        ecs_stack,
        "ECRRepositoryURI",
        value=ecs_stack.ecr_repository.repository_uri,
        description="URI of the ECR repository",
        export_name=f"{stack_prefix}-ECR-URI",
    )

    CfnOutput(
        monitoring_stack,
        "DashboardURL",
        value=monitoring_stack.dashboard_url,
        description="CloudWatch Dashboard URL",
    )

    app.synth()


if __name__ == "__main__":
    main()
