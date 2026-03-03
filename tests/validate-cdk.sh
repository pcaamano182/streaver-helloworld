#!/bin/bash
# CDK validation script for Streaver Hello World
# Validates CDK configuration, runs synth, and executes unit tests

set -e

echo "========================================="
echo "AWS CDK Validation"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Navigate to CDK directory
cd infrastructure/cdk

echo "1. Installing Python dependencies..."
if pip install -q -r requirements.txt -r requirements-dev.txt; then
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${RED}✗ Failed to install dependencies${NC}"
    exit 1
fi
echo ""

echo "2. Running CDK unit tests..."
if pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✓ All CDK tests passed${NC}"
else
    echo -e "${RED}✗ CDK tests failed${NC}"
    exit 1
fi
echo ""

echo "3. Synthesizing CloudFormation templates..."
echo "   Environment: dev"
if ENVIRONMENT=dev python app.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CDK synth successful for dev${NC}"
else
    echo -e "${RED}✗ CDK synth failed for dev${NC}"
    exit 1
fi

echo "   Environment: cert"
if ENVIRONMENT=cert python app.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CDK synth successful for cert${NC}"
else
    echo -e "${RED}✗ CDK synth failed for cert${NC}"
    exit 1
fi

echo "   Environment: prod"
if ENVIRONMENT=prod python app.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ CDK synth successful for prod${NC}"
else
    echo -e "${RED}✗ CDK synth failed for prod${NC}"
    exit 1
fi
echo ""

echo "========================================="
echo -e "${GREEN}AWS CDK validation completed successfully!${NC}"
echo "========================================="
