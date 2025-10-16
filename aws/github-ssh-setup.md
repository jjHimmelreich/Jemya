# 🔐 GitHub SSH Key Setup for Auto-Deployment

## Overview
The CI/CD pipeline now automatically discovers your EC2 instance and can deploy to it if you provide the SSH key as a GitHub secret.

## 🚀 Quick Setup

### 1. Get Your SSH Private Key
Your SSH private key is located at:
```bash
~/jemya-key-20251016.pem
```

### 2. Add to GitHub Secrets
1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `EC2_SSH_KEY`
5. Value: Copy the entire content of your `.pem` file:
   ```bash
   cat ~/jemya-key-20251016.pem
   ```
6. Click **Add secret**

### 3. How It Works
- 🔍 **Auto-Discovery**: Finds your EC2 instance by tag `Name=jemya-instance`
- 🌐 **Dynamic IP**: Gets current public IP automatically (no static secrets needed!)
- 🚀 **Auto-Deploy**: If SSH key exists, deploys automatically
- 📋 **Manual Fallback**: If no SSH key, provides manual deployment instructions

## 🔧 What the Pipeline Does

### With SSH Key (Automatic):
1. Discovers EC2 instance by tag
2. Gets current public IP dynamically
3. Creates deployment script
4. SCPs script to EC2
5. Executes deployment via SSH
6. Shows success summary with URL

### Without SSH Key (Manual):
1. Discovers EC2 instance by tag
2. Gets current public IP dynamically
3. Shows manual deployment commands
4. Provides Docker pull/run instructions

## 🏷️ Required EC2 Tags
Make sure your EC2 instance has this tag:
- **Key**: `Name`
- **Value**: `jemya-instance`

You can verify/add this tag:
```bash
# Check current tags
aws ec2 describe-tags --filters "Name=resource-id,Values=i-01a86512741d7221f"

# Add tag if missing
aws ec2 create-tags --resources i-01a86512741d7221f --tags Key=Name,Value=jemya-instance
```

## 🔄 Benefits
- ✅ **No static IP secrets needed** - discovers current IP automatically
- ✅ **Handles EC2 restarts** - always finds current IP
- ✅ **Multiple instances support** - finds by tag, not hardcoded ID
- ✅ **Graceful fallback** - works with or without SSH key
- ✅ **Security focused** - SSH key properly handled and cleaned up

## 🚨 Troubleshooting

### "No running Jemya EC2 instance found!"
1. Check your instance is running: `aws ec2 describe-instances --instance-ids i-01a86512741d7221f`
2. Verify the Name tag exists and equals `jemya-instance`
3. Make sure you're in the correct AWS region (`eu-west-1`)

### Deployment fails
1. Check security groups allow SSH (port 22) from GitHub Actions IP ranges
2. Verify EC2_SSH_KEY secret contains the full `.pem` file content
3. Ensure ec2-user has Docker permissions on the instance

## 📝 Example Deployment Output

### Automatic Deployment:
```
🔍 Auto-discovering Jemya EC2 instance...
✅ Found Jemya EC2 instance:
   Instance ID: i-01a86512741d7221f
   Public IP: 34.253.128.224
   Private IP: 172.31.xx.xx
✅ SSH key available for deployment
🚀 Deploying to EC2 instance: 34.253.128.224
🎉 Deployment to EC2 completed successfully!
```

### Manual Instructions:
```
📋 EC2 Instance discovered but no SSH key configured
🖥️ Instance: i-01a86512741d7221f
🌐 IP: 34.253.128.224
📦 Docker image built and pushed to ECR
🔧 To deploy manually, SSH to your instance and run: [commands]
```

Perfect! Your deployment will now automatically adapt to any EC2 IP changes! 🚀