# Streaver Hello World - DevOps Challenge

## Project Description

This project is a complete solution for the Senior DevOps/SRE technical challenge at Streaver. It implements a containerized Flask web application with Infrastructure as Code (IaC) using both AWS CDK and Terraform, following industry best practices for security, scalability, and observability.

**Challenge Requirements**: This solution addresses all requirements specified in [CHALLENGE.md](CHALLENGE.md), including containerized application deployment, infrastructure automation, resilience, observability, security, and CI/CD pipelines.

### Key Features

- **Flask Application** with health, error, and metrics endpoints
- **Dual Infrastructure as Code**: AWS CDK (Python) and Terraform
- **Multi-environment**: separate configurations for dev, cert, and prod
- **Comprehensive testing**: unit tests, load tests, security scanning
- **CI/CD with GitHub Actions**: automated integration and deployment pipelines
- **Observability**: structured logging, CloudWatch metrics, alarms, and dashboards
- **Security**: scanning with Bandit, Safety, Checkov, and Trivy
- **High availability**: Auto-scaling, health checks, circuit breakers

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          Internet                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
              ┌────────────────┐
              │ Application    │
              │ Load Balancer  │
              └───────┬────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  ECS Fargate  │           │  ECS Fargate  │
│   Task 1      │           │   Task 2      │
│  (Container)  │           │  (Container)  │
└───────────────┘           └───────────────┘
        │                           │
        └─────────────┬─────────────┘
                      │
                      ▼
              ┌────────────────┐
              │   CloudWatch   │
              │ Logs + Metrics │
              └────────────────┘
```

### Technology Stack

- **Application**: Python 3.11, Flask, Gunicorn
- **Containerization**: Multi-stage Docker
- **IaC**: AWS CDK (Python), Terraform
- **AWS Services**: ECS Fargate, ECR, ALB, VPC, CloudWatch, SNS
- **Testing**: pytest, k6, Bandit, Safety, Checkov, Trivy
- **CI/CD**: GitHub Actions with OIDC

## Quick Start

### Prerequisites

```bash
# Required software
- Python 3.11+
- Docker
- Node.js 18+ (for CDK)
- Terraform 1.5+
- AWS CLI configured
- Git
```

### 1. Clone the Repository

```bash
git clone https://github.com/pcaamano182/streaver-helloworld.git
cd streaver-helloworld
```

### 2. Run Locally with Docker

```bash
# Build the image
docker build -t streaver-helloworld:latest .

# Run the container
docker run -d -p 5000:5000 --name streaver-app streaver-helloworld:latest

# Test endpoints
curl http://localhost:5000/
curl http://localhost:5000/health
curl http://localhost:5000/metrics
curl http://localhost:5000/error  # Returns 500 intentionally

# View logs
docker logs -f streaver-app

# Stop and cleanup
docker stop streaver-app
docker rm streaver-app
```

### 3. Run Local Tests

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Unit tests (32 tests)
pytest app/tests/ -v

# Security scan with Bandit
bandit -r app/ -c tests/security/.bandit

# Dependency scan with Safety
safety check -r requirements.txt

# Load tests with k6 (requires Docker running)
docker run --rm -i grafana/k6 run --vus 10 --duration 30s - < tests/load/k6-smoke-test.js
```

## 🔧 Deployment with AWS CDK

### Initial Setup

```bash
cd infrastructure/cdk

# Install CDK dependencies
pip install -r requirements.txt
npm install -g aws-cdk

# Bootstrap CDK (first time per environment/region)
export AWS_PROFILE=dev
cdk bootstrap aws://ACCOUNT-ID/us-east-1

# Validate stack synthesis
cdk synth -c environment=dev
```

### Deploy to Development

```bash
# Configure AWS credentials for dev
export AWS_PROFILE=dev

# Deploy all stacks
cdk deploy --all -c environment=dev --require-approval never

# Deploy specific stack
cdk deploy StreamerHelloWorldNetwork-dev -c environment=dev
cdk deploy StreamerHelloWorldEcs-dev -c environment=dev
cdk deploy StreamerHelloWorldMonitoring-dev -c environment=dev

# View outputs (ALB URL, etc.)
cdk outputs --all -c environment=dev
```

