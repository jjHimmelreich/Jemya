#!/bin/bash
# 🔒 Assign Elastic IP to EC2 Instance for Static IP Address

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔒 Setting up Elastic IP for Jemya EC2 Instance${NC}"
echo "=============================================="

INSTANCE_ID="i-01a86512741d7221f"
AWS_REGION="eu-west-1"

echo -e "${YELLOW}📍 Current instance: ${INSTANCE_ID}${NC}"

# Check if instance already has an Elastic IP
CURRENT_EIP=$(aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text \
    --region $AWS_REGION)

echo "Current IP: $CURRENT_EIP"

# Allocate new Elastic IP
echo -e "${YELLOW}🔨 Allocating Elastic IP...${NC}"
ALLOCATION_ID=$(aws ec2 allocate-address \
    --domain vpc \
    --query 'AllocationId' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}✅ Elastic IP allocated: ${ALLOCATION_ID}${NC}"

# Get the Elastic IP address
ELASTIC_IP=$(aws ec2 describe-addresses \
    --allocation-ids $ALLOCATION_ID \
    --query 'Addresses[0].PublicIp' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}📍 Elastic IP: ${ELASTIC_IP}${NC}"

# Associate Elastic IP with instance
echo -e "${YELLOW}🔗 Associating Elastic IP with instance...${NC}"
ASSOCIATION_ID=$(aws ec2 associate-address \
    --instance-id $INSTANCE_ID \
    --allocation-id $ALLOCATION_ID \
    --query 'AssociationId' \
    --output text \
    --region $AWS_REGION)

echo -e "${GREEN}✅ Elastic IP associated: ${ASSOCIATION_ID}${NC}"

echo ""
echo -e "${BLUE}🎉 Elastic IP Setup Complete!${NC}"
echo "================================"
echo ""
echo -e "${GREEN}✅ Static IP Address: ${ELASTIC_IP}${NC}"
echo -e "${GREEN}✅ Never changes (even if instance restarts)${NC}"
echo -e "${GREEN}✅ Production-ready setup${NC}"
echo ""

echo -e "${YELLOW}📋 Update your GitHub secrets:${NC}"
echo "EC2_HOST: $ELASTIC_IP"
echo ""

echo -e "${YELLOW}🌐 Your app will always be available at:${NC}"
echo -e "${GREEN}http://$ELASTIC_IP${NC}"
echo ""

# Update callback URL
echo -e "${YELLOW}📝 Update your Spotify callback URL to:${NC}"
echo "http://$ELASTIC_IP/callback"
echo ""

# Save updated info
cat > ec2-elastic-ip-info.txt << EOF
# Jemya EC2 Elastic IP Configuration
# Generated: $(date)

INSTANCE_ID=$INSTANCE_ID
ELASTIC_IP=$ELASTIC_IP
ALLOCATION_ID=$ALLOCATION_ID
ASSOCIATION_ID=$ASSOCIATION_ID

# This IP is now STATIC and will never change
# Update GitHub secrets:
# EC2_HOST: $ELASTIC_IP

# App URL: http://$ELASTIC_IP
# Spotify Callback: http://$ELASTIC_IP/callback
EOF

echo -e "${GREEN}💾 Configuration saved to: ec2-elastic-ip-info.txt${NC}"

echo ""
echo -e "${BLUE}💰 Cost Impact:${NC}"
echo "• Elastic IP: FREE while associated with running instance"
echo "• Elastic IP: ~$0.005/hour (~$3.60/month) if instance stopped"
echo "• Recommendation: Keep instance running or release EIP when not needed"