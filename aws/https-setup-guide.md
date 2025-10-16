# 🔒 HTTPS/SSL Setup Guide for Jemya

## Overview
Jemya now deploys with **HTTPS by default** for secure OAuth authentication and production-ready deployment.

## 🏗️ Architecture
```
Internet (HTTPS:443) → Nginx SSL → Streamlit App (8501)
Internet (HTTP:80) → Nginx → Redirect to HTTPS
```

## 🔐 SSL Certificate Strategy

### 1. **Self-Signed Certificate (Default)**
- ✅ **Automatic**: Generated during deployment
- ✅ **Immediate HTTPS**: Works instantly
- ⚠️ **Browser Warning**: "Not secure" warning (expected)
- 🎯 **Use Case**: Development, testing, immediate deployment

### 2. **Let's Encrypt Certificate (Recommended)**
- ✅ **Free & Trusted**: No browser warnings
- ✅ **Auto-Renewal**: Handles expiration automatically
- ⚠️ **Requires Domain**: Need custom domain name
- 🎯 **Use Case**: Production with custom domain

### 3. **Custom Certificate (Enterprise)**
- ✅ **Full Control**: Your own CA or purchased cert
- ✅ **Corporate**: Works with internal CAs
- ⚠️ **Manual Setup**: Requires certificate management
- 🎯 **Use Case**: Enterprise, custom requirements

## 🚀 Current Deployment (Self-Signed)

### What Happens Automatically:
1. **Deploy container** on port 8501
2. **Install Nginx** with SSL support
3. **Generate self-signed certificate**
4. **Configure HTTPS** on port 443
5. **Redirect HTTP** (80) → HTTPS (443)

### Access URLs:
- **Primary**: `https://34.253.128.224` ← **HTTPS Secure**
- **Redirect**: `http://34.253.128.224` → Automatic redirect to HTTPS
- **Internal**: `http://localhost:8501` (Container only)

### Browser Experience:
1. Visit `http://34.253.128.224` → Redirects to HTTPS
2. Browser shows "🔒 Not secure" (self-signed cert)
3. Click "Advanced" → "Proceed to 34.253.128.224"
4. App loads securely over HTTPS

## 🌐 Upgrade to Trusted Certificate (Let's Encrypt)

### Prerequisites:
- Custom domain name (e.g., `jemya.yourdomain.com`)
- DNS pointing to your EC2 IP (`34.253.128.224`)

### Installation Steps:
```bash
# SSH to your EC2 instance
ssh -i ~/.ssh/jemya-key-20251016.pem ec2-user@34.253.128.224

# Install Certbot
sudo yum install -y certbot python3-certbot-nginx

# Stop Nginx temporarily
sudo systemctl stop nginx

# Get certificate (replace with your domain)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Update Nginx configuration
sudo tee /etc/nginx/conf.d/jemya.conf << 'EOF'
# HTTPS server with Let's Encrypt certificate
server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;
    
    # Let's Encrypt SSL certificate
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-SHA256:ECDHE-RSA-AES256-SHA384;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Increase timeouts for Streamlit
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }
}

# HTTP redirect to HTTPS
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
EOF

# Test and start Nginx
sudo nginx -t && sudo systemctl start nginx

# Set up auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet && systemctl reload nginx
```

## 🔧 Spotify OAuth Configuration

### Update Redirect URI:
Since Spotify requires HTTPS for production OAuth:

1. **Go to**: [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. **Edit your app** settings
3. **Update Redirect URIs**:
   - Remove: `http://34.253.128.224/callback`
   - Add: `https://34.253.128.224/callback`
   - Or with custom domain: `https://yourdomain.com/callback`

### Update GitHub Secrets:
```bash
SPOTIFY_REDIRECT_URI: https://34.253.128.224/callback
# Or with custom domain:
SPOTIFY_REDIRECT_URI: https://yourdomain.com/callback
```

## 🔍 Verification Commands

### Check HTTPS status:
```bash
# Test HTTPS connection
curl -I https://34.253.128.224

# Check certificate info
openssl s_client -connect 34.253.128.224:443 -servername 34.253.128.224

# Test HTTP redirect
curl -I http://34.253.128.224
```

### Check Nginx SSL:
```bash
sudo nginx -t
sudo systemctl status nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 🚨 Troubleshooting

### "SSL connection error"
- Check certificate exists: `sudo ls -la /etc/nginx/ssl/`
- Test Nginx config: `sudo nginx -t`
- Check port 443 access in security groups

### "Your connection is not private" (Chrome)
- **Expected with self-signed certificate**
- Click "Advanced" → "Proceed to site"
- Or upgrade to Let's Encrypt certificate

### "502 Bad Gateway"
- Container not running: `docker ps | grep jemya-app`
- Nginx proxy config issue
- Check internal port 8501 connectivity

### OAuth callback errors
- Verify Spotify redirect URI matches exactly
- Check HTTPS URL in GitHub secrets
- Ensure container gets correct environment variables

## 📊 Security Benefits

### HTTPS Advantages:
- ✅ **OAuth Security**: Required for Spotify production apps
- ✅ **Data Encryption**: All traffic encrypted in transit
- ✅ **Authentication**: Certificate validates server identity
- ✅ **SEO Boost**: Google prefers HTTPS sites
- ✅ **Browser Trust**: No "not secure" warnings

### Modern SSL Configuration:
- ✅ **TLS 1.2/1.3**: Latest security protocols
- ✅ **Strong Ciphers**: Modern encryption algorithms
- ✅ **Session Caching**: Performance optimization
- ✅ **WebSocket Support**: Secure real-time features

## 🎯 Next Steps

1. **✅ Current**: Self-signed HTTPS working
2. **🌐 Optional**: Get custom domain name
3. **🔐 Recommended**: Upgrade to Let's Encrypt
4. **📊 Advanced**: Add HSTS headers and security optimizations

Your Jemya app now runs on **secure HTTPS by default**! 🔒