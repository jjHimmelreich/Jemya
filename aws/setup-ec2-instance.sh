#!/bin/bash
# Complete setup script for EC2 instance to ensure it's ready for Jemya deployment
# This script configures all necessary components for automated deployment

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
}

log "🔧 Setting up EC2 instance for Jemya deployment..."

# Update system packages
log "📦 Updating system packages..."
sudo yum update -y
success "System packages updated"

# Install essential tools
log "🛠️ Installing essential tools..."
sudo yum install -y \
    curl \
    wget \
    unzip \
    git \
    htop \
    nano \
    tree \
    openssl \
    ca-certificates \
    gnupg \
    lsb-release
success "Essential tools installed"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    log "🐳 Installing Docker..."
    sudo yum install -y docker
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -a -G docker ec2-user
    
    # Verify Docker installation
    sudo docker --version
    success "Docker installed and configured"
else
    log "🐳 Docker already installed"
    sudo systemctl start docker
    sudo systemctl enable docker
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    log "🐙 Installing Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    docker-compose --version
    success "Docker Compose installed"
else
    log "🐙 Docker Compose already installed"
fi

# Install AWS CLI v2 if not present
if ! command -v aws &> /dev/null; then
    log "☁️ Installing AWS CLI v2..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
    rm -rf awscliv2.zip aws/
    aws --version
    success "AWS CLI v2 installed"
else
    log "☁️ AWS CLI already installed"
    aws --version
fi

# Install jq for JSON processing
if ! command -v jq &> /dev/null; then
    log "📊 Installing jq..."
    sudo yum install -y jq
    success "jq installed"
else
    log "📊 jq already installed"
fi

# Install Nginx
if ! command -v nginx &> /dev/null; then
    log "🌐 Installing Nginx..."
    sudo yum install -y nginx
    sudo systemctl enable nginx
    success "Nginx installed"
else
    log "🌐 Nginx already installed"
    sudo systemctl enable nginx
fi

# Configure Nginx for Jemya
log "⚙️ Configuring Nginx for Jemya..."
sudo mkdir -p /etc/nginx/conf.d
sudo mkdir -p /etc/nginx/ssl
sudo mkdir -p /var/log/nginx

# Create Nginx configuration for Jemya
sudo tee /etc/nginx/conf.d/jemya.conf << 'NGINX_EOF'
# Jemya Application Nginx Configuration
server {
    listen 80;
    server_name _;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    # Main application proxy to Streamlit
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        
        # Headers for Streamlit
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Streamlit
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }
    
    # Static files (if any)
    location /static/ {
        alias /var/www/jemya/static/;
        expires 1M;
        access_log off;
        add_header Cache-Control "public, immutable";
    }
    
    # Security: Hide server info
    server_tokens off;
    
    # Logging
    access_log /var/log/nginx/jemya_access.log;
    error_log /var/log/nginx/jemya_error.log;
}

# HTTPS server (optional - for SSL termination)
server {
    listen 443 ssl http2;
    server_name _;
    
    ssl_certificate /etc/nginx/ssl/jemya.crt;
    ssl_certificate_key /etc/nginx/ssl/jemya.key;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS
    add_header Strict-Transport-Security "max-age=31536000" always;
    
    # Same location blocks as HTTP server
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
    
    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
NGINX_EOF

# Create self-signed SSL certificate
log "🔐 Creating self-signed SSL certificate..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/jemya.key \
    -out /etc/nginx/ssl/jemya.crt \
    -subj "/C=US/ST=Cloud/L=AWS/O=Jemya/OU=IT Department/CN=jemya-app" \
    -config <(
        echo '[req]'
        echo 'distinguished_name = req'
        echo '[san]'
        echo 'subjectAltName = @alt_names'
        echo '[alt_names]'
        echo 'DNS.1 = localhost'
        echo 'DNS.2 = jemya-app'
        echo 'IP.1 = 127.0.0.1'
    ) -extensions san

sudo chmod 600 /etc/nginx/ssl/jemya.key
sudo chmod 644 /etc/nginx/ssl/jemya.crt
success "SSL certificate created"

# Test Nginx configuration
log "🧪 Testing Nginx configuration..."
sudo nginx -t
success "Nginx configuration is valid"

# Configure system limits for Docker
log "📊 Configuring system limits..."
sudo tee -a /etc/security/limits.conf << 'LIMITS_EOF'

# Jemya Docker limits
* soft nofile 65536
* hard nofile 65536
* soft nproc 65536
* hard nproc 65536
LIMITS_EOF

