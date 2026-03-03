"""
Network Stack for Streaver Hello World Application.

Creates VPC, subnets, NAT Gateway, and Internet Gateway.
Follows AWS best practices for networking architecture.
"""

from aws_cdk import (
    Stack,
    Tags,
    aws_ec2 as ec2,
)
from constructs import Construct
from typing import Dict, Any


class NetworkStack(Stack):
    """
    Network Stack that provisions VPC and related networking components.

    Creates:
    - VPC with public and private subnets across multiple AZs
    - Internet Gateway for public subnet connectivity
    - NAT Gateway(s) for private subnet outbound connectivity
    - Route tables and security groups
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Initialize the Network Stack.

        Args:
            scope: CDK scope
            construct_id: Unique identifier for this stack
            config: Configuration dictionary from YAML
            **kwargs: Additional stack properties
        """
        super().__init__(scope, construct_id, **kwargs)

        env_name = config["environment"]
        vpc_config = config["vpc"]

        # Create VPC with public and private subnets
        self.vpc = ec2.Vpc(
            self,
            "VPC",
            vpc_name=f"streaver-vpc-{env_name}",
            ip_addresses=ec2.IpAddresses.cidr(vpc_config["cidr"]),
            max_azs=vpc_config["max_azs"],
            nat_gateways=vpc_config["nat_gateways"],

            # Subnet configuration
            subnet_configuration=[
                # Public subnets for ALB
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                # Private subnets for ECS tasks
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],

            # Enable DNS
            enable_dns_hostnames=True,
            enable_dns_support=True,
        )

        # VPC Flow Logs would be enabled in production for security auditing
        # Commented out for cost optimization in this challenge
        # self.vpc.add_flow_log(
        #     "FlowLog",
        #     destination=ec2.FlowLogDestination.to_cloud_watch_logs()
        # )

        # Apply tags
        for key, value in config["tags"].items():
            Tags.of(self.vpc).add(key, value)

        # Output VPC ID for reference
        self.vpc_id = self.vpc.vpc_id
