# 🔑 GitHub Secrets Setup Guide

Your ECR repository has been created successfully! Now you need to set up GitHub secrets for the CI/CD pipeline.

## 📋 Required GitHub Secrets

Go to your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**

Add these secrets:

### 🔐 AWS Configuration
- **Name**: `AWS_ACCESS_KEY_ID`
  **Value**: `[Your deployment user access key ID]` (from create-deployment-user.sh output)

- **Name**: `AWS_SECRET_ACCESS_KEY`  
  **Value**: `[Your deployment user secret key]` (from create-deployment-user.sh output)

**Note**: AWS region is hardcoded to `eu-west-1` in the workflow (no need for AWS_REGION secret)

### 🎵 Spotify Configuration  
- **Name**: `SPOTIFY_CLIENT_ID`
  **Value**: Your Spotify app client ID

- **Name**: `SPOTIFY_CLIENT_SECRET`
  **Value**: Your Spotify app client secret

- **Name**: `SPOTIFY_REDIRECT_URI`
  **Value**: Your production redirect URI (e.g., `https://your-app.com/callback`)

### 🤖 OpenAI Configuration
- **Name**: `OPENAI_API_KEY`
  **Value**: Your OpenAI API key

### 🖥️ EC2 Deployment Configuration
- **Name**: `EC2_HOST`
  **Value**: Your EC2 instance public IP address (e.g., `54.123.45.67`)

- **Name**: `EC2_SSH_KEY`
  **Value**: Content of your EC2 private key file (entire .pem file content)

## ✅ ECR Repository Details

Your ECR repository has been created with:
- **Repository Name**: `jemya`
- **Repository URI**: `431969329260.dkr.ecr.eu-west-1.amazonaws.com/jemya`
- **Region**: `eu-west-1`
- **Vulnerability Scanning**: Enabled
- **Encryption**: AES256

## 🚀 How to Get EC2 Values

### **EC2_HOST** - Your EC2 Public IP
```bash
# Method 1: AWS Console
# Go to EC2 → Instances → Select your instance → Copy "Public IPv4 address"

# Method 2: From EC2 instance itself (SSH in first)
curl http://169.254.169.254/latest/meta-data/public-ipv4

# Method 3: AWS CLI (if configured)
aws ec2 describe-instances --query 'Reservations[*].Instances[?State.Name==`running`].PublicIpAddress' --output text
```

### **EC2_SSH_KEY** - Your Private Key Content
```bash
# This is the .pem file you downloaded when creating the EC2 key pair
# Copy the ENTIRE content including BEGIN/END lines:

cat ~/.ssh/your-key-name.pem

# Should look like:
# -----BEGIN RSA PRIVATE KEY-----
# MIIEpAIBAAKCAQEA1234567890abcdef...
# ...entire key content...
# -----END RSA PRIVATE KEY-----
```

### **Setup Process**
1. **Launch EC2 instance** (t2.micro, Amazon Linux 2)
2. **Download key pair** (.pem file) during EC2 creation  
3. **Get public IP** from AWS Console
4. **Add both values** to GitHub secrets
5. **Run the setup script** on EC2: `aws/setup-ec2.sh`

## 📋 Security Group Configuration
Your EC2 instance needs these inbound rules:
- **SSH (22)**: Your IP only (for management)
- **HTTP (80)**: 0.0.0.0/0 (public web access via Nginx)
- **HTTPS (443)**: 0.0.0.0/0 (SSL access)

## ✅ Next Steps

1. ✅ ECR repository created  
2. ✅ AWS credentials added to GitHub secrets
3. ⏳ Launch EC2 instance and get IP + SSH key
4. ⏳ Add `EC2_HOST` and `EC2_SSH_KEY` to GitHub secrets
5. ⏳ Push code to trigger automated deployment
3. ⏳ Push code to trigger CI/CD pipeline
4. ⏳ Create App Runner service (optional)

The CI/CD pipeline will now be able to build and push Docker images to your ECR repository!