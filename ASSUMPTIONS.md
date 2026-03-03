# Assumptions and Design Decisions

This document details all architectural decisions, assumptions, and trade-offs made during the implementation of the Streaver technical challenge.

**Challenge Context**: This document provides the rationale and decision-making process for implementing the solution to the DevOps/SRE challenge requirements specified in [CHALLENGE.md](CHALLENGE.md). All architectural choices were made to address the core challenge objectives: production-ready infrastructure, resilience, observability, security, and automation.

## General Context

### Challenge Constraints

1. **No access to real AWS environment**: All development and validation was performed locally
2. **Dual IaC requirement**: Implementation in both CDK and Terraform (CDK was required, Terraform added for completeness)
3. **Limited timeline**: Prioritization of core features over advanced optimizations
4. **Demo/Portfolio purpose**: Balance between simplicity and best practices

### Development Tools

**IDE and Environment**:
- **Visual Studio Code** with integrated Claude Code extension
- **Local development**: All code, infrastructure, and tests were developed and validated locally on Windows
- **Local-first testing**: Local validation was prioritized before each commit (Docker builds, unit tests, CDK synth, Terraform validate)

**AI Assistance**:

During implementation, **Claude Code** (model: Claude Sonnet 4.5) was used as an acceleration tool in the following areas:

- **Code writing**: Rapid generation of base code for application and infrastructure
- **Automated tests**: Creation of test suites (unit, security, load tests)
- **Technical documentation**: Generation of READMEs and configuration documentation
- **Debugging**: Resolution of technical issues (deprecation warnings, syntax errors)

---

## Architectural Decisions

### 1. Compute Service: ECS Fargate

**Decision**: Use ECS Fargate instead of EC2, EKS, or Lambda

**Reasons**:
- **Serverless**: No EC2 instance management
- **Simplicity**: Less operational complexity than EKS
- **Cost-effective**: Pay-per-use, ideal for variable workloads
- **Security**: Task-level isolation
- **Scaling**: Native auto-scaling with CloudWatch metrics

**Trade-offs**:
- More expensive than EC2 for constant 24/7 workloads
- Slight cold start vs EC2 (not relevant for this case)
- Less control over the host than with EC2

**Alternatives considered**:
- **EC2 + Auto Scaling Groups**: More economical at scale, but requires OS management, patching, etc.
- **EKS (Kubernetes)**: Overkill for a simple application, greater complexity
- **Lambda**: Not suitable for long-running APIs, timeout limits

### 2. Load Balancer: Application Load Balancer (ALB)

**Decision**: ALB instead of NLB or CLB

**Reasons**:
- **Layer 7**: Path, host, header-based routing
- **Health checks**: Intelligent HTTP health checks
- **Integration**: Native with ECS targets
- **Metrics**: Detailed metrics in CloudWatch
- **TLS termination**: Certificate management with ACM

**Trade-offs**:
- Slightly more expensive than NLB for pure TCP traffic
- Lower throughput than NLB (not critical for this case)

### 3. Networking: Multi-AZ VPC with Private Subnets

**Decision**: ECS tasks in private subnets, ALB in public subnets

**Reasons**:
- **Security**: Tasks do not have public IPs
- **Compliance**: Aligned with security frameworks (CIS, NIST)
- **Defense in depth**: Multiple security layers
- **High Availability**: Multi-AZ for redundancy

**Configuration by environment**:

| Environment | VPC CIDR | AZs | Public Subnets | Private Subnets | NAT Gateways |
|----------|----------|-----|----------------|-----------------|--------------|
| **dev** | 10.0.0.0/16 | 2 | 2 (/24) | 2 (/24) | 1 |
| **cert** | 10.1.0.0/16 | 2 | 2 (/24) | 2 (/24) | 1 |
| **prod** | 10.2.0.0/16 | 3 | 3 (/24) | 3 (/24) | 3 |

**NAT Gateway Strategy**:

- **Dev/Cert**: 1 NAT Gateway (cost savings)
  - Cost: ~$32/month
  - Risk: Single point of failure for internet egress
  - Mitigation: Acceptable for non-prod environments