# Configure Docker daemon
log "� Configuring Docker daemon..."
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json << 'DOCKER_EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true
}
DOCKER_EOF

# Note: SSM Agent is pre-installed on Amazon Linux 2 and enabled by default

# Start and enable services
log "🚀 Starting services..."
sudo systemctl restart docker
sudo systemctl enable docker
sudo systemctl start nginx
sudo systemctl enable nginx
success "All services started"

# Create application directories
log "📁 Creating application directories..."
sudo mkdir -p /var/www/jemya/{static,logs,tmp}
sudo mkdir -p /opt/jemya/{config,scripts,backups}
sudo chown -R ec2-user:ec2-user /var/www/jemya
sudo chown -R ec2-user:ec2-user /opt/jemya
success "Application directories created"

# Configure log rotation
log "📋 Configuring log rotation..."
sudo tee /etc/logrotate.d/jemya << 'LOGROTATE_EOF'
/var/log/nginx/jemya_*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 644 nginx nginx
    sharedscripts
    postrotate
        if [ -f /var/run/nginx.pid ]; then
            kill -USR1 `cat /var/run/nginx.pid`
        fi
    endscript
}

/var/www/jemya/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ec2-user ec2-user
}
LOGROTATE_EOF
success "Log rotation configured"

# Create monitoring script
log "📊 Creating monitoring script..."
sudo tee /opt/jemya/scripts/health-check.sh << 'HEALTH_EOF'
#!/bin/bash
# Health check script for Jemya application

check_docker() {
    if docker ps | grep -q jemya-app; then
        echo "✅ Jemya container is running"
        return 0
    else
        echo "❌ Jemya container is not running"
        return 1
    fi
}

check_nginx() {
    if systemctl is-active --quiet nginx; then
        echo "✅ Nginx is running"
        return 0
    else
        echo "❌ Nginx is not running"
        return 1
    fi
}

check_app_health() {
    if curl -f -s http://localhost/health > /dev/null; then
        echo "✅ Application health check passed"
        return 0
    else
        echo "❌ Application health check failed"
        return 1
    fi
}

echo "🔍 Jemya Health Check - $(date)"
echo "================================"

docker_ok=0
nginx_ok=0
app_ok=0

check_docker && docker_ok=1
check_nginx && nginx_ok=1
check_app_health && app_ok=1

echo ""
echo "Summary:"
echo "- Docker: $([[ $docker_ok -eq 1 ]] && echo "✅" || echo "❌")"
echo "- Nginx: $([[ $nginx_ok -eq 1 ]] && echo "✅" || echo "❌")"
echo "- App Health: $([[ $app_ok -eq 1 ]] && echo "✅" || echo "❌")"

if [[ $docker_ok -eq 1 && $nginx_ok -eq 1 && $app_ok -eq 1 ]]; then
    echo ""
    echo "🎉 All systems operational!"
    exit 0
else
    echo ""
    echo "⚠️ Some systems need attention"
    exit 1
fi
HEALTH_EOF

sudo chmod +x /opt/jemya/scripts/health-check.sh
success "Health check script created"

# Create deployment helper script
log "🚀 Creating deployment helper script..."
sudo tee /opt/jemya/scripts/deploy-app.sh << 'DEPLOY_EOF'
#!/bin/bash
# Deployment helper script for Jemya

IMAGE_URI=${1:-"latest"}
CONTAINER_NAME="jemya-app"

if [[ -z "$IMAGE_URI" || "$IMAGE_URI" == "latest" ]]; then
    echo "❌ Please provide Docker image URI"
    echo "Usage: $0 <image-uri>"
    echo "Example: $0 431969329260.dkr.ecr.eu-west-1.amazonaws.com/jemya:abc123"
    exit 1
fi

echo "🚀 Deploying Jemya application..."
echo "Image: $IMAGE_URI"
echo ""

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 431969329260.dkr.ecr.eu-west-1.amazonaws.com

# Stop and remove existing container
echo "🛑 Stopping existing container..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Pull new image
echo "📥 Pulling new image..."
docker pull $IMAGE_URI

# Run new container
echo "🎬 Starting new container..."
docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p 8501:8501 \
    -e ENVIRONMENT="production" \
    -v /var/www/jemya/logs:/app/logs \
    -v /opt/jemya/config:/app/config:ro \
    --log-driver json-file \
    --log-opt max-size=100m \
    --log-opt max-file=3 \
    $IMAGE_URI

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 10

