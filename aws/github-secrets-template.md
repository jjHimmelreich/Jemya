# 📋 GitHub Secrets Setup Template

⚠️ **IMPORTANT**: This is a TEMPLATE. Never commit actual secret values!

## 🔑 Required GitHub Secrets

Go to: `https://github.com/[YOUR_USERNAME]/Jemya/settings/secrets/actions`

### **AWS Deployment Credentials**
```
Name: AWS_ACCESS_KEY_ID
Value: [Your AWS Access Key ID - starts with AKIA]

Name: AWS_SECRET_ACCESS_KEY  
Value: [Your AWS Secret Access Key - 40 characters]
```

### **EC2 Configuration** (Optional - for auto-deployment)
```
Name: EC2_SSH_KEY
Value: [Content of your .pem file: cat ~/.ssh/jemya-key-20251016.pem]
```

### **Application Configuration**
```
Name: SPOTIFY_CLIENT_ID
Value: [Your Spotify app client ID]

Name: SPOTIFY_CLIENT_SECRET
Value: [Your Spotify app client secret]

Name: SPOTIFY_REDIRECT_URI
Value: https://[YOUR_EC2_IP]/callback

Name: OPENAI_API_KEY
Value: [Your OpenAI API key - starts with sk-]
```

## 🔍 How to Find Your Values

### AWS Credentials:
1. Go to AWS IAM Console
2. Find user: `jemya-github-actions`
3. Create new access key if needed

### EC2 SSH Key:
```bash
# Display your private key content
cat ~/.ssh/jemya-key-20251016.pem
```

### Spotify Credentials:
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Find your Jemya app
3. Copy Client ID and Client Secret

### OpenAI API Key:
1. Go to [OpenAI API Dashboard](https://platform.openai.com/api-keys)
2. Create or copy existing key

## 🚀 Deployment Process

After adding secrets:
```bash
git push origin main
```

The CI/CD pipeline will:
1. 🔍 Auto-discover your EC2 instance
2. 🚀 Deploy automatically (if SSH key provided)
3. 📋 Show manual instructions (if no SSH key)

## 🌐 Access Your App

Your app will be available at: `https://[YOUR_EC2_IP]` (HTTPS secure)

To find your current EC2 IP:
```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=jemya-instance" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text
```