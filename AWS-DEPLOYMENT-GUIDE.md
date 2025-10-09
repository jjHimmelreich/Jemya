# Jemya - AWS Deployment Guide

This guide walks you through deploying your Jemya Playlist Generator to AWS using AWS App Runner.

## 🏗️ Architecture Overview

**AWS App Runner** is the recommended deployment option because:
- Fully managed container service
- Auto-scaling based on traffic  
- Direct GitHub integration
- Built-in load balancing and SSL
- Pay-per-use pricing

## 📋 Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** installed and configured
3. **Docker** installed locally (for testing)
4. **GitHub repository** with your code
5. **API Keys** for Spotify and OpenAI

## 🚀 Step-by-Step Deployment

### 1. Prepare Your Environment

```bash
# Run the deployment preparation script
./deploy-aws.sh
```

This script will:
- Check AWS CLI setup
- Build and test Docker image locally  
- Verify your application works

### 2. Update Spotify App Settings

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Select your app
3. Click "Edit Settings"
4. Add your future App Runner URL to **Redirect URIs**:
   ```
   https://your-app-name.region.awsapprunner.com/callback
   ```
   (You'll get the actual URL after deployment)

### 3. Deploy to AWS App Runner

#### Option A: Using AWS Console (Recommended)

1. **Open AWS App Runner Console**
   - Go to: https://console.aws.amazon.com/apprunner/
   - Click "Create service"

2. **Configure Source**
   - Choose "Source code repository"
   - Connect your GitHub account
   - Select your repository
   - Branch: `main`

3. **Configure Build**
   - Runtime: `Docker`
   - Build command: *(leave empty)*
   - Start command: *(leave empty)*
   - Port: `8501`

4. **Configure Service**
   - Service name: `jemya-playlist-generator`
   - Virtual CPU: `0.25 vCPU`
   - Virtual memory: `0.5 GB`
   - Auto scaling: `1-10` instances

5. **Environment Variables**
   Set these required variables:
   ```
   SPOTIFY_CLIENT_ID=your_spotify_client_id
   SPOTIFY_CLIENT_SECRET=your_spotify_client_secret  
   SPOTIFY_REDIRECT_URI=https://your-app-url.region.awsapprunner.com/callback
   OPENAI_API_KEY=your_openai_api_key
   ENVIRONMENT=production
   ```

6. **Create Service**
   - Review settings
   - Click "Create & deploy"
   - Wait for deployment (5-10 minutes)

#### Option B: Using AWS CLI

```bash
# Create apprunner.yaml configuration
# Already created in your repository

# Deploy using CLI
aws apprunner create-service \
  --service-name jemya-playlist-generator \
  --source-configuration '{
    "CodeRepository": {
      "RepositoryUrl": "https://github.com/yourusername/Jemya",
      "SourceCodeVersion": {
        "Type": "BRANCH",
        "Value": "main"
      },
      "CodeConfiguration": {
        "ConfigurationSource": "REPOSITORY"
      }
    }
  }' \
  --instance-configuration '{
    "Cpu": "0.25 vCPU",
    "Memory": "0.5 GB"
  }'
```

### 4. Update Configuration

Once deployed, you'll get a URL like:
```
https://abcd1234.us-east-1.awsapprunner.com
```

**Update your environment variables:**
1. In App Runner console, go to your service
2. Click "Configuration" tab
3. Update `SPOTIFY_REDIRECT_URI` with actual URL + `/callback`
4. Deploy the changes

**Update Spotify app settings:**
1. Add the actual redirect URI to your Spotify app
2. Remove the placeholder URI

## 💰 Cost Estimation

**AWS App Runner Pricing (us-east-1):**
- **Build time**: $0.005 per build minute
- **Running costs**: 
  - vCPU: $0.064 per vCPU-hour
  - Memory: $0.007 per GB-hour
- **Data transfer**: $0.09 per GB (outbound)

**Example monthly cost** (light usage):
- 0.25 vCPU × 730 hours × $0.064 = ~$12
- 0.5 GB × 730 hours × $0.007 = ~$3  
- **Total: ~$15/month** + data transfer

## 🔒 Security Best Practices

### Environment Variables
- **Never commit API keys** to git
- Use AWS App Runner environment variables
- Consider AWS Systems Manager Parameter Store for sensitive data
- ⚠️ **Important**: `conf_aws.py` requires ALL environment variables to be set - it contains no fallback secrets

### Network Security
- App Runner provides HTTPS by default
- No need for additional SSL certificates
- Built-in DDoS protection

### API Key Management
```python
# Use environment variables in conf_aws.py
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
```

## 📈 Monitoring & Scaling

### Auto Scaling
App Runner automatically scales based on:
- CPU utilization
- Memory usage  
- Request volume

### Monitoring
- **CloudWatch Logs**: Application logs
- **CloudWatch Metrics**: Performance metrics
- **App Runner Console**: Service health dashboard

### Health Checks
The Dockerfile includes a health check:
```dockerfile
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health
```

## 🔧 Troubleshooting

### Common Issues

1. **Build Failures**
   ```bash
   # Test locally first
   docker build -t jemya-test .
   docker run -p 8501:8501 jemya-test
   ```

2. **Spotify Redirect URI Mismatch**
   - Ensure exact URL match in Spotify app settings
   - Include `/callback` at the end

3. **Environment Variables Not Set** 
   - Check App Runner configuration tab
   - Redeploy after changes

4. **Port Issues**
   - App Runner expects port 8501
   - Dockerfile EXPOSE 8501 is correct

### Logs Access
```bash
# View logs using AWS CLI
aws logs tail /aws/apprunner/jemya-playlist-generator --follow
```

## 🚀 Deployment Automation

For continuous deployment, set up GitHub Actions:

```yaml
# .github/workflows/deploy.yml
name: Deploy to AWS App Runner
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Deploy to App Runner
        run: |
          # App Runner will automatically detect changes
          # and trigger a new deployment
```

## 📚 Additional Resources

- [AWS App Runner Documentation](https://docs.aws.amazon.com/apprunner/)
- [Streamlit on App Runner Guide](https://docs.streamlit.io/knowledge-base/tutorials/deploy/aws-app-runner)
- [Spotify Web API Reference](https://developer.spotify.com/documentation/web-api/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)

## 🎉 Next Steps

After successful deployment:

1. **Test all functionality** with the live URL
2. **Set up monitoring** and alerts
3. **Configure custom domain** (optional)
4. **Implement backup strategy** for conversation data
5. **Consider adding analytics** for usage insights

Your Jemya Playlist Generator is now running in the cloud! 🌟