- **Prod**: 3 NAT Gateways (one per AZ)
  - Cost: ~$96/month
  - Benefit: High availability, no SPOF
  - Best practice: Recommended by AWS

**Important trade-off**:
- NAT Gateway is expensive (~$32/month + data transfer)
- Alternative explored: VPC Endpoints for S3, ECR, CloudWatch (cost savings)
- Future improvement: Implement VPC Endpoints to reduce NAT traffic

### 4. Container Registry: Amazon ECR

**Decision**: ECR instead of Docker Hub or private registries

**Reasons**:
- **Native integration**: With ECS, IAM, and CI/CD
- **Security scanning**: Integrated with Amazon Inspector
- **Lifecycle policies**: Automatic image retention
- **Private**: No risk of public exposure
- **IAM-based auth**: No separate credential management

**Configuration**:
- Image tag mutability: MUTABLE (allows latest tag)
- Scan on push: Enabled
- Lifecycle: Retain last 10 images

### 5. Logging: CloudWatch Logs with Structured JSON

**Decision**: Structured logs in JSON format to CloudWatch

**Reasons**:
- **Queryable**: CloudWatch Insights allows complex queries
- **Structured**: Easy parsing and analysis
- **Standardized**: Consistent schema
- **Integration**: Easy export to S3, OpenSearch, etc.

**Log schema**:
```json
{
  "timestamp": "2026-03-03T12:34:56.789Z",
  "level": "INFO|ERROR|WARNING",
  "message": "Human-readable message",
  "service": "streaver-helloworld",
  "method": "GET",
  "path": "/endpoint",
  "status": 200,
  "duration_ms": 15.23,
  "error": "Error details if applicable"
}
```

**Retention by environment**:
- Dev: 7 days (cost savings)
- Cert: 14 days
- Prod: 30 days (compliance and debugging)

**Future improvement**: Export to S3 with Athena for historical analysis

### 6. Monitoring: CloudWatch Metrics, Alarms, and Dashboards

**Decision**: Native CloudWatch instead of third-party (Datadog, New Relic)

**Reasons**:
- **Cost**: Included in AWS, no additional costs
- **Integration**: Native with ECS, ALB, SNS
- **Simplicity**: No agents or complex configuration required
- **Sufficient**: For the scope of the challenge

**Configured alarms**:

| Alarm | Threshold | Evaluation Period | Action |
|--------|-----------|-------------------|--------|
| High CPU | >80% | 2 of 2 datapoints (5 min) | SNS |
| High Memory | >80% | 2 of 2 datapoints (5 min) | SNS |
| 5XX Errors | >10 errors | 1 of 1 datapoint (5 min) | SNS |
| High Latency | p99 >1s | 2 of 2 datapoints (5 min) | SNS |
| Unhealthy Targets | <2 healthy | 1 of 1 datapoint (1 min) | SNS |

**SNS Topic**: Email notifications (configurable by environment)

**Trade-offs**:
- Fewer features than Datadog/New Relic (APM, distributed tracing)
- CloudWatch Insights not as powerful as Splunk/ELK
- Sufficient for 80% of use cases
- Future improvement: AWS X-Ray for distributed tracing

### 7. Auto-Scaling: CPU and Memory-based

**Decision**: Auto-scaling based on CloudWatch metrics

**Configuration by environment**:

| Environment | Min Tasks | Max Tasks | Target CPU | Target Memory | Scale-in Cooldown | Scale-out Cooldown |
|----------|-----------|-----------|------------|---------------|-------------------|-------------------|
| **dev** | 1 | 2 | 70% | 70% | 300s | 60s |
| **cert** | 2 | 4 | 70% | 70% | 300s | 60s |
| **prod** | 3 | 10 | 60% | 60% | 300s | 60s |

**Reasons**:
- **Responsive**: Fast scale-out (60s) for traffic spikes
- **Conservative scale-in**: 300s to avoid flapping
- **Headroom**: Target 60-70% allows absorbing spikes
- **Multi-metric**: CPU and memory for complete coverage

