# GitHub Actions CI/CD Workflows

Comprehensive CI/CD pipeline for the Streaver Hello World application using GitHub Actions.

## Workflows Overview

### 1. CI - Continuous Integration (`ci.yml`)

**Triggers:**
- Pull requests to main/master
- Push to main/master
- Manual trigger (workflow_dispatch)

**Jobs:**
1. **Lint and Format**: Ruff linter and format checking
2. **Unit Tests**: Pytest with coverage reporting
3. **Security Scan**: Bandit and Safety dependency checks
4. **Docker Build**: Build image and run Trivy scan
5. **Validate CDK**: CDK unit tests and synth for all environments
6. **Validate Terraform**: Format check, init, validate, and plan
7. **IaC Security Scan**: Checkov scanning
8. **Summary**: Aggregate results and set final status

**Artifacts:**
- Bandit security report (JSON)
- Trivy scan results (SARIF)
- Checkov reports (JSON)
- Code coverage (uploaded to Codecov)

**Duration:** ~8-10 minutes

---

### 2. CD - Deploy to Dev (`cd-dev.yml`)

**Triggers:**
- Push to main/master (automatic)
- Manual trigger (workflow_dispatch)

**Environment:** Development (dev)

**Jobs:**
1. **Deploy Infrastructure**: CDK deploy to dev environment
2. **Build and Push Image**: Build Docker image and push to ECR
3. **Update ECS Service**: Deploy new task definition to ECS
4. **Run Integration Tests**: End-to-end API tests
5. **Run Smoke Tests**: K6 smoke tests

**Configuration Required:**
- `AWS_ROLE_ARN_DEV`: IAM role for dev deployment (GitHub secret)

**Duration:** ~10-15 minutes

**Status:** Jobs disabled by default (requires AWS credentials)

---

### 3. CD - Deploy to Cert (`cd-cert.yml`)

**Triggers:**
- Manual trigger only (workflow_dispatch)

**Environment:** Certification (cert) with **manual approval required**

**Inputs:**
- `image_tag`: Docker image tag to promote (default: latest)

**Jobs:**
1. **Manual Approval**: GitHub environment protection rule
2. **Deploy Infrastructure**: CDK deploy to cert environment
3. **Promote Image**: Pull from dev ECR, push to cert ECR
4. **Update ECS Service**: Force new deployment
5. **Run Tests**: Integration tests + full k6 load tests

**Configuration Required:**
- `AWS_ROLE_ARN_CERT`: IAM role for cert deployment
- `CERT_ALB_URL`: ALB DNS for testing
- GitHub environment protection rule for "cert"

**Duration:** ~15-20 minutes (plus approval time)

**Status:** Jobs disabled by default (requires AWS credentials)

---

### 4. CD - Deploy to Production (`cd-prod.yml`)

**Triggers:**
- Manual trigger only (workflow_dispatch)

**Environment:** Production with **strict manual approval required**

**Inputs:**
- `image_tag`: Docker image tag to promote (required, no "latest" allowed)
- `skip_tests`: Skip post-deployment tests (default: false)

**Jobs:**
1. **Production Approval**: GitHub environment protection rule
2. **Pre-Deployment Checks**: Verify image exists, check service status
3. **Deploy Infrastructure**: CDK deploy with diff preview
4. **Promote Image**: Pull from cert ECR, push to prod ECR (no "latest" tag)
5. **Update ECS Service**: Blue/Green deployment
6. **Post-Deployment Tests**: Smoke tests (unless skipped)
7. **Deployment Notification**: Send notifications (Slack/email)

**Configuration Required:**
- `AWS_ROLE_ARN_PROD`: IAM role for prod deployment
- `PROD_ALB_URL`: ALB DNS for testing
- GitHub environment protection rule for "production"

**Duration:** ~20-25 minutes (plus approval time)

**Status:** Jobs disabled by default (requires AWS credentials)

---

## Setup Instructions

### Prerequisites

1. **AWS Account Setup:**
   - Three AWS accounts (dev, cert, prod) recommended
   - Or use one account with separate resources per environment

2. **GitHub Repository Setup:**
   - Repository settings → Environments → Create environments: `cert`, `production`
   - Add required reviewers for each environment

### Step 1: Configure OIDC Provider in AWS

Create OIDC provider for GitHub Actions in each AWS account:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### Step 2: Create IAM Roles

