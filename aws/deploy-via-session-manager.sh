#!/bin/bash
# Deploy to EC2 using AWS Session Manager (no SSH required)
set -e

INSTANCE_ID=$1
IMAGE_URI=$2

if [ -z "$INSTANCE_ID" ] || [ -z "$IMAGE_URI" ]; then
    echo "Usage: $0 <instance-id> <image-uri>"
    exit 1
fi

echo "🚀 Deploying to EC2 instance via Session Manager: $INSTANCE_ID"

# Create deployment commands as an array for Session Manager
DEPLOY_COMMANDS=(
    "echo '🚀 Deploying Jemya to EC2 via Session Manager...'"
    "aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 431969329260.dkr.ecr.eu-west-1.amazonaws.com"
    "docker stop jemya-app || true"
    "docker rm jemya-app || true"
    "docker pull $IMAGE_URI"
    "docker run -d --name jemya-app -p 8501:8501 --restart unless-stopped -e ENVIRONMENT=production $IMAGE_URI"
    "if ! command -v nginx &> /dev/null; then sudo yum update -y && sudo yum install -y nginx && sudo systemctl enable nginx; fi"
    "sudo tee /etc/nginx/conf.d/jemya.conf << 'NGINX_EOF'
server {
    listen 80;
    server_name _;
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection upgrade;
    }
}
NGINX_EOF"
    "sudo nginx -t && sudo systemctl restart nginx && sudo systemctl enable nginx"
    "echo '✅ Deployment completed!'"
    "docker ps | grep jemya-app"
    "sudo systemctl status nginx --no-pager -l"
)

# Execute deployment via Session Manager
echo "📡 Executing deployment via AWS Session Manager..."

# Convert commands array to JSON format
COMMANDS_JSON=$(printf '%s\n' "${DEPLOY_COMMANDS[@]}" | jq -R . | jq -s .)

aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=$COMMANDS_JSON" \
    --query 'Command.CommandId' \
    --output text > command_id.txt

COMMAND_ID=$(cat command_id.txt)
echo "📊 Command ID: $COMMAND_ID"

# Wait for command to complete
echo "⏳ Waiting for deployment to complete..."
for i in {1..30}; do
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$INSTANCE_ID" \
        --query 'Status' \
        --output text 2>/dev/null || echo "InProgress")
    
    if [ "$STATUS" = "Success" ]; then
        echo "✅ Deployment completed successfully!"
        aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --query 'StandardOutputContent' \
            --output text
        rm -f command_id.txt
        exit 0
    elif [ "$STATUS" = "Failed" ]; then
        echo "❌ Deployment failed!"
        aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$INSTANCE_ID" \
            --query 'StandardErrorContent' \
            --output text
        rm -f command_id.txt
        exit 1
    fi
    
    echo "⏳ Still deploying... (attempt $i/30)"
    sleep 10
done

echo "⚠️ Deployment timed out"
rm -f command_id.txt
exit 1