**Trade-off**:
- No scaling based on request rate or custom metrics
- Future improvement: Target tracking with ALB RequestCountPerTarget

### 8. Multi-Environment Strategy: Separate AWS Accounts

**Decision**: 3 separate AWS accounts (dev, cert, prod)

**Reasons**:
- **Security**: Blast radius limited per account
- **Compliance**: Independent IAM/SCP controls
- **Billing**: Clear cost allocation per environment
- **Isolation**: No risk of cross-environment impact
- **Best practice**: Recommended by AWS Well-Architected

**Assumed structure**:
```
AWS Organization
├── Management Account (root)
├── Dev Account (111111111111)
├── Cert Account (222222222222)
└── Prod Account (333333333333)
```

**Alternatives**:
- Single account with tags: Less secure, larger blast radius
- Separate workspaces in Terraform: Logical isolation but same account

### 9. Dual IaC: CDK + Terraform

**Decision**: Implement BOTH CDK and Terraform (challenge requirement)

**CDK (AWS Cloud Development Kit)**:
- **Type safety**: Python with type hints
- **Abstractions**: High-level L2/L3 constructs
- **AWS-native**: First-class support for new services
- **Testing**: Unit tests with CDK assertions

**Terraform**:
- **Multi-cloud**: Provider-agnostic
- **Mature ecosystem**: Abundance of modules and examples
- **State management**: S3 backend + DynamoDB lock
- **Plan preview**: Terraform plan for exact changes

**Modular structure**:

Both implementations follow the same 3 module/stack pattern:

1. **Networking**: VPC, subnets, NAT, IGW, route tables
2. **ECS**: Cluster, service, task definition, ALB, auto-scaling
3. **Monitoring**: CloudWatch alarms, dashboard, SNS topic

**Trade-off**:
- Duplicate maintenance of two codebases
- Potential drift between CDK and Terraform
- Demonstrates versatility and knowledge of both tools
- In real production, ONE tool would be chosen

### 10. CI/CD: GitHub Actions with OIDC

**Decision**: GitHub Actions instead of Jenkins, CircleCI, GitLab CI

**Reasons**:
- **Native**: Integrated with GitHub (where the code is)
- **Free tier**: Generous for public projects
- **Matrix builds**: Easy job parallelization
- **Marketplace**: Wide selection of reusable actions
- **OIDC**: Authentication without long-lived credentials

**OIDC vs IAM Access Keys**:
- **Security**: No hardcoded credentials in secrets
- **Short-lived**: Tokens expire automatically
- **Auditable**: CloudTrail shows token subject
- **Best practice**: Recommended by GitHub and AWS

**Pipeline strategy**:

- **CI (ci.yml)**: 8 parallel jobs on each push/PR
  - Lint, Test, Security, Docker, CDK, Terraform, IaC-Security, Summary
  - Estimated time: ~8-10 minutes

- **CD Dev (cd-dev.yml)**: Auto-deploy on merge to main
  - Build → Push ECR → Deploy CDK/Terraform → Smoke tests

- **CD Cert (cd-cert.yml)**: Manual trigger with approval
  - Image promotion from dev ECR
  - Requires DevOps lead approval

- **CD Prod (cd-prod.yml)**: Strict manual with multi-approval
  - Requires explicit image tag (no latest)
  - Requires approval from 2+ reviewers
  - Pre-deployment validation checks

**Important note**:
- All deploy jobs are disabled (`if: false`) because AWS is not available
- Placeholder jobs with setup instructions are included
- In a real environment, they would be enabled after configuring OIDC + secrets

---

## Security Decisions

### 1. Multi-Stage Docker Build

**Decision**: Multi-stage build with non-root user

```dockerfile
# Stage 1: Builder (with gcc, build tools)
FROM python:3.11-slim as builder
...

# Stage 2: Runtime (runtime only, no build tools)
FROM python:3.11-slim
...
USER appuser  # Non-root!
```

