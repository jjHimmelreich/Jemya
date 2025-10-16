#!/bin/bash
# 🌐 Custom Domain Setup for Jemya with Route 53
# 
# This script sets up a custom domain that points to your EC2 instance
# Works with both Elastic IP and dynamic IP scenarios

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🌐 Custom Domain Setup for Jemya${NC}"
echo "=================================="
echo ""

# Configuration
DOMAIN_NAME=""
INSTANCE_ID="i-01a86512741d7221f"
ELASTIC_IP="34.253.128.224"
AWS_REGION="eu-west-1"

# Get domain from user
echo -e "${YELLOW}📋 Domain Configuration${NC}"
echo "======================"
echo ""
echo "You have several options:"
echo "1. 🆓 Free subdomain (recommended for testing)"
echo "   - GitHub Pages: username.github.io"
echo "   - Netlify: appname.netlify.app"
echo "   - Vercel: appname.vercel.app"
echo ""
echo "2. 💰 Buy domain (~$10-15/year)"
echo "   - Route 53: .com, .net, .org domains"
echo "   - Namecheap, GoDaddy, etc."
echo ""
echo "3. 🆓 Free domain services"
echo "   - Freenom: .tk, .ml, .ga domains"
echo "   - NoIP: dynamic DNS service"
echo ""

read -p "Enter your domain name (e.g., jemya.yourdomain.com): " DOMAIN_NAME

if [ -z "$DOMAIN_NAME" ]; then
    echo -e "${RED}❌ Domain name is required${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}🎯 Setting up domain: ${DOMAIN_NAME}${NC}"
echo ""

# Check if domain uses Route 53
echo -e "${YELLOW}🔍 Checking domain configuration...${NC}"

# Method 1: Route 53 Hosted Zone (if domain is managed by AWS)
if aws route53 list-hosted-zones --query "HostedZones[?Name=='${DOMAIN_NAME}.']" --output text | grep -q "${DOMAIN_NAME}"; then
    echo -e "${GREEN}✅ Found Route 53 hosted zone for ${DOMAIN_NAME}${NC}"
    
    # Get hosted zone ID
    HOSTED_ZONE_ID=$(aws route53 list-hosted-zones \
        --query "HostedZones[?Name=='${DOMAIN_NAME}.'].Id" \
        --output text | cut -d'/' -f3)
    
    echo "Hosted Zone ID: $HOSTED_ZONE_ID"
    
    # Create/update A record
    echo -e "${YELLOW}🔨 Creating DNS A record...${NC}"
    
    cat > dns-change.json << EOF
{
    "Changes": [
        {
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": "${DOMAIN_NAME}",
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [
                    {
                        "Value": "${ELASTIC_IP}"
                    }
                ]
            }
        }
    ]
}
EOF

    # Apply DNS change
    CHANGE_ID=$(aws route53 change-resource-record-sets \
        --hosted-zone-id $HOSTED_ZONE_ID \
        --change-batch file://dns-change.json \
        --query 'ChangeInfo.Id' \
        --output text)
    
    echo -e "${GREEN}✅ DNS record created: ${CHANGE_ID}${NC}"
    rm dns-change.json
    
    echo -e "${YELLOW}⏳ Waiting for DNS propagation (up to 5 minutes)...${NC}"
    aws route53 wait resource-record-sets-changed --id $CHANGE_ID
    echo -e "${GREEN}✅ DNS record is active${NC}"
    
else
    echo -e "${YELLOW}⚠️ Domain not found in Route 53${NC}"
    echo "Manual DNS setup required:"
    echo ""
    echo -e "${BLUE}📋 DNS Configuration Instructions${NC}"
    echo "================================"
    echo ""
    echo "In your domain registrar's DNS settings, add:"
    echo ""
    echo -e "${YELLOW}A Record:${NC}"
    echo "  Name: @ (or leave blank for root domain)"
    echo "  Type: A" 
    echo "  Value: ${ELASTIC_IP}"
    echo "  TTL: 300 (5 minutes)"
    echo ""
    echo -e "${YELLOW}CNAME Record (for www):${NC}"
    echo "  Name: www"
    echo "  Type: CNAME"
    echo "  Value: ${DOMAIN_NAME}"
    echo "  TTL: 300"
    echo ""
