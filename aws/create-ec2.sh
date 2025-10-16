#!/bin/bash
# 🚀 EC2 Instance Creation and Setup Script for Jemya
# 
# This script creates an EC2 instance and sets it up for Jemya deployment
# Run this on your LOCAL MACHINE (not on EC2)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 EC2 Instance Creation and Setup for Jemya${NC}"
echo "=============================================="
echo ""

# Configuration
AWS_REGION="eu-west-1"
INSTANCE_TYPE="t3.micro"
KEY_PAIR_NAME="jemya-key-$(date +%Y%m%d)"
SECURITY_GROUP_NAME="jemya-sg"
INSTANCE_NAME="jemya-instance"

echo -e "${YELLOW}📋 Configuration:${NC}"
echo "   Region: $AWS_REGION"
echo "   Instance Type: $INSTANCE_TYPE (Free Tier)"
echo "   Key Pair: $KEY_PAIR_NAME"
echo "   Security Group: $SECURITY_GROUP_NAME"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found!${NC}"
    echo "Please install AWS CLI first"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured!${NC}"
    echo "Please configure AWS CLI first: aws configure"
    exit 1
fi

echo -e "${GREEN}✅ AWS CLI configured${NC}"

# Get latest Amazon Linux 2 AMI
echo -e "${YELLOW}🔍 Finding latest Amazon Linux 2 AMI...${NC}"
AMI_ID=$(aws ec2 describe-images \
    --owners amazon \
    --filters "Name=name,Values=amzn2-ami-hvm-*-x86_64-gp2" \
              "Name=state,Values=available" \
    --query 'Images | sort_by(@, &CreationDate) | [-1].ImageId' \
    --output text \
    --region $AWS_REGION)

echo "   AMI ID: $AMI_ID"

# Create key pair
echo -e "${YELLOW}🔑 Creating EC2 key pair...${NC}"
if aws ec2 describe-key-pairs --key-names $KEY_PAIR_NAME --region $AWS_REGION &> /dev/null; then
    echo "   Key pair '$KEY_PAIR_NAME' already exists"
else
    mkdir -p ~/.ssh
    aws ec2 create-key-pair \
        --key-name $KEY_PAIR_NAME \
        --query 'KeyMaterial' \
        --output text \
        --region $AWS_REGION > ~/.ssh/$KEY_PAIR_NAME.pem
    
    chmod 600 ~/.ssh/$KEY_PAIR_NAME.pem
    echo -e "${GREEN}   ✅ Key pair created: ~/.ssh/$KEY_PAIR_NAME.pem${NC}"
fi

# Get default VPC
echo -e "${YELLOW}🌐 Getting default VPC...${NC}"
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=is-default,Values=true" \
    --query 'Vpcs[0].VpcId' \
    --output text \
    --region $AWS_REGION)

echo "   VPC ID: $VPC_ID"

# Create security group
echo -e "${YELLOW}🛡️ Creating security group...${NC}"
if aws ec2 describe-security-groups --group-names $SECURITY_GROUP_NAME --region $AWS_REGION &> /dev/null; then
    echo "   Security group '$SECURITY_GROUP_NAME' already exists"
    SECURITY_GROUP_ID=$(aws ec2 describe-security-groups \
        --group-names $SECURITY_GROUP_NAME \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region $AWS_REGION)
else
    SECURITY_GROUP_ID=$(aws ec2 create-security-group \
        --group-name $SECURITY_GROUP_NAME \
        --description "Security group for Jemya application" \
        --vpc-id $VPC_ID \
        --query 'GroupId' \
        --output text \
        --region $AWS_REGION)
    
    echo -e "${GREEN}   ✅ Security group created: $SECURITY_GROUP_ID${NC}"
    
    # Add security group rules
    echo -e "${YELLOW}🔓 Adding security group rules...${NC}"
    
    # SSH access (port 22) - restrict to your IP
    MY_IP=$(curl -s https://checkip.amazonaws.com)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 22 \
        --cidr $MY_IP/32 \
        --region $AWS_REGION
    echo "   ✅ SSH (22) from your IP: $MY_IP"
    
    # HTTP access (port 80)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 80 \
        --cidr 0.0.0.0/0 \
        --region $AWS_REGION
    echo "   ✅ HTTP (80) from anywhere"
    
    # HTTPS access (port 443)
    aws ec2 authorize-security-group-ingress \
        --group-id $SECURITY_GROUP_ID \
        --protocol tcp \
        --port 443 \
        --cidr 0.0.0.0/0 \
        --region $AWS_REGION
    echo "   ✅ HTTPS (443) from anywhere"
fi

# Check for existing instances
echo -e "${YELLOW}🔍 Checking for existing instances...${NC}"
EXISTING_INSTANCE=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=$INSTANCE_NAME" "Name=instance-state-name,Values=running,pending" \
    --query 'Reservations[0].Instances[0].InstanceId' \
    --output text \
    --region $AWS_REGION 2>/dev/null)

if [ "$EXISTING_INSTANCE" != "None" ] && [ "$EXISTING_INSTANCE" != "" ]; then
    echo -e "${YELLOW}   ⚠️ Found existing instance: $EXISTING_INSTANCE${NC}"
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids $EXISTING_INSTANCE \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text \
        --region $AWS_REGION)
    echo -e "${GREEN}   ✅ Using existing instance at $PUBLIC_IP${NC}"
    INSTANCE_ID=$EXISTING_INSTANCE