# Verify deployment
echo "🔍 Verifying deployment..."
if docker ps | grep -q $CONTAINER_NAME; then
    echo "✅ Container is running"
    docker logs --tail 10 $CONTAINER_NAME
    
    # Test health endpoint
    sleep 5
    if curl -f -s http://localhost:8501 > /dev/null; then
        echo "✅ Application is responding"
        echo ""
        echo "🎉 Deployment completed successfully!"
        echo "🌐 Application available at:"
        echo "   - HTTP: http://$(curl -s ifconfig.me)"
        echo "   - Local: http://localhost"
    else
        echo "⚠️ Application may still be starting up"
        echo "Check logs: docker logs $CONTAINER_NAME"
    fi
else
    echo "❌ Container failed to start"
    echo "Check logs: docker logs $CONTAINER_NAME"
    exit 1
fi
DEPLOY_EOF

sudo chmod +x /opt/jemya/scripts/deploy-app.sh
success "Deployment helper script created"

# Create system info script
log "📋 Creating system info script..."
sudo tee /opt/jemya/scripts/system-info.sh << 'INFO_EOF'
#!/bin/bash
# System information script

echo "🖥️ Jemya EC2 Instance Information"
echo "================================="
echo ""

echo "📊 System Info:"
echo "- Hostname: $(hostname)"
echo "- OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d'"' -f2)"
echo "- Kernel: $(uname -r)"
echo "- Uptime: $(uptime -p)"
echo "- Load: $(uptime | awk -F'load average:' '{print $2}')"
echo ""

echo "💾 Memory Usage:"
free -h
echo ""

echo "💽 Disk Usage:"
df -h /
echo ""

echo "🐳 Docker Info:"
echo "- Version: $(docker --version 2>/dev/null || echo 'Not installed')"
echo "- Status: $(systemctl is-active docker 2>/dev/null || echo 'Not running')"
echo "- Containers: $(docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'Docker not available')"
echo ""

echo "🌐 Nginx Info:"
echo "- Version: $(nginx -v 2>&1 | cut -d' ' -f3 2>/dev/null || echo 'Not installed')"
echo "- Status: $(systemctl is-active nginx 2>/dev/null || echo 'Not running')"
echo "- Config Test: $(nginx -t 2>&1 | tail -1 2>/dev/null || echo 'Config not available')"
echo ""

echo "☁️ AWS Info:"
echo "- CLI Version: $(aws --version 2>&1 | cut -d' ' -f1 2>/dev/null || echo 'Not installed')"
echo "- Instance ID: $(curl -s http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null || echo 'Not available')"
echo "- Public IP: $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'Not available')"
echo "- Private IP: $(curl -s http://169.254.169.254/latest/meta-data/local-ipv4 2>/dev/null || echo 'Not available')"
echo "- AZ: $(curl -s http://169.254.169.254/latest/meta-data/placement/availability-zone 2>/dev/null || echo 'Not available')"
echo ""

echo " Services Status:"
for service in docker nginx; do
    status=$(systemctl is-active $service 2>/dev/null || echo "inactive")
    enabled=$(systemctl is-enabled $service 2>/dev/null || echo "disabled")
    echo "- $service: $status ($enabled)"
done
INFO_EOF

sudo chmod +x /opt/jemya/scripts/system-info.sh
success "System info script created"

# Final status check
log "� Final system status check..."
echo ""

success "🎉 EC2 instance setup completed successfully!"
echo ""
echo "📋 Setup Summary:"
echo "=================="
echo "✅ System packages updated"
echo "✅ Docker installed and configured"
echo "✅ Docker Compose installed"
echo "✅ AWS CLI v2 installed"
echo "✅ Nginx installed and configured"
echo "✅ SSL certificates created"
echo "✅ SSM Agent configured"
echo "✅ Application directories created"
echo "✅ Monitoring scripts created"
echo "✅ Helper scripts created"
echo ""

echo "🚀 Ready for deployment!"
echo ""
echo "📊 System Status:"
sudo systemctl status docker --no-pager -l | head -3
sudo systemctl status nginx --no-pager -l | head -3
echo ""

echo "🛠️ Available Scripts:"
echo "- Health Check: /opt/jemya/scripts/health-check.sh"
echo "- Deploy App: /opt/jemya/scripts/deploy-app.sh <image-uri>"
echo "- System Info: /opt/jemya/scripts/system-info.sh"
echo ""

echo "🌐 Test Nginx Configuration:"
echo "- HTTP Health: curl http://localhost/health"
echo "- HTTPS Health: curl -k https://localhost/health"