fi

# Update Nginx configuration for custom domain
echo -e "${YELLOW}🔧 Updating Nginx configuration for custom domain...${NC}"

# Create Nginx config update script
cat > update-nginx-domain.sh << 'EOF'
#!/bin/bash
# Update Nginx configuration for custom domain

DOMAIN_NAME="$1"

# Update Nginx configuration
sudo tee /etc/nginx/conf.d/jemya.conf << NGINXEOF
server {
    listen 80;
    server_name ${DOMAIN_NAME} www.${DOMAIN_NAME};

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeouts for Streamlit
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
NGINXEOF

# Test and restart Nginx
sudo nginx -t && sudo systemctl restart nginx

echo "✅ Nginx configured for domain: ${DOMAIN_NAME}"
EOF

chmod +x update-nginx-domain.sh

echo ""
echo -e "${BLUE}🎉 Domain Setup Instructions${NC}"
echo "============================="
echo ""

echo -e "${GREEN}✅ Domain: ${DOMAIN_NAME}${NC}"
echo -e "${GREEN}✅ Points to: ${ELASTIC_IP}${NC}"
echo ""

echo -e "${YELLOW}🔧 Next Steps:${NC}"
echo "1. 🌐 Update EC2 Nginx configuration:"
echo "   scp update-nginx-domain.sh ec2-user@${ELASTIC_IP}:/tmp/"
echo "   ssh ec2-user@${ELASTIC_IP} 'bash /tmp/update-nginx-domain.sh ${DOMAIN_NAME}'"
echo ""

echo "2. 🔐 Set up SSL (HTTPS) - optional but recommended:"
echo "   ssh ec2-user@${ELASTIC_IP}"
echo "   sudo yum install -y certbot python3-certbot-nginx"
echo "   sudo certbot --nginx -d ${DOMAIN_NAME} -d www.${DOMAIN_NAME}"
echo ""

echo "3. 🔑 Update GitHub Secrets:"
echo "   SPOTIFY_REDIRECT_URI: https://${DOMAIN_NAME}/callback"
echo "   (or http://${DOMAIN_NAME}/callback if no SSL)"
echo ""

echo "4. 🎯 Update Spotify App Settings:"
echo "   Redirect URI: https://${DOMAIN_NAME}/callback"
echo ""

echo -e "${CYAN}🌐 Your app will be available at:${NC}"
echo -e "${GREEN}   http://${DOMAIN_NAME}${NC}"
echo -e "${GREEN}   https://${DOMAIN_NAME} (after SSL setup)${NC}"
echo ""

# Save domain configuration
cat > domain-config.txt << EOF
# Jemya Custom Domain Configuration
# Generated: $(date)

DOMAIN_NAME=${DOMAIN_NAME}
ELASTIC_IP=${ELASTIC_IP}
INSTANCE_ID=${INSTANCE_ID}

# DNS Configuration:
# A Record: ${DOMAIN_NAME} → ${ELASTIC_IP}
# CNAME: www.${DOMAIN_NAME} → ${DOMAIN_NAME}

# App URLs:
# HTTP: http://${DOMAIN_NAME}
# HTTPS: https://${DOMAIN_NAME} (after SSL setup)

# Spotify Callback: https://${DOMAIN_NAME}/callback
EOF

echo -e "${GREEN}💾 Configuration saved to: domain-config.txt${NC}"

echo ""
echo -e "${BLUE}💡 Pro Tips:${NC}"
echo "• 🔒 Always use HTTPS in production (run certbot)"
echo "• 📱 Test on mobile devices after DNS propagation"  
echo "• 🌍 DNS changes can take up to 48 hours globally"
echo "• 💰 This setup keeps your costs at $0/month!"