### Deploy to Certification

```bash
export AWS_PROFILE=cert
cdk deploy --all -c environment=cert
```

### Deploy to Production

```bash
export AWS_PROFILE=prod
cdk deploy --all -c environment=prod
```

### Destroy (Cleanup)

```bash
# WARNING: This deletes all infrastructure
cdk destroy --all -c environment=dev

# Delete in reverse order (recommended)
cdk destroy StreamerHelloWorldMonitoring-dev -c environment=dev
cdk destroy StreamerHelloWorldEcs-dev -c environment=dev
cdk destroy StreamerHelloWorldNetwork-dev -c environment=dev
```

## 🔧 Deployment with Terraform

### Initial Setup

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Format files
terraform fmt -recursive
```

### Deploy to Development

```bash
# Plan (review changes)
terraform plan -var-file=environments/dev.tfvars

# Apply (execute changes)
terraform apply -var-file=environments/dev.tfvars

# View outputs (ALB URL, etc.)
terraform output
```

### Deploy to Certification

```bash
terraform apply -var-file=environments/cert.tfvars
```

### Deploy to Production

```bash
terraform apply -var-file=environments/prod.tfvars
```

### Destroy (Cleanup)

```bash
# WARNING: This deletes all infrastructure
terraform destroy -var-file=environments/dev.tfvars
```

## Monitoring and Observability

### CloudWatch Alarms

The monitoring stack automatically creates the following alarms:

- **High CPU**: >80% for 5 minutes → SNS notification
- **High Memory**: >80% for 5 minutes → SNS notification
- **5XX Errors**: >10 errors in 5 minutes → SNS notification
- **Response Time**: p99 >1s for 5 minutes → SNS notification
- **Unhealthy Targets**: <2 healthy targets → SNS notification

### CloudWatch Dashboard

Access the dashboard from the AWS CloudWatch console to view:

- Request count and response times
- CPU and memory utilization
- Error rates (4xx, 5xx)
- Healthy/unhealthy target count
- Auto-scaling metrics

### Structured Logs

All logs are sent to CloudWatch Logs in JSON format:

```json
{
  "timestamp": "2026-03-03T12:34:56.789Z",
  "level": "INFO",
  "message": "Request processed",
  "service": "streaver-helloworld",
  "method": "GET",
  "path": "/",
  "status": 200,
  "duration_ms": 15.23
}
```

### Available Metrics

- `request_count`: Total requests
- `error_count`: Total errors
- `start_time`: Application start timestamp

## Security

### Static Analysis

```bash
# Python security (Bandit)
bandit -r app/ -c tests/security/.bandit -f json -o reports/bandit.json

# Dependency vulnerabilities (Safety)
safety check -r requirements.txt --json > reports/safety.json

# IaC security (Checkov)
checkov -d infrastructure/cdk --framework cloudformation --output json
checkov -d infrastructure/terraform --framework terraform --output json