**Reasons**:
- **Smaller image**: Runtime image ~150MB vs ~500MB monolithic
- **Security**: No build tools in final image
- **Non-root**: Principle of least privilege
- **Attack surface**: Reduced attack surface

### 2. Multi-Layer Security Scanning

**Decision**: 4 complementary scanning tools

| Tool | Scope | Execution |
|------|-------|-----------|
| **Bandit** | Python code (SAST) | CI pipeline |
| **Safety** | Python dependencies (SCA) | CI pipeline |
| **Checkov** | IaC (CDK/Terraform) | CI pipeline |
| **Trivy** | Container vulnerabilities | CI pipeline |

**Reasons**:
- **Defense in depth**: Multiple detection layers
- **Shift-left**: Detect issues before deploy
- **Compliance**: Aligned with DevSecOps practices
- **SARIF export**: Integration with GitHub Security tab

**Configuration**:
- Bandit: Exclude tests, skip low-severity binds
- Checkov: Skip checks for dev environment shortcuts
- Trivy: Scan OS + app dependencies

### 3. Secrets Management

**Decision**: AWS Secrets Manager (in future implementation)

**Reasons**:
- **Rotation**: Programmable automatic rotation
- **Audit**: CloudTrail logging of accesses
- **Encryption**: KMS encryption at rest
- **IAM integration**: Fine-grained access control

**Note**: This challenge has no real secrets, but the structure is prepared for:

```python
# Example future implementation
secret_arn = secretsmanager.Secret(self, "AppSecret", ...)
task_definition.add_secret(
    secret_name="DB_PASSWORD",
    secret=ecs.Secret.from_secrets_manager(secret_arn)
)
```

### 4. Network Security

**Decision**: Defense in depth with multiple layers

**Security Groups**:

- **ALB SG**:
  - Inbound: 80/443 from 0.0.0.0/0 (internet)
  - Outbound: Ephemeral ports to ECS SG

- **ECS SG**:
  - Inbound: 5000 only from ALB SG
  - Outbound: 443 to internet (for ECR pulls, CloudWatch)

**NACLs**: Default (no custom, SGs are sufficient)

**Reasons**:
- **Least privilege**: Only necessary ports
- **Source restriction**: ECS only accessible from ALB
- **Stateful**: SGs handle return traffic automatically

### 5. IAM Roles: Least Privilege

**Decision**: Separate roles for ECS Task and Task Execution

**ECS Task Role** (app runtime):
- Permissions: CloudWatch Logs, CloudWatch Metrics
- NO permissions for: ECR, Secrets Manager (yet)

**ECS Task Execution Role** (ECS agent):
- Permissions: ECR pull, CloudWatch Logs create stream
- Managed policy: AmazonECSTaskExecutionRolePolicy

**Reasons**:
- **Separation of concerns**: Runtime vs infrastructure
- **Least privilege**: Only necessary permissions
- **Audit**: Easy to trace which role performed which action

---

## Testing Decisions

### 1. Unit Tests: Pytest with 100% Endpoint Coverage

**Decision**: 32 comprehensive tests for the Flask app

**Coverage**:
- All endpoints (/, /health, /error, /metrics)
- Error handling and status codes
- Metrics tracking (increment, retrieval)
- Structured logging format
- JSON response validation

**Reasons**:
- **Confidence**: High confidence in core functionality
- **Regression**: Detect breaking changes
- **Documentation**: Tests as executable spec

### 2. CDK Tests: Infrastructure Unit Tests

**Decision**: 16 tests with CDK assertions

**Coverage**:
- VPC with public and private subnets
- ECS cluster, service, task definition
- ALB, target group, listeners
- Auto-scaling policies
- CloudWatch alarms and dashboard

**Reasons**:
- **Prevent regressions**: Detect unintended changes
- **Fast feedback**: Tests execute in ~5s
- **Documentation**: Tests describe the architecture

**Trade-off**:
- No integration tests (require real AWS)
- Future improvement: LocalStack for integration tests

### 3. Load Tests: K6 with Two-Phase Approach

**Decision**: Smoke test (30s) + Load test (8 min)

