#!/bin/bash
# Test SSH deployment to EC2 instance

set -e

INSTANCE_ID="i-01a86512741d7221f"
PUBLIC_IP="34.253.128.224"
KEY_FILE="~/.ssh/jemya-key-20251016.pem"

echo "🚀 Testing SSH Deployment to EC2 Instance"
echo "=========================================="
echo "Instance: $INSTANCE_ID"
echo "IP: $PUBLIC_IP"
echo ""

# Test 1: Basic SSH connectivity
echo "📋 Test 1: Basic SSH connectivity"
ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@$PUBLIC_IP << 'EOF'
echo "SSH connection established"
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Uptime: $(uptime)"
exit 0
EOF
echo ""

# Test 2: Check if Docker is installed
echo "📋 Test 2: Docker availability"
ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@$PUBLIC_IP << 'EOF'
if command -v docker > /dev/null; then
    echo "Docker is installed"
    docker --version
    sudo systemctl status docker --no-pager -l | head -3
else
    echo "Docker is not installed"
fi
exit 0
EOF
echo ""

# Test 3: Check AWS CLI access
echo "📋 Test 3: AWS CLI availability"
ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@$PUBLIC_IP << 'EOF'
if command -v aws > /dev/null; then
    echo "AWS CLI is installed"
    aws --version
else
    echo "AWS CLI is not installed"
fi
exit 0
EOF
echo ""

# Test 4: Test file upload via SCP
echo "📋 Test 4: File transfer via SCP"
echo "echo 'Test deployment script'" > /tmp/test_deploy.sh
chmod +x /tmp/test_deploy.sh

scp -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 /tmp/test_deploy.sh ec2-user@$PUBLIC_IP:/tmp/

ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@$PUBLIC_IP << 'EOF'
if [ -f /tmp/test_deploy.sh ]; then
    echo "File transfer successful"
    echo "File contents:"
    cat /tmp/test_deploy.sh
    rm -f /tmp/test_deploy.sh
else
    echo "File transfer failed"
fi
exit 0
EOF

rm -f /tmp/test_deploy.sh
echo ""

# Test 5: Simulate deployment process
echo "📋 Test 5: Simulate deployment process"
cat > /tmp/deploy_simulation.sh << 'DEPLOY_EOF'
#!/bin/bash
set -e
echo "🚀 Simulating deployment process..."

# Check if ECR login would work (without actual login)
echo "Step 1: ECR login simulation"
if command -v aws > /dev/null; then
    echo "✅ AWS CLI available for ECR login"
else
    echo "❌ AWS CLI not available"
fi

# Check Docker daemon
echo "Step 2: Docker daemon check"
if sudo systemctl is-active docker > /dev/null 2>&1; then
    echo "✅ Docker daemon is running"
else
    echo "❌ Docker daemon is not running"
fi

# Check for existing container
echo "Step 3: Check for existing jemya-app container"
if sudo docker ps -a --format "table {{.Names}}" | grep -q jemya-app 2>/dev/null; then
    echo "✅ Found existing jemya-app container"
else
    echo "ℹ️  No existing jemya-app container found"
fi

# Check Nginx
echo "Step 4: Nginx check"
if command -v nginx > /dev/null; then
    echo "✅ Nginx is installed"
    sudo systemctl is-active nginx && echo "✅ Nginx is running" || echo "⚠️ Nginx is not running"
else
    echo "❌ Nginx is not installed"
fi

echo "✅ Deployment simulation completed"
DEPLOY_EOF

scp -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 /tmp/deploy_simulation.sh ec2-user@$PUBLIC_IP:/tmp/
ssh -i ~/.ssh/jemya-key-20251016.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 ec2-user@$PUBLIC_IP << 'EOF'
chmod +x /tmp/deploy_simulation.sh
/tmp/deploy_simulation.sh
exit 0
EOF

rm -f /tmp/deploy_simulation.sh

echo ""
echo "🎉 SSH deployment test completed successfully!"
echo ""
echo "✅ Ready for GitHub Actions SSH deployment"