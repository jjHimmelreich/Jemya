# CI/CD Guide — Jam-ya

## Quick Links

| Service | Purpose | Link |
|---------|---------|------|
| **GitHub** | Source code, Actions, Secrets | [github.com/jjHimmelreich/Jemya](https://github.com/jjHimmelreich/Jemya) |
| **GitHub Actions** | CI/CD pipelines | [Actions tab](https://github.com/jjHimmelreich/Jemya/actions) |
| **GitHub Secrets** | Manage pipeline secrets | [Settings → Secrets](https://github.com/jjHimmelreich/Jemya/settings/secrets/actions) |
| **AWS Console** | EC2, ECR, IAM, SSM | [console.aws.amazon.com](https://console.aws.amazon.com) |
| **AWS EC2** | Running instance | [EC2 eu-west-1](https://eu-west-1.console.aws.amazon.com/ec2/home?region=eu-west-1#Instances) |
| **AWS ECR** | Docker image repository | [ECR eu-west-1](https://eu-west-1.console.aws.amazon.com/ecr/repositories?region=eu-west-1) |
| **AWS IAM** | Users, roles, policies | [IAM Console](https://console.aws.amazon.com/iam/home#/users) |
| **Spotify Developer** | App credentials (Client ID/Secret) | [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) |
| **OpenAI** | API key management | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **GoDaddy** | Domain DNS management | [dcc.godaddy.com/manage/jam-ya.com/dns](https://dcc.godaddy.com/manage/jam-ya.com/dns) |

---

## Overview

Jam-ya uses a fully automated CI/CD pipeline built on **GitHub Actions** with **AWS ECR** for container storage and **AWS EC2** (Amazon Linux 2) as the deployment target. Deployments are performed SSH-less via **AWS Session Manager**.

```
Push to main
    │
    ▼
┌─────────────────────────────────────────┐
│           CI Workflow (ci.yml)          │
│  1. Build Docker image                  │
│  2. Security scans (CodeQL, Bandit,     │
│     Trivy, Hadolint, pip-audit)         │
│  3. Run tests + Docker smoke test       │
│  4. Push image to ECR (main only)       │
└──────────────────┬──────────────────────┘
                   │ on success
                   ▼
┌─────────────────────────────────────────┐
│        Deploy Workflow (deploy.yml)     │
│  1. Gate check (CI passed?)             │
│  2. Pull image from ECR                 │
│  3. Blue-Green deploy via SSM           │
│  4. Verify deployment                   │
└─────────────────────────────────────────┘
```

---

## Workflows

### 1. `ci.yml` — Continuous Integration

**Triggers:** Push to `main` or `develop`, PR to `main`, manual dispatch.

#### Jobs (in order)

| Job | Depends on | Description |
|-----|-----------|-------------|
| `build-image` | — | Builds Docker image once, exports as artifact |
| `security-scans` | `build-image` | CodeQL, Bandit, pip-audit |
| `docker-security` | `build-image` | Hadolint, Trivy |
| `test` | all above | Code style, unit tests, Docker smoke test |
| `push-to-ecr` | all above | Pushes to ECR (main branch pushes only) |

#### Image tagging strategy

| Condition | Tags applied |
|-----------|-------------|
| Push to `main` | `latest`, `sha-<commit>` |
| Push to `develop` | `develop` |
| Pull Request | `pr-<number>` |

#### Security gates

| Tool | What it checks | Fails on |
|------|---------------|----------|
| **CodeQL** | Python SAST vulnerabilities | Any finding |
| **Bandit** | Python code security | HIGH+ severity |
| **pip-audit** | Dependency CVEs (OSV database) | Critical patterns or >50 vulns |
| **Hadolint** | Dockerfile best practices | Reported to GitHub Security tab |
| **Trivy (image)** | Container OS + package CVEs | CRITICAL unfixed |
| **Trivy (fs)** | Filesystem vulnerabilities | Reported to GitHub Security tab |

#### Docker smoke test

CI starts the container with dummy env vars and hits `GET /health`. Must return HTTP 200 for the pipeline to proceed.

---

### 2. `deploy.yml` — Deploy to Production

**Triggers:**
- Automatically after `ci.yml` completes successfully on `main`
- Manually via **Actions → Deploy to Production → Run workflow**

#### Manual inputs

| Input | Default | Description |
|-------|---------|-------------|
| `environment` | `production` | `production` or `staging` |
| `force_deploy` | `false` | Skip CI gate check |
| `image_tag` | _(latest)_ | Specific ECR image tag to deploy |

#### Jobs

**`deployment-gate`**
- Checks whether CI passed (auto trigger) or if manually triggered
- Resolves which image tag to deploy (`latest` for auto, specified tag for manual)
- Verifies EC2 instance is running and SSM connectivity works

**`deploy`**
- Logs into ECR, verifies image exists
- Discovers the `jemya-instance` EC2 by tag
- Exports secrets as env vars, runs `aws_manager.py deploy` via the runner
- `aws_manager.py` sends the `docker run` command to EC2 via SSM

**`notify`**
- Always runs (success or failure), logs deployment result

#### Blue-Green deployment

Each deploy alternates between `jemya-blue` and `jemya-green` containers:

```
Current: jemya-blue  (port 8001)
Deploy:
  1. Start jemya-green on port 8002
  2. Health check jemya-green
  3. Update nginx proxy_pass → 8002
  4. Stop & remove jemya-blue
Done: jemya-green (port 8002)
```

If any step fails, nginx is **not** reloaded and the old container keeps serving traffic (automatic rollback).

---

### 3. `rotate-aws-keys.yml` — AWS Key Rotation

**Triggers:** Scheduled every 90 days at 02:00 UTC, or manual dispatch.

**Steps:**
1. Create a new IAM access key for `jemya-github-actions`
2. Test the new key works (`sts:GetCallerIdentity`)
3. Update `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` GitHub secrets via `gh` CLI
4. Wait 30 seconds for propagation
5. Delete the old key
6. On failure: automatically deletes the newly created key (cleanup)

---

## GitHub Secrets Required

Go to **[Settings → Secrets and variables → Actions](https://github.com/jjHimmelreich/Jemya/settings/secrets/actions)** to manage these.

### AWS

> Manage IAM users and keys at [console.aws.amazon.com/iam](https://console.aws.amazon.com/iam/home#/users)

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user `jemya-github-actions` access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user `jemya-github-actions` secret key |
| `AWS_REGION` | `eu-west-1` |

### Application (injected into Docker container at deploy time)

> **Spotify:** get Client ID & Secret at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)  
> **OpenAI:** get API key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

| Secret | Description |
|--------|-------------|
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIFY_REDIRECT_URI` | `https://jam-ya.com/auth/callback` |
| `OPENAI_API_KEY` | OpenAI API key |

### Key rotation (optional)

| Secret | Description |
|--------|-------------|
| `NOTIFICATION_EMAIL` | Gmail address for rotation alerts |
| `NOTIFICATION_EMAIL_PASSWORD` | Gmail app password |

---

## How Environment Variables Reach the Container

```
GitHub Secrets
    │
    ▼
deploy.yml runner (export SPOTIFY_CLIENT_ID=...)
    │
    ▼
aws_manager.py deploy (reads os.environ, builds -e flags)
    │
    ▼
SSM send-command → EC2
    │
    ▼
docker run -e SPOTIFY_CLIENT_ID=... -e OPENAI_API_KEY=... jemya:latest
    │
    ▼
Running container (env vars available to the app)
```

Env vars are **not persisted** on the EC2 filesystem — they live only in the running container. On redeploy, secrets are re-injected from GitHub.

---

## Infrastructure

| Component | Value |
|-----------|-------|
| EC2 instance tag | `Name=jemya-instance` |
| EC2 OS | Amazon Linux 2 |
| EC2 instance type | `t3.micro` |
| Region | `eu-west-1` |
| ECR repository | `jemya` |
| Elastic IP | `34.253.128.224` |
| Domain | `jam-ya.com` (GoDaddy DNS → Elastic IP) |
| SSL | Let's Encrypt via certbot (auto-renews daily at 03:00) |
| Reverse proxy | nginx |
| Deployment method | AWS Session Manager (no SSH) |

---

## Manual Operations

### Deploy a specific image tag
```bash
# Via GitHub Actions UI:
# Actions → Deploy to Production → Run workflow → image_tag: <sha>

# Or locally:
export SPOTIFY_CLIENT_ID=... # (all secrets)
python3 aws/aws_manager.py deploy --image-tag <tag> --deploy-only --profile jemya
```

### Check infrastructure status
```bash
python3 aws/aws_manager.py status --profile jemya
```

### Check domain / DNS / SSL status
```bash
python3 aws/aws_manager.py domain --action status --profile jemya
```

### Renew SSL certificate manually
```bash
python3 aws/aws_manager.py domain --action ssl --profile jemya
```

### SSH into the EC2 instance (via Session Manager, no key needed)
```bash
aws ssm start-session --target i-01a86512741d7221f --profile jemya --region eu-west-1
```

### View running containers on EC2
```bash
aws ssm send-command \
  --profile jemya --region eu-west-1 \
  --instance-ids i-01a86512741d7221f \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker ps"]' \
  --query 'Command.CommandId' --output text
```

---

## Troubleshooting

### CI fails — security scan
- **Bandit HIGH**: Check `bandit-report.json` artifact in the Actions run
- **Trivy CRITICAL**: Update the affected base image or package in `requirements.txt`
- **pip-audit**: Update the vulnerable package or add it to the `--ignore-vuln` list in `ci.yml`

### Deploy fails — SSM connectivity
```bash
# Verify the instance is SSM-reachable
aws ssm describe-instance-information --profile jemya --region eu-west-1
```
The EC2 instance needs:
- IAM role with `AmazonSSMManagedInstanceCore` attached
- Outbound HTTPS (port 443) to SSM endpoints (allowed by default)
- SSM agent running (`systemctl status amazon-ssm-agent`)

### Deploy fails — image not found in ECR
The deploy workflow expects the image to already be in ECR. Run the CI workflow first (push to `main`), then trigger deploy.

### Application not responding after deploy
```bash
# Check container logs via SSM
aws ssm send-command \
  --profile jemya --region eu-west-1 \
  --instance-ids i-01a86512741d7221f \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo docker logs jemya-blue 2>&1 || sudo docker logs jemya-green 2>&1"]' \
  --query 'Command.CommandId' --output text
```

### SSL certificate expired / certbot failed
```bash
python3 aws/aws_manager.py domain --action ssl --profile jemya
```
Certbot auto-renewal is set up as a cron job (`0 3 * * *`) on the EC2 instance. If it keeps failing, check that port 80 is open and DNS still resolves to `34.253.128.224`.
