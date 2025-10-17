#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 AWS Policy Status Check${NC}"
echo "=========================="
echo ""

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$ACCOUNT_ID" ]; then
    echo -e "${RED}❌ Failed to get AWS account ID. Check your credentials.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ AWS Account ID: ${ACCOUNT_ID}${NC}"
echo ""

# Function to check policy status
check_policy() {
    local policy_name=$1
    local expected_file=$2
    
    local policy_arn="arn:aws:iam::${ACCOUNT_ID}:policy/${policy_name}"
    
    echo -e "${YELLOW}🔍 Checking: ${policy_name}${NC}"
    
    if aws iam get-policy --policy-arn "$policy_arn" &>/dev/null; then
        # Policy exists - check if it matches our file
        local version_id=$(aws iam get-policy --policy-arn "$policy_arn" --query 'Policy.DefaultVersionId' --output text)
        local creation_date=$(aws iam get-policy --policy-arn "$policy_arn" --query 'Policy.CreateDate' --output text)
        local update_date=$(aws iam get-policy --policy-arn "$policy_arn" --query 'Policy.UpdateDate' --output text)
        
        echo -e "${GREEN}   ✅ EXISTS${NC}"
        echo "   📅 Created: $creation_date"
        echo "   🔄 Updated: $update_date"
        echo "   📝 Version: $version_id"
        
        # Get current policy document
        current_policy=$(aws iam get-policy-version --policy-arn "$policy_arn" --version-id "$version_id" --query 'PolicyVersion.Document' --output text)
        
        # Compare with expected (this is simplified - real comparison would need JSON normalization)
        if [ -f "$expected_file" ]; then
            echo "   📄 Expected file: $(basename $expected_file)"
            echo -e "${YELLOW}   ⚠️  Run update-policies.sh to ensure latest security improvements${NC}"
        else
            echo -e "${RED}   ❌ Expected file not found: $expected_file${NC}"
        fi
        
    else
        echo -e "${RED}   ❌ NOT FOUND${NC}"
        if [ -f "$expected_file" ]; then
            echo -e "${YELLOW}   💡 Run update-policies.sh to create with file: $(basename $expected_file)${NC}"
        fi
    fi
    echo ""
}

# Check GitHub Actions user
echo -e "${BLUE}👤 GitHub Actions User Policies${NC}"
echo "--------------------------------"

check_policy "JemyaGitHubActionsECRPolicy" "./aws/github-actions-user-ecr-policy.json"
check_policy "JemyaGitHubActionsAWSPolicy" "./aws/github-actions-user-aws-deployment-policy.json"

# Check for old policies that might need cleanup
echo -e "${BLUE}🧹 Legacy Policies (might need cleanup)${NC}"
echo "---------------------------------------"

legacy_policies=("JemyaECRAccess" "JemyaEC2ECRAccess" "JemyaGitHubActionsECRAccess" "JemyaDeploymentPolicy" "JemyaAdminUserPolicy")

for policy_name in "${legacy_policies[@]}"; do
    policy_arn="arn:aws:iam::${ACCOUNT_ID}:policy/${policy_name}"
    if aws iam get-policy --policy-arn "$policy_arn" &>/dev/null; then
        echo -e "${YELLOW}   ⚠️  LEGACY FOUND: ${policy_name}${NC}"
        echo "      💡 Consider removing after confirming new policies work"
    fi
done

echo ""
echo -e "${BLUE}🎯 Recommendations${NC}"
echo "==================="
echo "1. 🔄 Run './aws/update-policies.sh' to apply latest secure policies"
echo "2. 🧪 Test deployment workflow to ensure everything works"
echo "3. 🧹 Run './aws/cleanup-infrastructure.sh' to remove legacy policies"
echo "4. 👀 Monitor CloudTrail for any permission denials"