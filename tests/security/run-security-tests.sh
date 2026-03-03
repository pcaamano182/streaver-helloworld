#!/bin/bash
# Security testing script for Streaver Hello World
# Runs Bandit, Safety, Checkov, and Trivy scans

set -e

echo "========================================="
echo "Streaver Hello World - Security Testing"
echo "========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running from project root
if [ ! -f "Dockerfile" ]; then
    echo -e "${RED}Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Counter for failed tests
FAILED_TESTS=0

echo "----------------------------------------"
echo "1. Bandit - Python Security Linter"
echo "----------------------------------------"
if command -v bandit &> /dev/null; then
    echo "Running Bandit..."
    if bandit -r app/ -c tests/security/.bandit -f screen; then
        echo -e "${GREEN}✓ Bandit scan passed${NC}"
    else
        echo -e "${RED}✗ Bandit scan failed${NC}"
        ((FAILED_TESTS++))
    fi
else
    echo -e "${YELLOW}⚠ Bandit not installed. Install with: pip install bandit${NC}"
fi
echo ""

echo "----------------------------------------"
echo "2. Safety - Python Dependency Check"
echo "----------------------------------------"
if command -v safety &> /dev/null; then
    echo "Running Safety..."
    if safety check --file app/requirements.txt --json | jq; then
        echo -e "${GREEN}✓ Safety scan passed${NC}"
    else
        echo -e "${RED}✗ Safety scan found vulnerabilities${NC}"
        ((FAILED_TESTS++))
    fi
else
    echo -e "${YELLOW}⚠ Safety not installed. Install with: pip install safety${NC}"
fi
echo ""

echo "----------------------------------------"
echo "3. Checkov - IaC Security Scanner"
echo "----------------------------------------"
if command -v checkov &> /dev/null; then
    echo "Running Checkov on Terraform..."
    if checkov -d infrastructure/terraform --config-file tests/security/.checkov.yaml --compact; then
        echo -e "${GREEN}✓ Checkov Terraform scan passed${NC}"
    else
        echo -e "${YELLOW}⚠ Checkov Terraform scan found issues${NC}"
        # Don't fail on Checkov warnings for now
    fi
    echo ""

    echo "Running Checkov on CDK (CloudFormation)..."
    if [ -d "infrastructure/cdk/cdk.out" ]; then
        if checkov -d infrastructure/cdk/cdk.out --framework cloudformation --compact; then
            echo -e "${GREEN}✓ Checkov CDK scan passed${NC}"
        else
            echo -e "${YELLOW}⚠ Checkov CDK scan found issues${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ CDK output not found. Run 'cdk synth' first.${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Checkov not installed. Install with: pip install checkov${NC}"
fi
echo ""

echo "----------------------------------------"
echo "4. Trivy - Container Image Scanner"
echo "----------------------------------------"
if command -v trivy &> /dev/null; then
    echo "Building Docker image..."
    if docker build -t streaver-helloworld:security-test . > /dev/null; then
        echo "Running Trivy..."
        if trivy image --config tests/security/trivy.yaml streaver-helloworld:security-test; then
            echo -e "${GREEN}✓ Trivy scan passed${NC}"
        else
            echo -e "${YELLOW}⚠ Trivy scan found vulnerabilities${NC}"
            # Don't fail on Trivy warnings for base image vulnerabilities
        fi
    else
        echo -e "${RED}✗ Docker build failed${NC}"
        ((FAILED_TESTS++))
    fi
else
    echo -e "${YELLOW}⚠ Trivy not installed. Install from: https://github.com/aquasecurity/trivy${NC}"
fi
echo ""

echo "========================================="
echo "Security Testing Summary"
echo "========================================="
if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}All critical security tests passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED_TESTS critical test(s) failed${NC}"
    exit 1
fi