else
    # Launch EC2 instance
    echo -e "${YELLOW}🖥️ Launching new EC2 instance...${NC}"
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --count 1 \
    --instance-type $INSTANCE_TYPE \
    --key-name $KEY_PAIR_NAME \
    --security-group-ids $SECURITY_GROUP_ID \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
    --query 'Instances[0].InstanceId' \
    --output text \
    --region $AWS_REGION)

    echo -e "${GREEN}   ✅ EC2 instance launched: $INSTANCE_ID${NC}"

    # Wait for instance to be running
    echo -e "${YELLOW}⏳ Waiting for instance to be running...${NC}"
    aws ec2 wait instance-running --instance-ids $INSTANCE_ID --region $AWS_REGION

    # Get public IP
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids $INSTANCE_ID \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text \
        --region $AWS_REGION)
fi

echo -e "${GREEN}🌐 Instance is running!${NC}"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"

# Create summary
echo ""
echo -e "${BLUE}📋 EC2 Instance Summary${NC}"
echo "========================"
echo ""
echo -e "${GREEN}✅ Instance Details:${NC}"
echo "   Instance ID: $INSTANCE_ID"
echo "   Public IP: $PUBLIC_IP"
echo "   Instance Type: $INSTANCE_TYPE"
echo "   Region: $AWS_REGION"
echo ""
echo -e "${GREEN}✅ Connection Info:${NC}"
echo "   SSH Key: ~/.ssh/$KEY_PAIR_NAME.pem"
echo "   SSH Command: ssh -i ~/.ssh/$KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP"
echo ""

# GitHub Secrets information
echo -e "${BLUE}🔑 GitHub Secrets Setup${NC}"
echo "======================="
echo ""
echo "Add these secrets to your GitHub repository:"
echo "https://github.com/jjHimmelreich/Jemya/settings/secrets/actions"
echo ""
echo -e "${YELLOW}EC2_HOST:${NC}"
echo "$PUBLIC_IP"
echo ""
echo -e "${YELLOW}EC2_SSH_KEY:${NC}"
echo "Copy the content of: ~/.ssh/$KEY_PAIR_NAME.pem"
echo ""
echo "To copy the private key:"
echo -e "${BLUE}cat ~/.ssh/$KEY_PAIR_NAME.pem${NC}"
echo ""

# Save instance info to file
cat > ec2-instance-info.txt << EOF
# Jemya EC2 Instance Information
# Generated: $(date)

INSTANCE_ID=$INSTANCE_ID
PUBLIC_IP=$PUBLIC_IP
KEY_PAIR_NAME=$KEY_PAIR_NAME
SECURITY_GROUP_ID=$SECURITY_GROUP_ID
AWS_REGION=$AWS_REGION

# SSH Command:
ssh -i ~/.ssh/$KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP

# GitHub Secrets:
# EC2_HOST: $PUBLIC_IP
# EC2_SSH_KEY: Content of ~/.ssh/$KEY_PAIR_NAME.pem

# App URL:
# http://$PUBLIC_IP
EOF

echo -e "${GREEN}💾 Instance info saved to: ec2-instance-info.txt${NC}"
echo ""
echo -e "${GREEN}🎉 EC2 instance created successfully!${NC}"
echo ""
echo -e "${YELLOW}🔧 Next Steps:${NC}"
echo "1. SSH to EC2: ssh -i ~/.ssh/$KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP"
echo "2. Run setup on EC2: curl -s https://raw.githubusercontent.com/jjHimmelreich/Jemya/main/aws/setup-ec2.sh | bash"
echo "3. Add GitHub secrets (EC2_HOST and EC2_SSH_KEY)"
echo "4. Push code to trigger deployment"