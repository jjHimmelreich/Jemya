#!/bin/bash
# Complete infrastructure setup script for Jemya deployment
# This script sets up all AWS resources needed for the application

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
    exit 1
}

# Configuration
PROJECT_NAME="jemya"
AWS_REGION=${AWS_REGION:-"eu-west-1"}
INSTANCE_TYPE=${INSTANCE_TYPE:-"t3.small"}
KEY_PAIR_NAME=${KEY_PAIR_NAME:-"jemya-key-20251016"}

log "🏗️ Setting up complete infrastructure for Jemya deployment..."
echo ""
echo "Configuration:"
echo "- Project: $PROJECT_NAME"
echo "- Region: $AWS_REGION"
echo "- Instance Type: $INSTANCE_TYPE"
echo "- Key Pair: $KEY_PAIR_NAME"
echo ""

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
log "📋 AWS Account ID: $AWS_ACCOUNT_ID"

# 1. Create ECR Repository
log "📦 Creating ECR repository..."
if aws ecr describe-repositories --repository-names $PROJECT_NAME --region $AWS_REGION &>/dev/null; then
    warning "ECR repository $PROJECT_NAME already exists"
else
    aws ecr create-repository \
        --repository-name $PROJECT_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256
    success "ECR repository created"
fi

# Get ECR URI
ECR_URI=$(aws ecr describe-repositories --repository-names $PROJECT_NAME --region $AWS_REGION --query 'repositories[0].repositoryUri' --output text)
log "📦 ECR URI: $ECR_URI"

# 2. Create IAM Role for EC2 Instance (Session Manager)
log "👤 Creating IAM role for EC2 instance..."
ROLE_NAME="${PROJECT_NAME^}EC2SessionManagerRole"
PROFILE_NAME="${PROJECT_NAME^}EC2SessionManagerProfile"

# Create trust policy
cat > /tmp/ec2-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role if it doesn't exist
if aws iam get-role --role-name $ROLE_NAME &>/dev/null; then
    warning "IAM role $ROLE_NAME already exists"
else
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/ec2-trust-policy.json
    success "IAM role $ROLE_NAME created"
fi

# Attach Session Manager policy
aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore 2>/dev/null || true

# Create custom policy for ECR access
cat > /tmp/ec2-ecr-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
EOF

# Create and attach ECR policy
ECR_POLICY_NAME="${PROJECT_NAME^}EC2ECRAccess"
if aws iam get-policy --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/$ECR_POLICY_NAME &>/dev/null; then
    warning "ECR policy already exists"
else
    aws iam create-policy \
        --policy-name $ECR_POLICY_NAME \
        --policy-document file:///tmp/ec2-ecr-policy.json
    success "ECR policy created"
fi

aws iam attach-role-policy \
    --role-name $ROLE_NAME \
    --policy-arn arn:aws:iam::${AWS_ACCOUNT_ID}:policy/$ECR_POLICY_NAME 2>/dev/null || true

# Create instance profile
if aws iam get-instance-profile --instance-profile-name $PROFILE_NAME &>/dev/null; then
    warning "Instance profile $PROFILE_NAME already exists"
else
    aws iam create-instance-profile --instance-profile-name $PROFILE_NAME
    success "Instance profile created"
fi

# Add role to instance profile
aws iam add-role-to-instance-profile \
    --instance-profile-name $PROFILE_NAME \
    --role-name $ROLE_NAME 2>/dev/null || true

success "IAM role and instance profile configured"

echo ""
echo "🎉 Infrastructure setup completed!"
echo ""
echo "📋 Setup Summary:"
echo "=================="
echo "✅ ECR Repository: $ECR_URI"
echo "✅ IAM Role: $ROLE_NAME"
echo "✅ Instance Profile: $PROFILE_NAME"
echo ""
echo "🔑 Next Steps:"
echo "=============="
echo "1. Use existing EC2 instance or create new one with this instance profile"
echo "2. Run the EC2 setup script on your instance"
echo "3. Deploy your application"
echo ""
echo "🚀 Infrastructure components are ready!"