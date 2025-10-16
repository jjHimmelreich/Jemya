#!/bin/bash
# Update IAM policy for GitHub Actions deployment user to support EC2 deployment

set -e

echo "🔧 Updating IAM policy for GitHub Actions deployment..."

# Configuration
POLICY_NAME="GitHubActionsDeploymentPolicy"
USER_NAME="jemya-github-actions"
POLICY_FILE="aws-deployment-policy.json"

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Get current account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📋 AWS Account: $ACCOUNT_ID"

# Check if policy file exists
if [ ! -f "$POLICY_FILE" ]; then
    echo "❌ Policy file $POLICY_FILE not found!"
    echo "💡 Make sure you're running this script from the aws/ directory"
    exit 1
fi

echo "📄 Policy file found: $POLICY_FILE"

# Get the policy ARN
POLICY_ARN="arn:aws:iam::$ACCOUNT_ID:policy/$POLICY_NAME"

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" > /dev/null 2>&1; then
    echo "📋 Policy exists. Getting current version..."
    
    # Create a new version of the policy
    echo "🔄 Creating new policy version..."
    NEW_VERSION=$(aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://"$POLICY_FILE" \
        --set-as-default \
        --query 'PolicyVersion.VersionId' \
        --output text)
    
    echo "✅ Policy updated successfully to version: $NEW_VERSION"
    
    # List all versions and delete old ones (keep only latest 5)
    echo "🧹 Cleaning up old policy versions..."
    aws iam list-policy-versions --policy-arn "$POLICY_ARN" \
        --query 'Versions[?IsDefaultVersion==`false`].VersionId' \
        --output text | tr '\t' '\n' | head -n -4 | while read version; do
        if [ ! -z "$version" ]; then
            echo "🗑️ Deleting old policy version: $version"
            aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$version" || true
        fi
    done
    
else
    echo "❌ Policy $POLICY_ARN not found!"
    echo "💡 Creating new policy..."
    
    # Create the policy
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://"$POLICY_FILE" \
        --description "GitHub Actions deployment policy for Jemya project with EC2 support"
    
    echo "✅ Policy created successfully: $POLICY_ARN"
    
    # Attach to user if exists
    if aws iam get-user --user-name "$USER_NAME" > /dev/null 2>&1; then
        echo "👤 Attaching policy to user: $USER_NAME"
        aws iam attach-user-policy \
            --user-name "$USER_NAME" \
            --policy-arn "$POLICY_ARN"
        echo "✅ Policy attached to user successfully"
    else
        echo "⚠️ User $USER_NAME not found. Please create the user first."
    fi
fi

# Verify the policy is attached to the user
echo "🔍 Verifying policy attachment..."
if aws iam list-attached-user-policies --user-name "$USER_NAME" --query "AttachedPolicies[?PolicyArn=='$POLICY_ARN']" --output text | grep -q "$POLICY_NAME"; then
    echo "✅ Policy is properly attached to user: $USER_NAME"
else
    echo "⚠️ Policy may not be attached to user. Attaching now..."
    aws iam attach-user-policy \
        --user-name "$USER_NAME" \
        --policy-arn "$POLICY_ARN"
    echo "✅ Policy attached successfully"
fi

echo ""
echo "🎉 IAM policy update completed!"
echo "📋 Summary:"
echo "   Policy: $POLICY_NAME"
echo "   ARN: $POLICY_ARN"
echo "   User: $USER_NAME"
echo ""
echo "🚀 GitHub Actions should now have the necessary EC2 permissions for deployment discovery."