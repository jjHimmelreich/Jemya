#!/bin/bash
# SSH connectivity test script

set -e

INSTANCE_ID="i-01a86512741d7221f"
KEY_FILE="~/.ssh/jemya-key-20251016.pem"

echo "🔍 SSH Connectivity Test for Jemya EC2 Instance"
echo "==============================================="
echo ""

# Get instance details
echo "📋 Getting instance information..."
INSTANCE_INFO=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress,PublicDnsName,KeyName]' --output text)
STATE=$(echo $INSTANCE_INFO | cut -f1)
PUBLIC_IP=$(echo $INSTANCE_INFO | cut -f2)
PUBLIC_DNS=$(echo $INSTANCE_INFO | cut -f3)
KEY_NAME=$(echo $INSTANCE_INFO | cut -f4)

echo "   Instance ID: $INSTANCE_ID"
echo "   State: $STATE"
echo "   Public IP: $PUBLIC_IP"
echo "   Public DNS: $PUBLIC_DNS"
echo "   Key Pair: $KEY_NAME"
echo ""

# Check if instance is running
if [ "$STATE" != "running" ]; then
    echo "❌ Instance is not running (State: $STATE)"
    exit 1
fi

echo "✅ Instance is running"
echo ""

# Test network connectivity
echo "🌐 Testing network connectivity..."
if ping -c 3 -W 3000 $PUBLIC_IP > /dev/null 2>&1; then
    echo "✅ Ping successful"
else
    echo "❌ Ping failed - network connectivity issue"
    echo "💡 This could indicate VPC/subnet routing problems"
fi
echo ""

# Test port 22 connectivity
echo "🔌 Testing SSH port (22) connectivity..."
if timeout 10 bash -c "</dev/tcp/$PUBLIC_IP/22" 2>/dev/null; then
    echo "✅ Port 22 is open and accepting connections"
else
    echo "❌ Port 22 is not accessible"
    echo "💡 SSH service may not be running or security group blocks access"
fi
echo ""

# Check security group rules
echo "🔒 Checking security group rules..."
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
SSH_RULES=$(aws ec2 describe-security-groups --group-ids $SG_ID --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`].IpRanges[*].CidrIp' --output text)

echo "   Security Group: $SG_ID"
echo "   SSH Rules: $SSH_RULES"

if echo "$SSH_RULES" | grep -q "0.0.0.0/0"; then
    echo "✅ SSH access allowed from anywhere (0.0.0.0/0)"
else
    echo "⚠️  SSH access limited to specific IPs: $SSH_RULES"
fi
echo ""

# Test SSH key
echo "🔑 Checking SSH key..."
if [ -f ~/.ssh/jemya-key-20251016.pem ]; then
    KEY_PERMS=$(ls -la ~/.ssh/jemya-key-20251016.pem | cut -d' ' -f1)
    echo "✅ SSH key exists: ~/.ssh/jemya-key-20251016.pem"
    echo "   Permissions: $KEY_PERMS"
    
    if [ "$KEY_PERMS" = "-rw-------" ]; then
        echo "✅ Key permissions are correct"
    else
        echo "⚠️  Key permissions should be 600 (rw------)"
    fi
else
    echo "❌ SSH key not found: ~/.ssh/jemya-key-20251016.pem"
    exit 1
fi
echo ""

# Attempt SSH connection
echo "🔐 Testing SSH connection..."
echo "Command: ssh -i ~/.ssh/jemya-key-20251016.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP"
echo ""

if ssh -i ~/.ssh/jemya-key-20251016.pem -o ConnectTimeout=10 -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "echo 'SSH connection successful!'" 2>/dev/null; then
    echo "🎉 SSH connection successful!"
    echo ""
    echo "📊 System info from EC2:"
    ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no ec2-user@$PUBLIC_IP "
        echo '  - Hostname: \$(hostname)'
        echo '  - Uptime: \$(uptime -p)'
        echo '  - SSH service: \$(systemctl is-active sshd)'
        echo '  - Docker: \$(command -v docker > /dev/null && echo \"installed\" || echo \"not installed\")'
    " 2>/dev/null
else
    echo "❌ SSH connection failed"
    echo ""
    echo "🔧 Troubleshooting steps:"
    echo "1. Check if SSH service is running on the instance"
    echo "2. Verify the instance has a public IP and internet gateway"
    echo "3. Ensure the security group allows SSH (port 22) from your IP"
    echo "4. Try connecting via AWS Session Manager if available"
    echo "5. Check VPC route tables and NACLs"
    echo ""
    echo "🚀 Quick fix attempt: Restart the instance"
    echo "   aws ec2 reboot-instances --instance-ids $INSTANCE_ID"
fi