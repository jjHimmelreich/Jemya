#!/bin/bash
# 🌟 Complete AWS Infrastructure Setup for Jemya
# 
# This master script verifies existing infrastructure and creates what's missing:
# 1. Checks/creates ECR repository 
# 2. Checks/creates deployment user and policies
# 3. Checks/creates EC2 instance with proper configuration
# 4. Provides complete GitHub secrets setup instructions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${CYAN}🌟 Complete AWS Infrastructure Setup for Jemya${NC}"
echo "================================================="
echo ""
echo "This script will verify and set up:"
echo "  🐳 ECR repository for Docker images"  
echo "  👤 IAM deployment user with proper policies"
echo "  🖥️ EC2 instance (t3.micro free tier)"
echo "  🛡️ Security groups and networking"
echo "  📋 GitHub secrets instructions"
echo ""

# Check prerequisites
echo -e "${BLUE}🔍 Checking Prerequisites${NC}"
echo "========================="

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found!${NC}"
    echo "Please install AWS CLI first"
    exit 1
fi
echo -e "${GREEN}✅ AWS CLI installed${NC}"

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured!${NC}"
    echo "Please configure AWS CLI first: aws configure"
    exit 1
fi

# Get current AWS identity
CURRENT_USER=$(aws sts get-caller-identity --query 'Arn' --output text)
echo -e "${GREEN}✅ AWS credentials configured: ${CURRENT_USER}${NC}"

read -p "Continue with infrastructure setup? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo ""
echo -e "${BLUE}🐳 Phase 1: ECR Repository${NC}"
echo "=========================="

# Check if ECR repository exists
ECR_REPO_URI=""
if aws ecr describe-repositories --repository-names jemya --region eu-west-1 &> /dev/null; then
    ECR_REPO_URI=$(aws ecr describe-repositories --repository-names jemya --region eu-west-1 --query 'repositories[0].repositoryUri' --output text)
    echo -e "${GREEN}✅ ECR repository already exists: ${ECR_REPO_URI}${NC}"
else
    echo -e "${YELLOW}🔨 Creating ECR repository...${NC}"
    if [ -f "./aws/create-deployment-user.sh" ]; then
        ./aws/create-deployment-user.sh
        ECR_REPO_URI=$(aws ecr describe-repositories --repository-names jemya --region eu-west-1 --query 'repositories[0].repositoryUri' --output text 2>/dev/null || echo "")
    else
        echo -e "${RED}❌ ECR setup script not found: aws/create-deployment-user.sh${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}👤 Phase 2: IAM Deployment User${NC}"
echo "==============================="

# Check if deployment user exists
DEPLOYMENT_USER="jemya-github-actions"
if aws iam get-user --user-name $DEPLOYMENT_USER &> /dev/null; then
    echo -e "${GREEN}✅ IAM deployment user already exists: ${DEPLOYMENT_USER}${NC}"
    
    # Check if user has access keys
    ACCESS_KEYS=$(aws iam list-access-keys --user-name $DEPLOYMENT_USER --query 'AccessKeyMetadata[?Status==`Active`].AccessKeyId' --output text)
    if [ -n "$ACCESS_KEYS" ]; then
        echo -e "${GREEN}✅ User has active access keys${NC}"
        EXISTING_ACCESS_KEY=$(echo $ACCESS_KEYS | cut -d' ' -f1)
        echo -e "${YELLOW}💡 Existing Access Key ID: ${EXISTING_ACCESS_KEY}${NC}"
    else
        echo -e "${YELLOW}⚠️ User exists but no active access keys found${NC}"
        echo -e "${YELLOW}🔨 You may need to create new access keys manually${NC}"
    fi
else
    echo -e "${YELLOW}🔨 IAM user will be created by ECR setup script${NC}"
fi

echo ""
echo -e "${BLUE}🖥️ Phase 3: EC2 Instance${NC}"
echo "========================"

# Check for existing EC2 instances
EXISTING_INSTANCES=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=jemya-instance" "Name=instance-state-name,Values=running,pending" \
    --query 'Reservations[*].Instances[*].[InstanceId,PublicIpAddress,State.Name]' \
    --output text \
    --region eu-west-1)

