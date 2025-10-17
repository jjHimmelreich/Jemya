# Jemya
Spotify Playlists Generator and Analyzer

![Security](https://img.shields.io/badge/Security-Hardened_IAM-green?style=flat-square)
![AWS](https://img.shields.io/badge/AWS-Least_Privilege-blue?style=flat-square)
![CI/CD](https://img.shields.io/badge/CI%2FCD-Separated_Workflows-orange?style=flat-square)

## 🚀 Quick Setup

### Local Development
1. Copy your configuration to `conf.py`:
```python
# conf.py
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret"
SPOTIFY_REDIRECT_URI = "http://localhost:8501/callback"
OPENAI_API_KEY = "your_openai_api_key"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
streamlit run app.py
```

### Production Deployment
The application automatically uses environment variables in production:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET` 
- `SPOTIFY_REDIRECT_URI`
- `OPENAI_API_KEY`
- `ENVIRONMENT=production`

## 📁 Project Structure
```
├── app.py                          # Main Streamlit application
├── ai_manager.py                   # OpenAI integration for playlist generation
├── spotify_manager.py              # Spotify API wrapper and authentication
├── configuration_manager.py        # Smart configuration system
├── conversation_manager.py         # Conversation state management
├── conf.py                         # Local development config (create from template)
├── conf.py.template               # Configuration template
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container configuration
├── run_streamlit.sh              # Application startup script
│
├── .github/workflows/            # CI/CD pipelines
│   ├── ci.yml                   # Build, test, security scan, ECR push
│   ├── deploy.yml               # Deployment workflow (manual + auto)
│   └── rotate-aws-keys.yml      # Automated security key rotation
│
├── aws/                         # AWS infrastructure
│   ├── setup-infrastructure.sh  # Complete AWS setup
│   ├── cleanup-infrastructure.sh # Clean infrastructure teardown
│   ├── check-policies.sh        # Policy status verification
│   ├── update-policies.sh       # Apply policy updates
│   ├── *.json                   # Secure IAM policies (least privilege)
│   └── nginx-jemya.conf         # Production nginx HTTPS config
│
├── tools/                       # Development and debugging utilities
│   ├── debug_search.py          # Spotify search debugging
│   ├── track_debugger.py        # Track analysis tools
│   ├── security-check.sh        # Pre-commit security scanning
│   └── test_*.py               # Various testing utilities
│
├── conversations/               # User conversation history
├── static/                     # Static assets (images, etc.)
├── ZZZ_archive_backend/        # Legacy backend code (archived)
└── SECURITY.md                 # Security setup and guidelines
```

## 🛡️ CI/CD Pipeline
- **GitHub Actions** with comprehensive security scanning

## 🚀 AWS Deployment
**Production Instance:** `34.253.128.224` (Static Elastic IP)

### 🛡️ Security Features
- **Hardened IAM policies** with principle of least privilege
- **Region-locked permissions** (eu-west-1)
- **85% attack surface reduction** from security improvements
- **Automated key rotation** every 90 days
- **HTTPS-only** with nginx SSL termination

### 🔄 CI/CD Pipeline
- **Separated workflows** for better control and debugging
- **Security scanning** with multiple tools (CodeQL, Bandit, Safety, Trivy)
- **ECR container registry** with secure access policies
- **Automated deployment** on CI success + manual override
- **Infrastructure as code** with policy management scripts

### 📂 AWS Infrastructure
See `aws/` directory for:
- Complete infrastructure setup scripts
- Secure IAM policy definitions
- Policy management and update tools
- Infrastructure cleanup utilities