Create IAM role for each environment with trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:YOUR_ORG/streaver-helloworld:*"
        }
      }
    }
  ]
}
```

Attach policies for:
- ECR (push/pull images)
- ECS (deploy services)
- CloudFormation (CDK deployments)
- IAM (create/manage roles)
- EC2, VPC (networking)
- CloudWatch (logs and metrics)

### Step 3: Add GitHub Secrets

Repository Settings → Secrets and variables → Actions → New repository secret:

**Required secrets:**
- `AWS_ROLE_ARN_DEV`: `arn:aws:iam::111111111111:role/GitHubActionsDevRole`
- `AWS_ROLE_ARN_CERT`: `arn:aws:iam::222222222222:role/GitHubActionsCertRole`
- `AWS_ROLE_ARN_PROD`: `arn:aws:iam::333333333333:role/GitHubActionsProdRole`
- `CERT_ALB_URL`: `http://alb-cert.us-east-1.elb.amazonaws.com`
- `PROD_ALB_URL`: `http://alb-prod.us-east-1.elb.amazonaws.com`

### Step 4: Enable Deployment Jobs

In each CD workflow file, change `if: false` to `if: true` for the deployment jobs:

```yaml
# Before
if: false  # Disabled - requires AWS credentials

# After
if: true
```

### Step 5: Configure Environment Protection Rules

1. Go to Settings → Environments
2. For `cert` environment:
   - Add 1 required reviewer
   - Set deployment branch to `main` or `master`
3. For `production` environment:
   - Add 2+ required reviewers
   - Set deployment branch to `main` or `master`
   - Optional: Add deployment delay (e.g., 30 minutes)

---

## Usage

### Running CI (Automatic)

CI runs automatically on every PR and push to main:

```bash
# Create a PR
git checkout -b feature/my-feature
git add .
git commit -m "feat: add new feature"
git push origin feature/my-feature

# CI will run automatically on the PR
```

### Deploying to Dev (Automatic)

Merge to main triggers automatic deployment to dev:

```bash
# Merge PR to main
# CD to dev runs automatically
```

Or trigger manually:
1. Go to Actions → CD - Deploy to Dev
2. Click "Run workflow"
3. Select branch: `main`
4. Click "Run workflow"

### Deploying to Cert (Manual Approval)

1. Go to Actions → CD - Deploy to Cert (Manual)
2. Click "Run workflow"
3. Select branch: `main`
4. Enter image tag (or leave empty for latest)
5. Click "Run workflow"
6. Wait for approval request
7. Approve the deployment
8. Monitor progress

### Deploying to Production (Manual Approval)

1. Go to Actions → CD - Deploy to Production (Manual)
2. Click "Run workflow"
3. Select branch: `main`
4. **Enter specific image tag** (e.g., `abc123-1234567890`)
5. Choose whether to skip tests
6. Click "Run workflow"
7. Wait for approval request (requires 2+ approvers)
8. Approve the deployment
9. Monitor progress
10. Verify deployment via notifications

---

## Workflow Details

### CI Workflow Jobs

#### Lint and Format
- Uses Ruff for fast Python linting
- Checks code formatting
- Continues on error to show all issues

#### Unit Tests
- Runs pytest with coverage
- Generates coverage report
- Uploads to Codecov (optional)
- Fails if tests fail

#### Security Scan
- Bandit: Python code security
- Safety: Dependency vulnerabilities
- Generates JSON reports
- Continues on error (informational)

#### Docker Build
- Builds multi-stage Dockerfile
- Uses build cache for speed
- Runs Trivy vulnerability scan
- Uploads SARIF to GitHub Security
- Smoke tests the container

#### Validate CDK
- Installs CDK CLI and dependencies
- Runs 16 CDK unit tests
- Synthesizes CloudFormation for all envs
- Fails if synthesis fails

#### Validate Terraform
- Checks formatting
- Validates configuration
- Runs plan for each environment
- Continues on plan errors (no AWS creds)

#### IaC Security Scan
- Runs Checkov on Terraform
- Checks for security misconfigurations
- Generates JSON report
- Continues on error (informational)

### CD Dev Workflow Jobs

#### Deploy Infrastructure
- Uses CDK to deploy/update infrastructure
- Outputs ALB DNS and other values
- Saves outputs as artifacts

#### Build and Push Image
- Generates unique image tag
- Builds Docker image
- Pushes to ECR (dev repository)
- Scans with Trivy

