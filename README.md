# Jam-ya
Spotify Playlists Generator and Analyzer

![Security](https://img.shields.io/badge/Security-Hardened_IAM-green?style=flat-square)
![AWS](https://img.shields.io/badge/AWS-Least_Privilege-blue?style=flat-square)
![CI/CD](https://img.shields.io/badge/CI%2FCD-Separated_Workflows-orange?style=flat-square)

## 🔑 Creating App Credentials

Before running the app you need credentials for three external services.

### Spotify OAuth App
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **Create App** and give it a name / description
3. Under **Redirect URIs** add:
   - `http://localhost:5555/callback` (local dev)
   - `https://<your-domain>/callback` (production)
4. Save — copy the **Client ID** and **Client Secret** from the app settings

### YouTube / Google OAuth App
1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services → Library**
2. Search for and enable the **YouTube Data API v3**
3. Go to **APIs & Services → Credentials** → **Create Credentials → OAuth 2.0 Client ID**
4. Choose **Web application**, add authorised redirect URIs:
   - `http://localhost:5555/callback/youtube` (local dev)
   - `https://<your-domain>/callback/youtube` (production)
5. Download or copy the **Client ID** and **Client Secret**
6. On the **OAuth consent screen** tab, add your Google account as a test user (required while the app is in "Testing" mode)

### OpenAI API Key
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key** and copy it immediately (it is shown only once)

---

## 🚀 Quick Setup
<!-- Trigger deployment with debugging -->

### Local Development
1. Copy `conf.py.template` to `conf.py` and fill in your values:
```python
# conf.py
SPOTIFY_CLIENT_ID = "your_spotify_client_id"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret"
SPOTIFY_REDIRECT_URI = "http://localhost:5555/callback"
OPENAI_API_KEY = "your_openai_api_key"

# YouTube / Google OAuth (required for YouTube features)
YOUTUBE_CLIENT_ID = "your_google_client_id"
YOUTUBE_CLIENT_SECRET = "your_google_client_secret"
YOUTUBE_REDIRECT_URI = "http://localhost:5555/callback/youtube"
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
./run_dev.sh
```
This starts both the FastAPI backend (port 8000) and React frontend (port 5555) concurrently.

### Production Deployment
The application automatically uses environment variables in production:
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI`
- `OPENAI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REDIRECT_URI`
- `ENVIRONMENT=production`

## 📁 Project Structure
```
├── backend/                        # FastAPI backend
│   ├── main.py                     # App entry point, CORS, static SPA serving
│   ├── routers/                    # Route handlers (auth, playlists, ai, mcp)
│   └── services/                   # Business logic (spotify, ai)
│
├── frontend/                       # React + Vite + TypeScript UI
│   ├── src/
│   │   ├── components/             # Sidebar, chat, playlist table, etc.
│   │   ├── hooks/                  # useChat, usePlaylists, useAuth
│   │   └── api/                    # Typed API client
│   └── dist/                       # Built output (served by FastAPI in prod)
│
├── ai_manager.py                   # OpenAI integration for playlist generation
├── mcp_manager.py                  # MCP client (FastAPI ↔ Spotify MCP server)
├── spotify_mcp_server.py           # Spotify MCP server
├── configuration_manager.py        # Config: conf.py (dev) / env vars (prod)
├── conversation_manager.py         # Conversation persistence
├── conf.py                         # Local development config (create from template)
├── conf.py.template                # Configuration template
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Multi-stage build (Node → Python)
├── run_dev.sh                      # Start backend + frontend concurrently
│
├── .github/workflows/              # CI/CD pipelines
│   ├── ci.yml                      # Build, test, security scan, ECR push
│   ├── deploy.yml                  # Blue-green deployment (manual + auto)
│   └── rotate-aws-keys.yml         # Automated security key rotation
│
├── aws/                            # AWS infrastructure
│   ├── aws_manager.py              # Deployment orchestration
│   ├── nginx-jemya.conf            # Production nginx HTTPS config
│   └── *.json                      # Secure IAM policies (least privilege)
│
├── tools/                          # Development and debugging utilities
│   ├── spotify-crossfade-extension/    # Chrome extension: crossfade between tracks
│   └── dj-mixer/                       # DJ Mixer tool (→ github.com/jjHimmelreich/DJMixer)
├── conversations/                  # User conversation history
└── SECURITY.md                     # Security setup and guidelines
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

### Currently available at:
https://34.253.128.224/
