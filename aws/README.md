# AWS Infrastructure Setup for Jemya

This directory contains scripts and configurations for setting up and managing Jemya's AWS infrastructure.

## 📁 Files Overview

### Infrastructure Setup
- `setup-aws-infrastructure.sh` - Creates AWS resources (ECR, IAM roles, etc.)
- `setup-ec2-instance.sh` - Configures EC2 instance with all required software

### Configuration Files
- `aws-deployment-policy.json` - IAM policy for GitHub Actions deployment user
- `ec2-trust-policy.json` - IAM trust policy for EC2 instance role
- `nginx-jemya.conf` - Nginx configuration for the application
- `update-iam-policy.sh` - Updates IAM policies

## 🚀 Quick Start

### 1. Prerequisites
```bash
# Install AWS CLI v2
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
```

### 2. Setup AWS Infrastructure
```bash
# Run the infrastructure setup script
./aws/setup-aws-infrastructure.sh
```

This creates:
- ✅ ECR Repository for Docker images
- ✅ IAM Role for EC2 instance
- ✅ IAM Instance Profile
- ✅ Custom IAM policies for ECR access

### 3. Configure EC2 Instance
```bash
# Copy and run setup script
scp -i ~/.ssh/jemya-key-20251016.pem aws/setup-ec2-instance.sh ec2-user@YOUR_EC2_IP:/tmp/
ssh -i ~/.ssh/jemya-key-20251016.pem ec2-user@YOUR_EC2_IP "chmod +x /tmp/setup-ec2-instance.sh && /tmp/setup-ec2-instance.sh"
```

### 4. Deploy Application

The CI/CD pipeline will automatically deploy when you push to main branch and add the EC2_SSH_KEY secret.

## 🔧 Configuration Details

### EC2 Instance Setup
The `setup-ec2-instance.sh` script configures:

- **System Updates** - Latest packages and security updates
- **Docker** - Container runtime with proper configuration
- **AWS CLI v2** - Latest version for ECR access
- **Nginx** - Reverse proxy with SSL support
- **Security** - Firewall rules and system hardening
- **Monitoring** - Health check and system info scripts
- **Log Management** - Proper log rotation and storage

### Nginx Configuration
- **HTTP (Port 80)** - Reverse proxy to Streamlit (8501)
- **HTTPS (Port 443)** - SSL termination with self-signed certificates
- **Health Checks** - `/health` endpoint for monitoring
- **WebSocket Support** - For Streamlit real-time features
- **Security Headers** - XSS protection, HSTS, etc.

### Helper Scripts Created on EC2
After setup, these scripts are available on the EC2 instance:

```bash
# Health check
/opt/jemya/scripts/health-check.sh

# Deploy application
/opt/jemya/scripts/deploy-app.sh <image-uri>

# System information
/opt/jemya/scripts/system-info.sh
```

## 🔐 Security Features

### IAM Security
- **Least Privilege** - Minimal required permissions
- **Resource-Specific** - Access limited to tagged resources
- **SSH Security** - Private key-based authentication

### Network Security
- **Security Groups** - Controlled ingress/egress rules
- **SSL/TLS** - HTTPS with proper certificates
- **Firewall** - System-level protection

### Application Security
- **Container Isolation** - Docker security boundaries
- **Log Monitoring** - Centralized logging with rotation
- **Health Monitoring** - Automated health checks

## 🔍 Monitoring & Troubleshooting

### Check Application Health
```bash
# Via health endpoint
curl http://YOUR_EC2_IP/health

# Container status
docker ps | grep jemya-app

# Application logs
docker logs jemya-app --tail 50
```

### System Monitoring
```bash
# Run system info script
/opt/jemya/scripts/system-info.sh

# Check services
systemctl status docker nginx

# Resource usage
htop
df -h
```

### Common Issues

#### SSH Connection Issues
```bash
# Check security group allows SSH (port 22)
aws ec2 describe-security-groups --group-ids <your-sg-id> --query 'SecurityGroups[0].IpPermissions[?FromPort==`22`]'

# Test SSH connection
ssh -i ~/.ssh/jemya-key-20251016.pem -o ConnectTimeout=10 ec2-user@<your-ec2-ip> "echo 'Connection successful'"
```

#### Application Not Accessible
```bash
# Check container
docker ps
docker logs jemya-app

# Check Nginx
sudo nginx -t
sudo systemctl status nginx

# Check ports
netstat -tulpn | grep -E ':(80|443|8501)'
```

#### ECR Access Issues
```bash
# Test ECR login
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 431969329260.dkr.ecr.eu-west-1.amazonaws.com

# Check IAM permissions
aws sts get-caller-identity
```

## 📋 Environment Variables

Required secrets in GitHub Actions:
- `AWS_ACCESS_KEY_ID` - GitHub Actions IAM user access key
- `AWS_SECRET_ACCESS_KEY` - GitHub Actions IAM user secret key
- `EC2_SSH_KEY` - Private SSH key content (jemya-key-20251016.pem)
- `SPOTIFY_CLIENT_ID` - Spotify API credentials
- `SPOTIFY_CLIENT_SECRET` - Spotify API credentials
- `SPOTIFY_REDIRECT_URI` - Spotify OAuth redirect
- `OPENAI_API_KEY` - OpenAI API key

## 🔄 Updates & Maintenance

### Update Infrastructure
```bash
# Update IAM policies
./aws/update-iam-policy.sh

### Update EC2 configuration
```bash
# Copy and run setup script via SSH
scp -i ~/.ssh/jemya-key-20251016.pem aws/setup-ec2-instance.sh ec2-user@<your-ec2-ip>:/tmp/
ssh -i ~/.ssh/jemya-key-20251016.pem ec2-user@<your-ec2-ip> "chmod +x /tmp/setup-ec2-instance.sh && /tmp/setup-ec2-instance.sh"
```
```

### Backup & Recovery
```bash
# Create AMI snapshot
aws ec2 create-image --instance-id i-01a86512741d7221f --name "jemya-backup-$(date +%Y%m%d)"

# Backup application data
docker exec jemya-app tar czf /tmp/app-backup.tar.gz /app/data
```

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review application logs: `docker logs jemya-app`
3. Run health check: `/opt/jemya/scripts/health-check.sh`
4. Check system status: `/opt/jemya/scripts/system-info.sh`

## 🎯 Next Steps

1. **Custom Domain** - Set up Route 53 and ACM for proper SSL
2. **Monitoring** - Add CloudWatch monitoring and alarms
3. **Backup Strategy** - Implement automated backups
4. **CI/CD Enhancement** - Add integration tests and rollback capabilities