# AWS CDK Infrastructure

Infrastructure as Code using AWS CDK (Python) for the Streaver Hello World application.

## Prerequisites

- Python 3.11+
- AWS CDK CLI 2.136.0+
- AWS CLI configured with appropriate credentials
- Node.js 18+ (for CDK CLI)

## Installation

```bash
# Install CDK CLI globally (if not already installed)
npm install -g aws-cdk

# Install Python dependencies
pip install -r requirements.txt

# Verify CDK installation
cdk --version
```

## Project Structure

```
cdk/
├── app.py                  # Main CDK application entry point
├── cdk.json                # CDK configuration
├── requirements.txt        # Python dependencies
├── config/                 # Environment configurations
│   ├── dev.yaml
│   ├── cert.yaml
│   └── prod.yaml
├── stacks/                 # CDK stack definitions
│   ├── network_stack.py    # VPC, subnets, NAT, IGW
│   ├── ecs_stack.py        # ECS cluster, service, ALB
│   └── monitoring_stack.py # CloudWatch alarms and dashboards
└── tests/                  # Unit tests
    └── test_stacks.py
```

## Configuration

Each environment has its own configuration file in `config/`:

- `dev.yaml` - Development environment (cost-optimized)
- `cert.yaml` - Certification environment (pre-production)
- `prod.yaml` - Production environment

### Key Configuration Parameters

- **VPC CIDR**: Network range for the VPC
- **NAT Gateways**: Number of NAT Gateways (1 for dev, 2 for prod HA)
- **ECS Task Size**: CPU and memory allocation
- **Auto-scaling**: Min/max task counts and thresholds
- **Monitoring**: Alarm thresholds and notification emails

**Important**: Update the following in config files before deployment:
- `account_id`: Replace with your AWS account ID
- `monitoring.alarm_email`: Replace with your email address

## Deployment

### Synthesize CloudFormation Templates

```bash
# Set environment
export ENVIRONMENT=dev  # or cert, prod

# Generate CloudFormation templates
cdk synth
```

### Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### Deploy Stacks

```bash
# Deploy all stacks
cdk deploy --all

# Deploy specific stack
cdk deploy Streaver-Dev-Network

# Deploy with auto-approval (CI/CD)
cdk deploy --all --require-approval never
```

### View Differences

```bash
cdk diff
```

### Destroy Infrastructure

```bash
cdk destroy --all
```

## Stack Dependencies

```
NetworkStack (VPC, Subnets, NAT)
    ↓
EcsStack (Cluster, Service, ALB)
    ↓
MonitoringStack (Alarms, Dashboard)
```

## Outputs

After deployment, CDK will output:

- **LoadBalancerDNS**: URL to access the application
- **ECRRepositoryURI**: Docker image repository URI
- **DashboardURL**: CloudWatch dashboard URL

## Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run unit tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=stacks --cov-report=html
```

## Security Features

- **Least Privilege IAM**: Minimal permissions for task and execution roles
- **Private Subnets**: ECS tasks run in private subnets
- **Security Groups**: Restricted ingress/egress rules
- **ECR Scanning**: Automatic image vulnerability scanning
- **No Public IPs**: ECS tasks have no direct internet access

## Cost Optimization

- **NAT Gateway**: Single NAT Gateway in dev (can be increased for HA)
- **Fargate Spot**: Can be enabled for non-production workloads
- **Auto-scaling**: Scales down during low traffic periods
- **Log Retention**: Shorter retention in dev (7 days) vs prod (30 days)

## Multi-Environment Strategy

This infrastructure supports multiple environments with separate AWS accounts:

- **Dev**: 111111111111 (replace with actual)
- **Cert**: 222222222222 (replace with actual)
- **Prod**: 333333333333 (replace with actual)

Use AWS Organizations and cross-account roles for GitHub Actions deployment.

## Troubleshooting

### CDK Synth Fails

```bash
# Check Python path
which python

# Verify dependencies
pip list | grep aws-cdk

# Check configuration
export ENVIRONMENT=dev
python app.py
```

### Deployment Fails

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify CDK bootstrap
cdk bootstrap --show-template

# Check CloudFormation events
aws cloudformation describe-stack-events --stack-name Streaver-Dev-Network
```

## Additional Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Well-Architected Framework](https://aws.amazon.com/architecture/well-architected/)
