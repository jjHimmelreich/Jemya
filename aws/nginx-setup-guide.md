# 🌐 Nginx Reverse Proxy Setup for Jemya

## Overview
Jemya uses **Nginx as a reverse proxy** to serve the application on standard HTTP port 80, while the Streamlit app runs internally on port 8501.

## 🏗️ Architecture
```
Internet (Port 80) → Nginx → Streamlit App (Port 8501)
```

### Benefits:
- ✅ **Standard port 80** - No need to specify port in URLs
- ✅ **SSL/HTTPS support** - Easy to add certificates later
- ✅ **Load balancing** - Can scale to multiple containers
- ✅ **Static file serving** - Nginx can serve assets efficiently
- ✅ **WebSocket support** - Proper handling of Streamlit's real-time features

## 🔧 Current Configuration

The CI/CD pipeline automatically sets up Nginx with this configuration:

```nginx
server {
    listen 80;
    server_name _;  # Accept any hostname/IP
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeouts for Streamlit
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
```

## 📍 Access URLs

### Production (Auto-deployed):
- **Public URL**: `http://34.253.128.224` (Port 80)
- **Internal**: `http://localhost:8501` (Container only)

### Custom Domain (Optional):
Use `aws/setup-custom-domain.sh` to configure:
- **Custom URL**: `http://yourdomain.com` (Port 80)
- **With SSL**: `https://yourdomain.com` (Port 443)

## 🚀 Deployment Flow

### Automated (CI/CD Pipeline):
1. **Discover EC2** instance dynamically
2. **Deploy container** on port 8501
3. **Install Nginx** (if not present)
4. **Configure reverse proxy** from port 80 → 8501
5. **Start/restart services**

### Manual Setup:
```bash
# 1. Install Nginx
sudo yum update -y
sudo yum install -y nginx

# 2. Create configuration
sudo tee /etc/nginx/conf.d/jemya.conf << 'EOF'
server {
    listen 80;
    server_name _;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeouts for Streamlit
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}
EOF

# 3. Test and start
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl start nginx
```

## 🔍 Verification Commands

### Check Nginx status:
```bash
sudo systemctl status nginx
curl -I http://localhost  # Should return Streamlit headers
```

### Check container:
```bash
docker ps | grep jemya-app
curl -I http://localhost:8501  # Direct container access
```

### Check logs:
```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
docker logs jemya-app
```

## 🚨 Troubleshooting

### "502 Bad Gateway"
- Container not running: `docker ps | grep jemya-app`
- Wrong port mapping: Check `-p 8501:8501` in docker run
- Firewall blocking: Check security groups allow port 80

### "Connection refused"
- Nginx not running: `sudo systemctl start nginx`
- Wrong Nginx config: `sudo nginx -t`
- Port 80 blocked: Check EC2 security groups

### WebSocket issues
- Missing upgrade headers in Nginx config
- Timeout settings too low
- Firewall blocking WebSocket upgrades

## 🔐 SSL/HTTPS Setup (Optional)

### With Let's Encrypt (Free):
```bash
# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Get certificate (requires domain name)
sudo certbot --nginx -d yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### With Custom Certificate:
```bash
# Update Nginx config to include SSL
server {
    listen 443 ssl;
    server_name yourdomain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # Same proxy configuration as above
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

## 📊 Performance Tips

### Static File Serving:
```nginx
location /static/ {
    alias /app/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### Compression:
```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript;
```

### Rate Limiting:
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

location / {
    limit_req zone=api burst=20 nodelay;
    # ... existing proxy config
}
```

## 🔧 Configuration Files

### Nginx Main Config:
- **Location**: `/etc/nginx/nginx.conf`
- **Jemya Config**: `/etc/nginx/conf.d/jemya.conf`
- **Logs**: `/var/log/nginx/`

### Docker Container:
- **Image**: ECR repository `jemya:latest`
- **Port**: 8501 (internal)
- **Restart**: `unless-stopped`

## 🎯 Next Steps

1. **✅ Basic setup**: Nginx + Streamlit (current)
2. **🔐 Add SSL**: Use Let's Encrypt for HTTPS
3. **📊 Monitoring**: Add Nginx metrics and health checks
4. **🚀 CDN**: CloudFront for global performance
5. **🔄 Load Balancing**: Multiple containers if needed

Your app is now properly configured with Nginx on standard port 80! 🌐