**Smoke test**:
- 10 VUs, 30 seconds
- Quick endpoint validation
- Relaxed thresholds

**Load test**:
- Stage 1: Ramp-up to 50 VUs (2 min)
- Stage 2: Sustained 100 VUs (4 min)
- Stage 3: Ramp-down to 0 VUs (2 min)
- Thresholds: p95 <500ms, p99 <1s

**Reasons**:
- **Realistic**: Simulates real traffic with ramp-up/down
- **Scalability validation**: Verifies auto-scaling
- **Performance SLOs**: Defines clear thresholds

**Trade-off**:
- Requires running app (cannot execute without AWS)
- Future improvement: Include in CD pipeline with ephemeral environment

### 4. Security Scanning: Multiple Tools, Different Scopes

**Decision**: See Security section above

### 5. IaC Validation: Synth/Validate + Plan

**Decision**: Validation scripts for CDK and Terraform

**CDK validation**:
```bash
cdk synth --all -c environment=dev
pytest infrastructure/cdk/tests/
```

**Terraform validation**:
```bash
terraform init
terraform validate
terraform fmt -check
terraform plan -var-file=environments/dev.tfvars
```

**Reasons**:
- **Syntax validation**: Detect basic errors
- **Type checking**: CDK has advantage here (Python types)
- **Plan preview**: Terraform plan shows exact changes

**Limitation**:
- Without AWS, cannot do `cdk deploy` or `terraform apply`
- Syntactic and logical validation is sufficient for challenge

---

## Cost Optimization Decisions

### 1. NAT Gateway: Single for Dev/Cert, Multi for Prod

**Annual savings**: ~$768 in dev + cert

| Environment | NAT Gateways | Monthly cost | Annual cost |
|----------|--------------|---------------|-------------|
| Dev | 1 | $32 | $384 |
| Cert | 1 | $32 | $384 |
| Prod | 3 | $96 | $1,152 |

**Future improvement**: VPC Endpoints (S3, ECR, CloudWatch)
- Cost: ~$7/month per endpoint
- Savings: Reduces NAT data transfer (~50-70%)
- ROI: Positive in high-traffic environments

### 2. Fargate Spot: Considered but NOT Implemented

**Decision**: DO NOT use Fargate Spot (yet)

**Reasons**:
- **Simplicity first**: Fargate on-demand is predictable
- Spot can interrupt tasks without notice (2 min warning)
- Requires graceful shutdown handling

**Future improvement**: Mix 70% On-demand + 30% Spot
- Savings: ~30% on compute costs
- Risk: Mitigated with circuit breakers and health checks

### 3. CloudWatch Logs: Retention Policy by Environment

**Savings**: Variable depending on traffic

| Environment | Retention | Cost Impact |
|----------|-----------|-------------|
| Dev | 7 days | Low (few requests) |
| Cert | 14 days | Medium |
| Prod | 30 days | Justified (compliance) |

**Future improvement**: Export to S3 + Athena
- S3 cost: ~$0.023/GB/month (vs $0.50/GB CloudWatch)
- Savings: ~95% for historical logs

### 4. ECR Lifecycle: Retain Only Last 10 Images

**Savings**: Prevents unlimited accumulation

**Policy**:
```json
{
  "rules": [{
    "rulePriority": 1,
    "description": "Keep last 10 images",
    "selection": {
      "tagStatus": "any",
      "countType": "imageCountMoreThan",
      "countNumber": 10
    },
    "action": { "type": "expire" }
  }]
}
```

**Reasons**:
- **Sufficient**: 10 images cover 2+ weeks of deploys
- **Automatic**: No manual cleanup required
- **Cost**: Avoids unnecessary storage costs

### 5. Right-Sizing: Task Resources by Environment

| Environment | vCPU | Memory | Cost/hour | Justification |
|----------|------|--------|------------|---------------|
| Dev | 0.25 | 512 MB | $0.012 | Low traffic |
| Cert | 0.5 | 1024 MB | $0.024 | Realistic testing |
| Prod | 1 | 2048 MB | $0.073 | Performance + headroom |

