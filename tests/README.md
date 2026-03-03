# Testing Suite

Comprehensive testing suite for the Streaver Hello World application covering unit tests, integration tests, load tests, security scans, and infrastructure validation.

## Test Categories

### 1. Application Tests

#### Unit Tests
Located in `app/tests/test_unit.py`

**What they test:**
- All Flask endpoints (/, /health, /error, /metrics)
- Request/response handling
- Metrics tracking
- Error handling
- HTTP method validation

**Run unit tests:**
```bash
cd app
python -m pytest tests/test_unit.py -v
```

**Coverage:**
```bash
python -m pytest tests/test_unit.py --cov=. --cov-report=html
```

#### Integration Tests
Located in `app/tests/test_integration.py`

**What they test:**
- End-to-end API functionality
- Load balancer health
- Service availability
- Response times

**Note:** Requires deployed environment with `INTEGRATION_TEST_URL` set.

**Run integration tests:**
```bash
export INTEGRATION_TEST_URL=http://your-alb-dns-name
cd app
python -m pytest tests/test_integration.py -v
```

---

### 2. Load Tests

Located in `tests/load/`

#### K6 Load Test
Comprehensive load testing with ramp-up, steady state, and ramp-down phases.

**Configuration:**
- Ramp-up: 0→100 users over 2 minutes
- Steady: 100 users for 5 minutes
- Ramp-down: 100→0 over 1 minute

**Thresholds:**
- p95 response time < 500ms
- p99 response time < 1000ms
- Error rate < 1%

**Run load test:**
```bash
# Install k6
# macOS: brew install k6
# Linux: https://k6.io/docs/getting-started/installation/

# Run test
export TARGET_URL=http://your-alb-dns-name
k6 run tests/load/k6-load-test.js

# With custom settings
k6 run --vus 50 --duration 3m tests/load/k6-load-test.js
```

#### K6 Smoke Test
Lightweight smoke test for quick validation.

**Configuration:**
- 5 virtual users
- 1 minute duration
- Tests all endpoints

**Run smoke test:**
```bash
export TARGET_URL=http://your-alb-dns-name
k6 run tests/load/k6-smoke-test.js
```

---

### 3. Security Tests

Located in `tests/security/`

Run all security tests:
```bash
bash tests/security/run-security-tests.sh
```

#### Bandit - Python Security Linter
Scans Python code for common security issues.

**Install:**
```bash
pip install bandit
```

**Run manually:**
```bash
bandit -r app/ -c tests/security/.bandit
```

#### Safety - Dependency Vulnerability Scanner
Checks Python dependencies for known vulnerabilities.

**Install:**
```bash
pip install safety
```

**Run manually:**
```bash
safety check --file app/requirements.txt
```

#### Checkov - IaC Security Scanner
Scans Terraform and CloudFormation for security misconfigurations.

**Install:**
```bash
pip install checkov
```

**Run manually:**
```bash
# Terraform
checkov -d infrastructure/terraform --config-file tests/security/.checkov.yaml

# CDK (after synth)
checkov -d infrastructure/cdk/cdk.out --framework cloudformation
```

#### Trivy - Container Image Scanner
Scans Docker images for vulnerabilities.

**Install:**
```bash
# macOS
brew install trivy

# Linux
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
sudo apt-get update
sudo apt-get install trivy
```

**Run manually:**
```bash
docker build -t streaver-helloworld:test .
trivy image --config tests/security/trivy.yaml streaver-helloworld:test
```

---

### 4. Infrastructure Tests

#### CDK Validation
Tests CDK stacks and synthesizes CloudFormation templates.

**Run CDK validation:**
```bash
bash tests/validate-cdk.sh
```

**What it does:**
- Installs dependencies
- Runs CDK unit tests (16 tests)
- Synthesizes templates for dev/cert/prod
- Validates CloudFormation output

**Run manually:**
```bash
cd infrastructure/cdk

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Synthesize for each environment
ENVIRONMENT=dev python app.py
ENVIRONMENT=cert python app.py
ENVIRONMENT=prod python app.py
```