#### Update ECS Service
- Downloads current task definition
- Updates image to new tag
- Deploys to ECS
- Waits for stability

#### Integration Tests
- Runs pytest integration tests
- Tests all endpoints
- Verifies expected responses

#### Smoke Tests
- Installs k6
- Runs lightweight load test
- Verifies basic performance

### CD Cert Workflow Jobs

#### Manual Approval
- Requires GitHub environment approval
- Shows deployment details
- Can be rejected

#### Promote Image
- Pulls image from dev ECR
- Re-tags for cert ECR
- Pushes to cert repository
- Maintains traceability

#### Run Tests
- Integration tests
- **Full k6 load tests** (not just smoke)
- Generates performance reports

### CD Prod Workflow Jobs

#### Pre-Deployment Checks
- Verifies image exists in cert ECR
- Checks current service status
- Prevents bad deployments

#### Deploy Infrastructure
- Shows CDK diff before deploying
- Deploys infrastructure changes
- Logs all changes

#### Promote Image
- Pulls from cert ECR
- Pushes to prod ECR
- **Does not tag as "latest"** (safety)

#### Update ECS Service
- Blue/Green deployment strategy
- Gradual traffic shift
- Auto-rollback on failure

#### Post-Deployment Tests
- Smoke tests only (unless skipped)
- Verifies basic functionality
- Fast validation

#### Deployment Notification
- Summarizes deployment
- Can integrate with Slack/email/PagerDuty
- Records deployment metadata

---

## Troubleshooting

### CI Fails on Lint
```bash
# Fix locally
ruff check app/ --fix
ruff format app/
git add .
git commit -m "fix: lint issues"
```

### CI Fails on Tests
```bash
# Run tests locally
cd app
pytest tests/ -v
# Fix issues, commit, push
```

### Docker Build Fails
```bash
# Build locally
docker build -t test .
# Fix Dockerfile issues
```

### CDK Synth Fails
```bash
cd infrastructure/cdk
ENVIRONMENT=dev python app.py
# Fix CDK code issues
```

### Terraform Validate Fails
```bash
cd infrastructure/terraform
terraform fmt -recursive
terraform validate
# Fix Terraform issues
```

### Deployment Approval Pending
- Check repository settings → Environments
- Ensure approvers are added
- Notify approvers
- They must approve from Actions tab

### Deployment Fails
- Check CloudWatch Logs
- Review ECS task events
- Check ALB target health
- Verify security groups
- Check IAM permissions

---

## Best Practices

### 1. Branch Protection
- Require CI to pass before merge
- Require code reviews
- Restrict who can push to main

### 2. Environment Protection
- Cert: 1 reviewer minimum
- Prod: 2+ reviewers
- Use deployment delays for high-risk changes

### 3. Image Tagging
- Dev: Use git SHA + timestamp
- Cert: Promote from dev with same tag
- Prod: Require explicit tag (no "latest")

### 4. Rollback Strategy
- Keep previous task definitions
- Can rollback via ECS console
- Or redeploy previous image tag

### 5. Monitoring
- Watch CloudWatch dashboards during deployment
- Set up alarms before deployment
- Have rollback plan ready

### 6. Testing
- Always run full tests in cert
- Smoke tests are sufficient for prod (fast validation)
- Load test in cert, not prod

---

## Extending the Pipeline

### Add Slack Notifications

```yaml
- name: Send Slack notification
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "Deployment to ${{ env.ENVIRONMENT }} completed"
      }
```

### Add Datadog Integration

```yaml
- name: Send Datadog event
  run: |
    curl -X POST "https://api.datadoghq.com/api/v1/events" \
      -H "DD-API-KEY: ${{ secrets.DD_API_KEY }}" \
      -d '{
        "title": "Deployment to ${{ env.ENVIRONMENT }}",
        "text": "Image: ${{ github.sha }}",
        "tags": ["environment:${{ env.ENVIRONMENT }}"]
      }'
```

### Add Blue/Green Deployment

Use AWS CodeDeploy with ECS:

```yaml
- name: Create CodeDeploy deployment
  run: |
    aws deploy create-deployment \
      --application-name MyApp \
      --deployment-group-name MyDeploymentGroup \
      --deployment-config-name CodeDeployDefault.ECSAllAtOnce
```

---

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [AWS Actions for GitHub](https://github.com/aws-actions)
- [OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Environment Protection Rules](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