**Future improvement**: CloudWatch Container Insights
- Analyze actual utilization
- Right-size based on historical data
- Potential savings: 20-30%

---

## CI/CD Decisions

### 1. Pipeline Strategy: CI Every Push, CD Manual (Mostly)

**CI Pipeline (ci.yml)**:
- Trigger: Every push + PR
- Duration: ~8-10 minutes
- Jobs: 8 parallel (lint, test, security, docker, cdk, terraform, iac-security, summary)

**CD Pipelines**:
- **Dev**: Auto on merge to main (if: false for now)
- **Cert**: Manual trigger with approval
- **Prod**: Manual trigger with multi-approval + explicit tag

**Reasons**:
- **Fast feedback**: Fast CI detects issues early
- **Control**: Manual CD avoids accidental deploys
- **Safety**: Production requires multiple approvals

### 2. Image Promotion: Build Once, Deploy Many

**Decision**: Build in dev, promote same image to cert/prod

**Flow**:
```
main branch
  ↓
Build + Push → dev-ecr/app:git-abc123
  ↓
[Tests pass]
  ↓
Tag → cert-ecr/app:git-abc123  (copy)
  ↓
[Approval + Validation]
  ↓
Tag → prod-ecr/app:git-abc123  (copy)
```

**Reasons**:
- **Immutability**: Same image in all environments
- **Speed**: No rebuild, only copy/retag
- **Confidence**: What is tested in dev/cert goes to prod
- **Traceability**: Git SHA in tag

### 3. OIDC Authentication: No Long-Lived Credentials

**Assumed setup**:

```yaml
# In GitHub Actions
- uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::111111111111:role/GitHubActionsRole
    aws-region: us-east-1
```

**IAM Trust Policy**:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:sub": "repo:pcaamano182/streaver-helloworld:ref:refs/heads/main"
      }
    }
  }]
}
```

**Reasons**:
- **Security**: No AWS_ACCESS_KEY_ID/SECRET in GitHub secrets
- **Audit**: CloudTrail shows repo/branch in each call
- **Rotation**: No credentials to rotate
- **Best practice**: Recommended by GitHub and AWS

### 4. Rollback Strategy: Blue/Green with Circuit Breaker

**Decision**: Deployment circuit breaker enabled

```python
deployment_configuration=ecs.DeploymentConfiguration(
    maximum_percent=200,  # Blue/Green: both task sets active
    minimum_healthy_percent=100,  # No downtime
    deployment_circuit_breaker=ecs.DeploymentCircuitBreaker(
        enable=True,
        rollback=True  # Auto-rollback on failure
    )
)
```

**Reasons**:
- **Zero downtime**: 100% healthy during deploy
- **Auto-rollback**: Detects failures and rolls back
- **Safety net**: Prevents broken deploys in production

**Future improvement**: Canary deployments with CodeDeploy
- 10% → 50% → 100% traffic shift
- Automated rollback based on CloudWatch alarms

---

## Future Improvements (With More Time)

### Infrastructure

#### 1. Multi-Region Active-Active

**Implementation**:
- Route 53 with health checks and failover
- DynamoDB global tables
- S3 cross-region replication
- CloudFront with multiple origins

**Benefits**:
- Disaster recovery (RTO < 5 min, RPO < 1 min)
- Latency reduction for global users
- Compliance with data residency requirements

**Estimated cost**: +150% (2.5x due to duplication + networking)

#### 2. AWS WAF + Shield

**Implementation**:
- WAF on ALB with managed rule groups
- Rate limiting per IP
- Geo-blocking for high-risk countries
- Shield Standard (included) or Advanced ($3k/month)

**Benefits**:
- Protection against OWASP Top 10
- DDoS mitigation
- Bot detection

**Estimated cost**: $5-10/month (WAF) or $3k/month (Shield Advanced)

#### 3. Service Mesh (AWS App Mesh or Istio)

**Implementation**:
- Sidecar proxies (Envoy)
- mTLS between services
- Traffic shaping (circuit breakers, retries, timeouts)
- Distributed tracing integration

**Benefits**:
- Zero trust networking
- Advanced traffic management
- Improved observability

**Trade-off**: +40% operational complexity

#### 4. Database Layer

**Option 1: RDS PostgreSQL**
- Multi-AZ for HA
- Read replicas for scale-out
- Automated backups (PITR 35 days)

**Option 2: DynamoDB**
- Serverless, auto-scaling
- Global tables for multi-region
- DynamoDB Streams for CDC

**Decision**: Depends on workload (relational vs NoSQL)

#### 5. Caching Layer (ElastiCache)

**Implementation**:
- Redis cluster mode
- 3 nodes (Multi-AZ)
- Cache-aside pattern

**Benefits**:
- Reduces latency (sub-millisecond)
- Reduces database load
- Session storage for multiple tasks

**Estimated cost**: $50-100/month (cache.t3.micro)

### Observability

#### 1. Distributed Tracing (AWS X-Ray)

**Implementation**:
```python
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.flask.middleware import XRayMiddleware