#### Terraform Validation
Validates Terraform configuration and modules.

**Run Terraform validation:**
```bash
bash tests/validate-terraform.sh
```

**What it does:**
- Formats Terraform files
- Initializes providers
- Validates configuration
- Runs plan for each environment

**Run manually:**
```bash
cd infrastructure/terraform

# Format
terraform fmt -recursive

# Initialize
terraform init -backend=false

# Validate
terraform validate

# Plan for environment
terraform plan -var-file=environments/dev.tfvars
```

---

## CI/CD Integration

These tests are integrated into GitHub Actions workflows:

### On Pull Request
- Unit tests
- Bandit security scan
- Safety dependency check
- CDK validation
- Terraform validation

### On Merge to Main
- All PR checks
- Docker build and Trivy scan
- Deploy to dev environment
- Integration tests against dev
- Smoke tests

### Manual Triggers
- Load tests (can be run manually)
- Full security scan
- Deploy to cert/prod

---

## Test Results and Reports

### Unit Test Coverage
```bash
cd app
pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html
```

### Load Test Results
K6 outputs results to:
- Console (real-time metrics)
- `tests/load/k6-results.json` (detailed results)

### Security Scan Results
Results are printed to console. Can be redirected to files:
```bash
bash tests/security/run-security-tests.sh > security-report.txt 2>&1
```

---

## Best Practices

### Before Committing
```bash
# Run unit tests
cd app && pytest tests/test_unit.py

# Run security scans
bash tests/security/run-security-tests.sh

# Validate IaC
bash tests/validate-cdk.sh
bash tests/validate-terraform.sh
```

### Before Deploying
```bash
# Run all tests locally
cd app && pytest tests/

# Build and test Docker image
docker build -t streaver-helloworld:test .
docker run -p 5000:5000 streaver-helloworld:test

# Test endpoints
curl http://localhost:5000/health
```

### After Deployment
```bash
# Run smoke test
export TARGET_URL=http://your-alb-dns-name
k6 run tests/load/k6-smoke-test.js

# Run integration tests
export INTEGRATION_TEST_URL=http://your-alb-dns-name
cd app && pytest tests/test_integration.py -v
```

---

## Troubleshooting

### Unit Tests Fail
- Check Python version (3.11+)
- Verify dependencies: `pip install -r requirements.txt -r tests/requirements-test.txt`
- Check for syntax errors in application code

### Integration Tests Skip
- Ensure `INTEGRATION_TEST_URL` environment variable is set
- Verify ALB DNS is accessible
- Check security groups allow inbound traffic

### Load Tests Timeout
- Increase timeout in k6 script
- Check network connectivity
- Verify target can handle load

### Security Scans Fail
- Review findings and assess risk
- Update dependencies if vulnerabilities found
- Add exceptions to `.trivyignore` if needed (document why)

### IaC Validation Fails
- Check AWS credentials (for CDK synth)
- Verify Python/Terraform versions
- Review error messages for specific issues

---

## Adding New Tests

### Adding Unit Tests
1. Create test function in `app/tests/test_unit.py`
2. Use pytest fixtures for test client
3. Assert expected behavior
4. Run tests to verify

### Adding Load Test Scenarios
1. Create new JS file in `tests/load/`
2. Define k6 options (VUs, duration, thresholds)
3. Implement test logic
4. Document in this README

### Adding Security Checks
1. Update relevant config file (`.bandit`, `.checkov.yaml`, etc.)
2. Add to `run-security-tests.sh` if new tool
3. Document tool installation and usage

---

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [K6 Documentation](https://k6.io/docs/)
- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Checkov Documentation](https://www.checkov.io/)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [AWS CDK Testing](https://docs.aws.amazon.com/cdk/v2/guide/testing.html)
- [Terraform Testing](https://www.terraform.io/docs/language/modules/testing-experiment.html)
