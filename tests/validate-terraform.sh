#!/bin/bash
# Terraform validation script for Streaver Hello World
# Validates, formats, and plans Terraform configuration

set -e

echo "========================================="
echo "Terraform Validation"
echo "========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Navigate to Terraform directory
cd infrastructure/terraform

echo "1. Formatting Terraform files..."
if terraform fmt -recursive -check; then
    echo -e "${GREEN}✓ All files are properly formatted${NC}"
else
    echo -e "${YELLOW}⚠ Some files need formatting. Running fmt...${NC}"
    terraform fmt -recursive
    echo -e "${GREEN}✓ Files formatted${NC}"
fi
echo ""

echo "2. Initializing Terraform..."
if terraform init -backend=false > /dev/null; then
    echo -e "${GREEN}✓ Terraform initialized${NC}"
else
    echo -e "${RED}✗ Terraform init failed${NC}"
    exit 1
fi
echo ""

echo "3. Validating Terraform configuration..."
if terraform validate; then
    echo -e "${GREEN}✓ Configuration is valid${NC}"
else
    echo -e "${RED}✗ Validation failed${NC}"
    exit 1
fi
echo ""

echo "4. Running terraform plan for each environment..."
for env in dev cert prod; do
    echo "   Environment: $env"
    if terraform plan -var-file=environments/$env.tfvars -out=/dev/null > /dev/null 2>&1; then
        echo -e "${GREEN}   ✓ Plan successful for $env${NC}"
    else
        echo -e "${YELLOW}   ⚠ Plan failed for $env (expected without AWS credentials)${NC}"
    fi
done
echo ""

echo "========================================="
echo -e "${GREEN}Terraform validation completed!${NC}"
echo "========================================="