xray_recorder.configure(service='streaver-helloworld')
XRayMiddleware(app, xray_recorder)
```

**Benefits**:
- Request flow visualization
- Latency breakdown (ALB → ECS → downstream services)
- Error root cause analysis

**Cost**: ~$5/million traces (first 100k free)

#### 2. Synthetic Monitoring (CloudWatch Synthetics)

**Implementation**:
- Canaries running every 5 minutes
- Multi-region probes
- Assertions on response time, status, content

**Benefits**:
- Proactive monitoring (detects issues before users)
- SLA validation
- Third-party endpoint monitoring

**Cost**: ~$0.001/run (~$8/month per canary)

#### 3. Log Aggregation (OpenSearch)

**Implementation**:
- CloudWatch Logs → Lambda → OpenSearch
- Kibana dashboards
- Alerting rules

**Benefits**:
- Advanced queries (vs CloudWatch Insights)
- Custom visualizations
- Cross-service correlation

**Cost**: $50-200/month (t3.small.search)

**Alternative**: Managed Grafana + Loki (more economical)

#### 4. SLIs/SLOs/Error Budgets

**Definition**:
```yaml
SLOs:
  - name: Availability
    target: 99.9%
    window: 30d
    SLI: successful_requests / total_requests

  - name: Latency
    target: 95% < 500ms
    window: 7d
    SLI: p95_latency
```

**Benefits**:
- Objective reliability targets
- Error budget as guide for velocity vs stability
- Stakeholder alignment

**Tools**: Prometheus + Grafana + sloth, or custom tool

### Security

#### 1. SIEM (Security Information and Event Management)

**Implementation**:
- AWS Security Hub (aggregator)
- GuardDuty (threat detection)
- Config Rules (compliance)
- CloudTrail (audit logs)

**Benefits**:
- Centralized security posture
- Automatic threat detection
- Compliance reporting (PCI, HIPAA, etc.)

**Cost**: $5-20/month (depends on volume)

#### 2. Runtime Security (Falco or AWS GuardDuty Runtime Monitoring)

**Implementation**:
- Sidecar in ECS tasks
- Anomalous behavior detection
- Real-time alerts

**Benefits**:
- Detect container escape attempts
- Unauthorized process execution
- Network anomalies

**Cost**: $10-30/task/month

#### 3. Automatic Secrets Rotation

**Implementation**:
```python
secret = secretsmanager.Secret(
    self, "DBPassword",
    generate_secret_string=secretsmanager.SecretStringGenerator(
        secret_string_template='{"username":"admin"}',
        generate_string_key="password"
    )
)

