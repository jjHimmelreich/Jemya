# Jemya
Spotify Playlists Generator and Analyzer

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

## � Project Structure
```
├── app.py                    # Main Streamlit application
├── configuration_manager.py  # Smart configuration system
├── conf.py                  # Local development config
├── spotify_manager.py       # Spotify API management
├── ai_manager.py           # OpenAI integration
├── backend/                # Backend modules
├── tests/                  # Test files
├── tools/                  # Development and debugging tools
├── aws/                    # AWS deployment and infrastructure
├── .github/workflows/      # GitHub Actions CI/CD
└── frontend/              # React frontend (optional)
```

## 🛡️ CI/CD Pipeline
- **GitHub Actions** with comprehensive security scanning

## 🚀 AWS Deployment Status
**EC2 Instance Ready:** `34.253.128.224` ← **Static Elastic IP**
- Add GitHub secrets and push to deploy automatically
- Access app at: `http://34.253.128.224`
- **Never changes** - production-ready setup!
- See `aws/` directory for infrastructure scripts
- **Free security tools**: CodeQL, Bandit, Safety, pip-audit, Trivy, Hadolint
- **AWS App Runner** deployment with ECR container registry
- **Automated testing** and code quality checks
- **Automated key rotation** every 90 days