if [ -n "$EXISTING_INSTANCES" ]; then
    echo -e "${GREEN}✅ Found existing EC2 instance(s):${NC}"
    echo "$EXISTING_INSTANCES" | while read instance_id public_ip state; do
        echo -e "${GREEN}   Instance: ${instance_id} | IP: ${public_ip} | State: ${state}${NC}"
    done
    
    # Use the first running instance
    INSTANCE_ID=$(echo "$EXISTING_INSTANCES" | head -1 | cut -f1)
    PUBLIC_IP=$(echo "$EXISTING_INSTANCES" | head -1 | cut -f2)
    echo -e "${CYAN}🎯 Using instance: ${INSTANCE_ID} (${PUBLIC_IP})${NC}"
else
    echo -e "${YELLOW}🔨 No existing EC2 instance found. Creating new one...${NC}"
    if [ -f "./aws/create-ec2.sh" ]; then
        ./aws/create-ec2.sh
        # Get the created instance info
        INSTANCE_ID=$(tail -20 ec2-instance-info.txt | grep "INSTANCE_ID=" | cut -d'=' -f2)
        PUBLIC_IP=$(tail -20 ec2-instance-info.txt | grep "PUBLIC_IP=" | cut -d'=' -f2)
    else
        echo -e "${RED}❌ EC2 setup script not found: aws/create-ec2.sh${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}🛡️ Phase 4: Security Verification${NC}"
echo "================================="

# Check security groups
if [ -n "$INSTANCE_ID" ]; then
    SECURITY_GROUPS=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[*].GroupName' --output text --region eu-west-1)
    echo -e "${GREEN}✅ Security Groups: ${SECURITY_GROUPS}${NC}"
    
    # Check if instance is accessible
    echo -e "${YELLOW}🔌 Testing instance connectivity...${NC}"
    if ping -c 1 -W 3 $PUBLIC_IP &> /dev/null; then
        echo -e "${GREEN}✅ Instance is reachable${NC}"
    else
        echo -e "${YELLOW}⚠️ Instance might not be fully ready yet${NC}"
    fi
fi

echo ""
echo -e "${CYAN}🎉 Infrastructure Setup Complete!${NC}"
echo "=================================="
echo ""

# Create comprehensive summary
echo -e "${MAGENTA}📋 Infrastructure Summary${NC}"
echo "========================"
echo ""

if [ -n "$ECR_REPO_URI" ]; then
    echo -e "${GREEN}✅ ECR Repository:${NC}"
    echo "   URI: $ECR_REPO_URI"
    echo "   Region: eu-west-1"
    echo ""
fi

echo -e "${GREEN}✅ IAM Deployment User:${NC}"
echo "   Name: $DEPLOYMENT_USER"
if [ -n "$EXISTING_ACCESS_KEY" ]; then
    echo "   Access Key: $EXISTING_ACCESS_KEY"
fi
echo ""

if [ -n "$INSTANCE_ID" ] && [ -n "$PUBLIC_IP" ]; then
    echo -e "${GREEN}✅ EC2 Instance:${NC}"
    echo "   Instance ID: $INSTANCE_ID"
    echo "   Public IP: $PUBLIC_IP"
    echo "   Type: t3.micro (Free Tier)"
    echo "   Region: eu-west-1"
    echo ""
fi

echo -e "${MAGENTA}🔑 GitHub Secrets Setup${NC}"
echo "======================="
echo ""
echo "Add these secrets to your GitHub repository:"
echo -e "${BLUE}https://github.com/jjHimmelreich/Jemya/settings/secrets/actions${NC}"
echo ""

echo -e "${YELLOW}AWS Credentials:${NC}"
if [ -n "$EXISTING_ACCESS_KEY" ]; then
    echo "  AWS_ACCESS_KEY_ID: $EXISTING_ACCESS_KEY"
    echo "  AWS_SECRET_ACCESS_KEY: [Check your records or create new keys]"
