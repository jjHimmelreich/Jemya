#!/bin/bash
# 🔐 Create AWS IAM User for GitHub Actions Deployment

set -e

echo "🔐 Creating dedicated AWS IAM user for GitHub Actions deployment..."

# Variables
DEPLOYMENT_USER="jemya-github-actions"
POLICY_NAME="JemyaDeploymentPolicy"
POLICY_FILE="aws-deployment-policy.json"

# 1. Create IAM user
echo "👤 Creating IAM user: $DEPLOYMENT_USER"
aws iam create-user \
    --profile jemya \
    --user-name $DEPLOYMENT_USER \
    --tags Key=Purpose,Value=GitHubActions Key=Application,Value=Jemya \
    || echo "User might already exist"

# 2. Create custom policy
echo "📋 Creating deployment policy: $POLICY_NAME"
POLICY_ARN=$(aws iam create-policy \
    --profile jemya \
    --policy-name $POLICY_NAME \
    --policy-document file://$POLICY_FILE \
    --description "Minimal permissions for Jemya GitHub Actions deployment" \
    --query 'Policy.Arn' \
    --output text 2>/dev/null || \
    aws iam get-policy \
        --profile jemya \
        --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --profile jemya --query Account --output text):policy/$POLICY_NAME" \
        --query 'Policy.Arn' \
        --output text)

echo "✅ Policy ARN: $POLICY_ARN"

# 3. Attach policy to user
echo "🔗 Attaching policy to user..."
aws iam attach-user-policy \
    --profile jemya \
    --user-name $DEPLOYMENT_USER \
    --policy-arn $POLICY_ARN

# 4. Create access keys
echo "🔑 Creating access keys..."
ACCESS_KEY_OUTPUT=$(aws iam create-access-key \
    --profile jemya \
    --user-name $DEPLOYMENT_USER \
    --output json)

ACCESS_KEY_ID=$(echo $ACCESS_KEY_OUTPUT | jq -r '.AccessKey.AccessKeyId')
SECRET_ACCESS_KEY=$(echo $ACCESS_KEY_OUTPUT | jq -r '.AccessKey.SecretAccessKey')

# 5. Display results
echo ""
echo "✅ IAM User Setup Complete!"
echo "=========================="
echo ""
echo "👤 User: $DEPLOYMENT_USER"
echo "📋 Policy: $POLICY_NAME"
echo "🔑 Access Key ID: $ACCESS_KEY_ID"
echo "🔐 Secret Access Key: $SECRET_ACCESS_KEY"
echo ""
echo "🔐 GitHub Secrets to Add:"
echo "========================"
echo "AWS_ACCESS_KEY_ID: $ACCESS_KEY_ID"
echo "AWS_SECRET_ACCESS_KEY: $SECRET_ACCESS_KEY"
echo "AWS_REGION: $(aws configure get region || echo 'us-east-1')"
echo ""
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "- Save these credentials securely"
echo "- Add them to GitHub Secrets immediately"
echo "- Never commit these to code"
echo "- The secret access key won't be shown again"
echo ""
echo "🛡️  Security Features:"
echo "- ✅ Minimal permissions (ECR, App Runner only)"
echo "- ✅ Resource-specific restrictions"
echo "- ✅ No admin or broad permissions"
echo "- ✅ Scoped to Jemya application only"
echo ""
echo "📋 Next Steps:"
echo "1. Copy the credentials above to GitHub Secrets"
echo "2. Test deployment with a small change"
echo "3. Monitor AWS CloudTrail for user activity"
echo "4. Rotate keys regularly (every 90 days recommended)"