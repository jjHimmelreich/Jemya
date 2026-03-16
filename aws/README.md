# AWS Infrastructure for Jemya

This folder contains all AWS-related infrastructure files for the Jemya project.

## 🚀 Quick Start

### Complete Infrastructure Setup
```bash
python3 aws_manager.py setup
```

### Deploy Application
```bash
python3 aws_manager.py deploy
```

### Check Infrastructure Status
```bash
python3 aws_manager.py status
```

## 📁 File Overview

### 🔧 Core Scripts
## Core Components

- `aws_manager.py`: Complete AWS infrastructure management and deployment
- IAM policies for EC2 Session Manager access
- Configuration files for AWS services
  - Setup/cleanup ECR, IAM, EC2, Security Groups
  - Session Manager support
  - Interactive and automated modes

### 🚀 Deployment
## Scripts

- `validate.sh`: Infrastructure validation script

### 🔐 IAM Policies
- **`session-manager-policy.json`** - Session Manager permissions for GitHub Actions
- **`github-actions-user-aws-deployment-policy.json`** - Basic deployment permissions
- **`github-actions-user-ecr-policy.json`** - ECR access permissions
- **`ec2-instance-role-policy.json`** - EC2 instance role permissions

### 🌐 Configuration
- **`nginx-jemya.conf`** - Nginx reverse proxy configuration for HTTPS

## 🎯 Features

- **Session Manager Deployment** - No SSH keys or IP whitelisting required
- **Complete Automation** - One command setup
- **Security First** - IAM-based authentication
- **Environment Variables** - Secure secrets handling
- **HTTPS Support** - Nginx reverse proxy configuration

## 📋 Prerequisites

1. AWS CLI configured with appropriate permissions
2. Python 3.8+
3. boto3 library (`pip install boto3`)

## 🔍 Usage Examples

```bash
# Check current status
python3 aws_manager.py status

# Setup complete infrastructure
python3 aws_manager.py setup

# Cleanup all resources
python3 aws_manager.py cleanup

# SSH security groups (optional)
python3 aws_manager.py ssh

# Update IAM policies
python3 aws_manager.py policies
```

## 🌍 Custom Domain (jam-ya.com via GoDaddy)

### Step 1 — Run the domain setup
```bash
python3 aws_manager.py domain
```
This will:
1. Allocate an **Elastic IP** and attach it to the EC2 instance (static public IP)
2. Create a **Route 53 Hosted Zone** for `jam-ya.com`
3. Add **A records** for `jam-ya.com` and `www.jam-ya.com`
4. Update **nginx** on the server to use the real domain name
5. Print the **4 Route 53 nameservers** you must set in GoDaddy

### Step 2 — Update GoDaddy nameservers
1. Log in to [GoDaddy](https://www.godaddy.com) → **My Products** → **Domains** → `jam-ya.com`
2. Go to **DNS** → **Nameservers** → **Change** → **Enter my own nameservers (advanced)**
3. Delete existing nameservers and add the 4 NS values printed in Step 1
4. Save and wait for DNS propagation (usually 5–30 minutes)

### Step 3 — Install Let's Encrypt SSL (after DNS propagates)
```bash
python3 aws_manager.py domain --action ssl
```
This installs `certbot` on the EC2 instance and replaces the self-signed certificate with a
trusted Let's Encrypt certificate. nginx is automatically reconfigured.

### Check domain status
```bash
python3 aws_manager.py domain --action status
```

## 🔒 Security Notes

- All deployment uses Session Manager (no SSH required)
- IAM policies follow least-privilege principle
- Environment variables are passed securely
- GitHub Actions uses temporary credentials only