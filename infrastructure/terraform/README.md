# Terraform Infrastructure

Infrastructure as Code using Terraform for the Streaver Hello World application.

## Prerequisites

- Terraform >= 1.6.0
- AWS CLI configured with appropriate credentials
- AWS account with necessary permissions

## Installation

```bash
# Install Terraform (macOS)
brew install terraform

# Install Terraform (Linux)
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# Verify installation
terraform version
```

## Project Structure

```
terraform/
├── main.tf                 # Main configuration using modules
├── variables.tf            # Variable definitions
├── outputs.tf              # Output definitions
├── versions.tf             # Provider and version constraints
├── modules/                # Reusable modules
│   ├── networking/         # VPC, subnets, NAT, IGW
│   ├── ecs/                # ECS cluster, service, ALB
│   └── monitoring/         # CloudWatch alarms and dashboards
└── environments/           # Environment-specific configurations
    ├── dev.tfvars
    ├── cert.tfvars
    └── prod.tfvars
```

## Module Overview

### Networking Module
Creates network infrastructure:
- VPC with configurable CIDR
- Public and private subnets across multiple AZs
- Internet Gateway
- NAT Gateway(s) for private subnet egress
- Route tables and associations

### ECS Module
Creates containerized application infrastructure:
- ECR repository with image scanning
- ECS Fargate cluster
- Task definition with IAM roles
- ECS service with auto-scaling
- Application Load Balancer
- Target group with health checks
- Security groups

### Monitoring Module
Creates observability infrastructure:
- CloudWatch alarms (CPU, Memory, 5XX errors, response time, unhealthy targets)
- SNS topic for notifications
- CloudWatch dashboard

## Configuration

Each environment has its own `.tfvars` file in `environments/`:

- **dev.tfvars**: Development environment (minimal resources)
- **cert.tfvars**: Certification environment (pre-production)
- **prod.tfvars**: Production environment (full resources)

### Key Configuration Parameters

Edit the tfvars files to customize:

```hcl
environment            = "dev"              # Environment name
vpc_cidr               = "10.0.0.0/16"      # VPC CIDR block
availability_zones     = ["us-east-1a", "us-east-1b"]
nat_gateway_count      = 1                  # 1 for dev, 2 for prod HA
ecs_task_cpu           = 512                # CPU units
ecs_task_memory        = 1024               # Memory in MB
ecs_task_min_capacity  = 1                  # Min tasks for auto-scaling
ecs_task_max_capacity  = 5                  # Max tasks for auto-scaling
alarm_email            = "your@email.com"   # Email for alerts
```

## Usage

### Initialize Terraform

```bash
cd infrastructure/terraform
terraform init
```

### Validate Configuration

```bash
terraform validate
```

### Format Code

```bash
terraform fmt -recursive
```

### Plan Deployment

```bash
# Development environment
terraform plan -var-file=environments/dev.tfvars

# Certification environment
terraform plan -var-file=environments/cert.tfvars

# Production environment
terraform plan -var-file=environments/prod.tfvars
```

### Apply Changes

```bash
# Deploy to dev
terraform apply -var-file=environments/dev.tfvars

# Deploy to cert
terraform apply -var-file=environments/cert.tfvars

# Deploy to prod
terraform apply -var-file=environments/prod.tfvars
```

### View Outputs

```bash
terraform output
```

### Destroy Infrastructure

```bash
terraform destroy -var-file=environments/dev.tfvars
```

## State Management

For production use, configure remote state backend in `versions.tf`:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-terraform-state-bucket"
    key            = "streaver-helloworld/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### Setup Remote State Backend

```bash
# Create S3 bucket for state
aws s3api create-bucket \
  --bucket your-terraform-state-bucket \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket your-terraform-state-bucket \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Multi-Environment Strategy

This infrastructure supports multiple environments with separate state:

1. **Separate AWS Accounts** (Recommended):
   - Configure different AWS profiles for each environment
   - Use separate state backends per account

   ```bash
   # Deploy to dev account
   AWS_PROFILE=dev terraform apply -var-file=environments/dev.tfvars

   # Deploy to prod account
   AWS_PROFILE=prod terraform apply -var-file=environments/prod.tfvars
   ```

2. **Workspaces** (Alternative):
   ```bash
   terraform workspace new dev
   terraform workspace new cert
   terraform workspace new prod

   terraform workspace select dev
   terraform apply -var-file=environments/dev.tfvars
   ```

## Module Inputs and Outputs

### Networking Module

**Inputs:**
- `vpc_cidr`: VPC CIDR block
- `availability_zones`: List of AZs
- `nat_gateway_count`: Number of NAT Gateways

**Outputs:**
- `vpc_id`: VPC identifier
- `public_subnet_ids`: Public subnet IDs
- `private_subnet_ids`: Private subnet IDs

### ECS Module

**Inputs:**
- `vpc_id`: VPC identifier
- `task_cpu`, `task_memory`: Task resources
- `min_capacity`, `max_capacity`: Auto-scaling limits

**Outputs:**
- `cluster_name`: ECS cluster name
- `service_name`: ECS service name
- `ecr_repository_url`: Docker registry URL
- `alb_dns_name`: Load balancer DNS

### Monitoring Module

**Inputs:**
- `cluster_name`, `service_name`: Resources to monitor
- `alarm_email`: Notification email
- `cpu_alarm_threshold`, `memory_alarm_threshold`: Alert thresholds

**Outputs:**
- `sns_topic_arn`: SNS topic ARN
- `dashboard_name`: CloudWatch dashboard name
- `alarm_names`: List of alarm names

## Security Best Practices

- **IAM Roles**: Least privilege with specific resource policies
- **Security Groups**: Minimal ingress/egress rules
- **Private Subnets**: ECS tasks run without public IPs
- **ECR Scanning**: Automatic vulnerability scanning
- **Secrets**: Use AWS Secrets Manager for sensitive data
- **Encryption**: S3 state encryption, EBS encryption

## Cost Optimization

- **NAT Gateway**: 1 for dev ($32/month), 2 for prod HA
- **ECS Fargate**: Pay per vCPU and memory used
- **ALB**: Pay per hour + LCU consumed
- **CloudWatch**: Log retention varies by environment (7/14/30 days)

### Estimated Monthly Costs (us-east-1)

- **Dev**: ~$100/month (1 NAT, 1 task, 7-day logs)
- **Cert**: ~$150/month (1 NAT, 2 tasks, 14-day logs)
- **Prod**: ~$250/month (2 NATs, 2-10 tasks, 30-day logs)

## Troubleshooting

### Terraform Init Fails

```bash
# Clear cache
rm -rf .terraform .terraform.lock.hcl

# Re-initialize
terraform init
```

### Plan Shows Unexpected Changes

```bash
# Refresh state
terraform refresh -var-file=environments/dev.tfvars

# Check for drift
terraform plan -var-file=environments/dev.tfvars
```

### Apply Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify permissions
aws iam get-user

# Check resource limits
aws service-quotas list-service-quotas --service-code ecs
```

### State Lock Issues

```bash
# Force unlock (use with caution)
terraform force-unlock <lock-id>
```

## Additional Resources

- [Terraform AWS Provider Documentation](https://registry.terraform.io/providers/hashicorp/aws/latest/docs)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [Terraform Module Development](https://developer.hashicorp.com/terraform/language/modules/develop)
