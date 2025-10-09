#!/bin/bash

# AWS App Runner Deployment Script for Jemya Playlist Generator
# This script helps deploy your application to AWS App Runner

set -e

echo "🚀 Jemya AWS Deployment Helper"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed. Please install it first:${NC}"
    echo "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# Check if user is logged in to AWS
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Please run:${NC}"
    echo "aws configure"
    exit 1
fi

echo -e "${GREEN}✅ AWS CLI is configured${NC}"

# Get current AWS account and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
echo "Account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"

echo ""
echo "🔧 Pre-deployment checklist:"
echo "1. Update your Spotify app settings:"
echo "   - Go to https://developer.spotify.com/dashboard"
echo "   - Add your App Runner URL to Redirect URIs"
echo "   - Format: https://your-app-name.${AWS_REGION}.awsapprunner.com/callback"
echo ""
echo "2. Prepare environment variables:"
echo "   - SPOTIFY_CLIENT_ID"
echo "   - SPOTIFY_CLIENT_SECRET" 
echo "   - SPOTIFY_REDIRECT_URI"
echo "   - OPENAI_API_KEY"
echo ""

read -p "Have you completed the checklist above? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Please complete the checklist and run this script again.${NC}"
    exit 1
fi

echo ""
echo "🏗️  Building and testing Docker image locally..."

# Build Docker image
if docker build -t jemya-local .; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo ""
echo "🧪 Testing Docker image locally..."
echo "Starting container on port 8501..."

# Test the container locally
CONTAINER_ID=$(docker run -d -p 8501:8501 --name jemya-test jemya-local)

echo "Container started with ID: $CONTAINER_ID"
echo "Waiting for application to start..."
sleep 10

# Check if container is running
if docker ps | grep -q jemya-test; then
    echo -e "${GREEN}✅ Container is running${NC}"
    echo "Test URL: http://localhost:8501"
    echo ""
    read -p "Test the application in your browser, then press Enter to continue..."
else
    echo -e "${RED}❌ Container failed to start${NC}"
    docker logs jemya-test
    exit 1
fi

# Cleanup test container
docker stop jemya-test
docker rm jemya-test

echo ""
echo "🚀 Ready for AWS App Runner deployment!"
echo ""
echo "Next steps:"
echo "1. Go to AWS App Runner in the console: https://console.aws.amazon.com/apprunner/"
echo "2. Click 'Create service'"
echo "3. Choose 'Source code repository'"
echo "4. Connect your GitHub repository"
echo "5. Use these settings:"
echo "   - Runtime: Docker"
echo "   - Build command: (leave empty, uses Dockerfile)"
echo "   - Start command: (leave empty, uses Dockerfile CMD)"
echo "   - Port: 8501"
echo "6. Configure environment variables from aws-env-template.txt"
echo "7. Deploy!"
echo ""
echo -e "${GREEN}🎉 Your application is ready for deployment!${NC}"