# Lambda for rotation every 30 days
secret.add_rotation_schedule(
    "RotationSchedule",
    automatically_after=Duration.days(30),
    rotation_lambda=rotation_function
)
```

**Benefits**:
- Reduces risk of credential compromise
- Compliance with security policies
- Zero-touch automation

#### 4. Network Segmentation (PrivateLink)

**Implementation**:
- VPC Endpoints for AWS services (S3, ECR, Secrets Manager)
- PrivateLink for internal services
- No internet traffic

**Benefits**:
- Data exfiltration prevention
- Reduces attack surface
- Savings on NAT Gateway costs

**Cost**: $7/month per endpoint + $0.01/GB

### CI/CD

#### 1. GitOps with ArgoCD or Flux

**Implementation**:
- Git as single source of truth
- Automatic sync every 3 minutes
- Drift detection and remediation

**Benefits**:
- Declarative deployments
- Audit trail (Git history)
- Easy rollback (git revert)

**Trade-off**: Requires Kubernetes (not compatible with ECS)

#### 2. Feature Flags (AWS AppConfig or LaunchDarkly)

**Implementation**:
```python
from appconfig import AppConfigClient

client = AppConfigClient()
if client.get_flag('new-feature-enabled'):
    # New code path
else:
    # Old code path
```

**Benefits**:
- Deploy code != enable feature
- Progressive rollout (10% → 50% → 100%)
- Kill switch for problematic features

**Cost**: $0 (AppConfig) or $10-100/month (LaunchDarkly)

#### 3. Canary Deployments with AWS CodeDeploy

**Implementation**:
```yaml
deployment_config:
  type: Canary10Percent5Minutes
  # 10% traffic → wait 5 min → 100%
  # Auto-rollback if CloudWatch alarm triggers
```

**Benefits**:
- Reduces blast radius of bugs
- Automated rollback
- Real traffic validation

**Improvement over**: Blue/Green (more granular)

#### 4. Performance Testing in Pipeline

**Implementation**:
```yaml
- name: Load Test
  run: |
    k6 run --vus 100 --duration 5m tests/load/k6-load-test.js
    # Fail build if p95 > 500ms
```

**Benefits**:
- Detect performance regressions
- Pre-production SLO validation
- Capacity planning data

**Trade-off**: Requires ephemeral or long-running staging environment

---

## Lessons Learned

### 1. Deprecation Warnings Matter

**Issue**: CDK had 4 deprecation warnings initially

**Fix**:
- `datetime.utcnow()` → `datetime.now(timezone.utc)`
- `alb.metric_*()` → `alb.metrics.*`
- `RetentionDays` integer → enum mapping

**Lesson**: Resolve warnings early to avoid future breaking changes

### 2. Terraform Syntax Is Strict

**Issue**: Invalid `deployment_configuration` block

```terraform
# ❌ Incorrect
deployment_configuration {
  deployment_circuit_breaker {
    enable = true
    rollback = true
  }
}

# ✅ Correct
deployment_circuit_breaker {
  enable = true
  rollback = true
}
```

**Lesson**: Consult official docs, don't assume syntax

### 3. Security Scanning Needs Tuning

**Issue**: Bandit reported 80 LOW warnings (noise)

**Fix**: Config file `.bandit` with excludes:
```yaml
exclude_dirs:
  - '/tests/'
  - '/.venv/'
```

**Lesson**: Security tools require tuning to avoid alert fatigue

### 4. Test Validation Before Commit

**Issue**: User asked "were you able to run these tests?" in Phase 4

**Lesson**: ALWAYS validate tests locally before commit, don't assume they pass

### 5. Documentation Is As Important As Code

**Effort distribution**:
- Code: ~60%
- Tests: ~20%
- Documentation: ~20%

**Lesson**: Comprehensive README is critical for onboarding and maintainability

---

## Conclusion

This project demonstrates a production-ready implementation following best practices for:

- **Infrastructure as Code**: Modular, testable, reproducible
- **Security**: Defense in depth, least privilege, automated scanning
- **Observability**: Structured logs, metrics, alarms, dashboards
- **Reliability**: Multi-AZ, auto-scaling, health checks, circuit breakers
- **CI/CD**: Automated testing, security scanning, deployment pipelines
- **Cost Optimization**: Right-sizing, lifecycle policies, retention tuning

The future improvements listed above would transform this project from a "good enough" MVP to an enterprise-grade system capable of handling millions of requests with high availability and strict compliance.

---

**Developed for the Streaver technical challenge - Senior DevOps Engineer**