# Container vulnerabilities (Trivy)
trivy image streaver-helloworld:latest --format json
```

### Implemented Best Practices

- Multi-stage Docker builds with non-root user
- Private subnets for ECS tasks (no public IPs)
- Security groups with least-privilege
- IAM roles with minimum necessary policies
- Secrets in AWS Secrets Manager (not hardcoded)
- Automatic vulnerability scanning in CI/CD
- HTTPS/TLS on ALB (ACM certificates)
- VPC Flow Logs enabled

## CI/CD Pipelines

### Continuous Integration (ci.yml)

Runs on every push and PR:

1. **Lint**: Flake8, Black, isort
2. **Test**: 32 unit tests with pytest
3. **Security**: Bandit + Safety
4. **Docker**: Build and scan with Trivy
5. **CDK**: Synth and tests (16 tests)
6. **Terraform**: Validate, fmt, plan
7. **IaC Security**: Checkov scan
8. **Summary**: Consolidated report

### Continuous Deployment

- **cd-dev.yml**: Auto-deploy to dev on merge to main
- **cd-cert.yml**: Manual deploy to cert with approval
- **cd-prod.yml**: Manual deploy to prod with multi-approval

**NOTE**: CD workflows are disabled by default (`if: false`) as there is no AWS environment available for this challenge. See [.github/workflows/README.md](.github/workflows/README.md) for configuration instructions.

## Project Structure

```
streaver-helloworld/
├── app/
│   ├── main.py                    # Flask application
│   └── tests/
│       └── test_unit.py           # 32 unit tests
├── infrastructure/
│   ├── cdk/
│   │   ├── app.py                 # CDK app entry point
│   │   ├── stacks/
│   │   │   ├── network_stack.py   # VPC, subnets, NAT
│   │   │   ├── ecs_stack.py       # ECS, ALB, auto-scaling
│   │   │   └── monitoring_stack.py # CloudWatch, SNS
│   │   ├── config/                # dev/cert/prod configs
│   │   └── tests/
│   │       └── test_stacks.py     # 16 CDK tests
│   └── terraform/
│       ├── main.tf                # Root module
│       ├── modules/
│       │   ├── networking/        # VPC module
│       │   ├── ecs/               # ECS module
│       │   └── monitoring/        # CloudWatch module
│       └── environments/          # dev/cert/prod tfvars
├── tests/
│   ├── load/
│   │   ├── k6-load-test.js        # Load test (8 min)
│   │   └── k6-smoke-test.js       # Smoke test (30s)
│   ├── security/
│   │   ├── .bandit                # Bandit config
│   │   ├── checkov.yml            # Checkov config
│   │   └── trivy.yml              # Trivy config
│   └── integration/
│       ├── validate-cdk.sh        # CDK validation
│       └── validate-terraform.sh  # Terraform validation
├── .github/
│   └── workflows/
│       ├── ci.yml                 # CI pipeline
│       ├── cd-dev.yml             # Dev deployment
│       ├── cd-cert.yml            # Cert deployment
│       └── cd-prod.yml            # Prod deployment
├── Dockerfile                     # Multi-stage build
├── requirements.txt               # App dependencies
├── requirements-dev.txt           # Dev dependencies
├── README.md                      # This file
└── ASSUMPTIONS.md                 # Decisions and trade-offs
```

## Testing

### Test Coverage

- **Unit Tests**: 32 tests (100% passing)
  - Endpoints: /, /health, /error, /metrics
  - Error handling and logging
  - Metrics tracking

- **CDK Tests**: 16 tests (100% passing)
  - VPC and networking resources
  - ECS cluster, service, task definition
  - ALB, target groups, security groups
  - Auto-scaling policies
  - CloudWatch alarms and dashboard

- **Load Tests**: k6
  - Smoke test: 10 VUs, 30s
  - Load test: 100 VUs, 8min, 3 stages

- **Security Tests**:
  - Bandit: Python code scanning
  - Safety: Dependency vulnerabilities
  - Checkov: IaC security
  - Trivy: Container vulnerabilities

- **IaC Validation**:
  - CDK synth + tests
  - Terraform validate + fmt + plan

### Run Complete Suite

```bash
# From project root
bash tests/integration/validate-all.sh
```

## Multi-Environment

The project supports 3 environments with separate configurations:

| Environment | AWS Account | Region | Fargate Tasks | NAT Gateways | Auto-scaling |
|----------|-------------|--------|---------------|--------------|--------------|
| **dev** | 111111111111 | us-east-1 | 1 (min) - 2 (max) | 1 | Yes (CPU 70%) |
| **cert** | 222222222222 | us-east-1 | 2 (min) - 4 (max) | 1 | Yes (CPU 70%) |
| **prod** | 333333333333 | us-east-1 | 3 (min) - 10 (max) | 3 (HA) | Yes (CPU 60%) |

### Multi-Account Strategy

A separate AWS account architecture per environment is assumed:

- **Security**: Complete isolation between environments
- **Compliance**: Independent IAM controls and SCPs
- **Billing**: Cost allocation tags per environment
- **Blast radius**: Limit impact of changes

See [ASSUMPTIONS.md](ASSUMPTIONS.md) for more details on architectural decisions.

## Future Improvements

With more time, the following improvements would be implemented:

### Infrastructure

- [ ] **Multi-region**: Active-active or active-passive deployment
- [ ] **WAF**: AWS WAF for attack protection
- [ ] **CDN**: CloudFront for caching and global distribution
- [ ] **RDS/DynamoDB**: Database for persistence
- [ ] **ElastiCache**: Redis/Memcached for caching
- [ ] **Service Mesh**: AWS App Mesh or Istio
- [ ] **Secrets Rotation**: Automatic rotation with Lambda
- [ ] **Backup**: AWS Backup for disaster recovery

### Observability

- [ ] **Distributed Tracing**: AWS X-Ray or Datadog APM
- [ ] **Synthetic Monitoring**: CloudWatch Synthetics canaries
- [ ] **Log Aggregation**: OpenSearch or ELK stack
- [ ] **Custom Metrics**: Business metrics with EMF
- [ ] **Anomaly Detection**: CloudWatch Anomaly Detection
- [ ] **SLIs/SLOs**: Service Level Indicators and Objectives
- [ ] **Runbooks**: Incident response documentation

### CI/CD

- [ ] **GitOps**: ArgoCD or Flux for deployments
- [ ] **Feature Flags**: LaunchDarkly or AWS AppConfig
- [ ] **Canary Deployments**: Gradual traffic shifting
- [ ] **Blue/Green Testing**: Smoke tests pre-cutover
- [ ] **Automatic Rollback**: On failed health checks
- [ ] **Deployment Approvals**: Integrations with Slack/Teams
- [ ] **Performance Testing**: K6 in pipeline with thresholds

### Security

- [ ] **SIEM**: AWS Security Hub + GuardDuty
- [ ] **Compliance**: AWS Config rules
- [ ] **Penetration Testing**: Automated tests
- [ ] **Network Segmentation**: PrivateLink for services
- [ ] **Encryption**: Customer-managed KMS keys
- [ ] **Certificate Management**: Automatic ACM renewal
- [ ] **IAM Access Analyzer**: Permissions analysis

### Application

- [ ] **API Versioning**: /v1/, /v2/ endpoints
- [ ] **Rate Limiting**: Throttling per client/IP
- [ ] **Caching**: HTTP caching headers
- [ ] **Compression**: Gzip/Brotli responses
- [ ] **GraphQL**: Alternative to REST
- [ ] **WebSockets**: For real-time updates
- [ ] **Async Processing**: SQS + Lambda for background jobs

## Development

This project was developed as a solution to the Streaver technical challenge. **Claude Code** (model: Claude Sonnet 4.5) was used as an acceleration tool for code writing, automated test generation, and technical documentation, significantly reducing implementation time.

### Incremental Commits

The commit history shows iterative progress:

1. `feat: add containerized Flask application with health and metrics endpoints`
2. `feat: add AWS CDK infrastructure with networking, ECS, and monitoring stacks`
3. `feat: add Terraform infrastructure with modular design`
4. `feat: add comprehensive testing suite (unit, load, security, IaC validation)`
5. `feat: add comprehensive CI/CD pipelines with GitHub Actions`
6. `docs: add final documentation (README and ASSUMPTIONS)`

## License

This project is part of a technical challenge and does not have a commercial use license.

## Contact

For inquiries about the challenge:
- **Company**: Streaver
- **Repository**: https://github.com/pcaamano182/streaver-helloworld
- **Position**: Senior DevOps Engineer

---

**Note**: This README assumes there is no access to real AWS environments for the challenge. All deployment instructions are theoretical but follow industry best practices.