else
    echo "  AWS_ACCESS_KEY_ID: [Get from create-deployment-user.sh output]"
    echo "  AWS_SECRET_ACCESS_KEY: [Get from create-deployment-user.sh output]"
fi
echo ""

if [ -n "$PUBLIC_IP" ]; then
    echo -e "${YELLOW}EC2 Configuration:${NC}"
    echo "  EC2_HOST: $PUBLIC_IP"
    echo "  EC2_SSH_KEY: [Content of ~/.ssh/jemya-key-$(date +%Y%m%d).pem]"
    echo ""
fi

echo -e "${YELLOW}Application Configuration:${NC}"
echo "  SPOTIFY_CLIENT_ID: [Your Spotify app client ID]"
echo "  SPOTIFY_CLIENT_SECRET: [Your Spotify app client secret]"
if [ -n "$PUBLIC_IP" ]; then
    echo "  SPOTIFY_REDIRECT_URI: http://$PUBLIC_IP/callback"
fi
echo "  OPENAI_API_KEY: [Your OpenAI API key]"
echo ""

echo -e "${MAGENTA}🚀 Next Steps${NC}"
echo "============="
echo ""
echo "1. 🔑 Add all GitHub secrets (listed above)"
echo ""
if [ -n "$PUBLIC_IP" ]; then
    echo "2. 🔧 Complete EC2 setup (if not done already):"
    echo "   ssh -i ~/.ssh/jemya-key-$(date +%Y%m%d).pem ec2-user@$PUBLIC_IP"
    echo "   curl -s https://raw.githubusercontent.com/jjHimmelreich/Jemya/main/aws/setup-ec2.sh | bash"
    echo ""
fi
echo "3. 🚀 Deploy your application:"
echo "   git push origin main"
echo ""
if [ -n "$PUBLIC_IP" ]; then
    echo "4. 🌐 Access your app:"
    echo -e "   ${GREEN}http://$PUBLIC_IP${NC}"
    echo ""
fi

echo -e "${MAGENTA}💰 Cost Summary${NC}"
echo "=============="
echo ""
echo "With AWS Free Tier:"
echo "✅ EC2 t3.micro: FREE (750 hours/month for 12 months)"
echo "✅ EBS Storage: FREE (30 GB for 12 months)"
echo "✅ ECR: FREE (500MB always free)"
echo "✅ Data Transfer: FREE (1GB/month)"
echo ""
echo -e "${GREEN}Total Monthly Cost: $0 (First 12 months)${NC}"
echo ""

echo -e "${CYAN}🎯 Your Jemya infrastructure is ready for deployment!${NC}"

# Save comprehensive setup info
cat > infrastructure-summary.txt << EOF
# Jemya Infrastructure Summary
# Generated: $(date)
# 
# This file contains all the information about your AWS infrastructure

## ECR Repository
ECR_REPOSITORY_URI=$ECR_REPO_URI

## IAM User
DEPLOYMENT_USER=$DEPLOYMENT_USER
DEPLOYMENT_USER_ACCESS_KEY=$EXISTING_ACCESS_KEY

## EC2 Instance
INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP
SSH_KEY_FILE=~/.ssh/jemya-key-$(date +%Y%m%d).pem

## GitHub Secrets Required
# AWS_ACCESS_KEY_ID=$EXISTING_ACCESS_KEY
# AWS_SECRET_ACCESS_KEY=[Your secret key]
# EC2_HOST=$PUBLIC_IP
# EC2_SSH_KEY=[Content of SSH key file above]
# SPOTIFY_CLIENT_ID=[Your Spotify client ID]
# SPOTIFY_CLIENT_SECRET=[Your Spotify client secret]
# SPOTIFY_REDIRECT_URI=http://$PUBLIC_IP/callback
# OPENAI_API_KEY=[Your OpenAI API key]

## Commands
# SSH to EC2: ssh -i ~/.ssh/jemya-key-$(date +%Y%m%d).pem ec2-user@$PUBLIC_IP
# App URL: http://$PUBLIC_IP
EOF

echo -e "${GREEN}💾 Complete setup info saved to: infrastructure-summary.txt${NC}"