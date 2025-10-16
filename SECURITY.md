# 🔒 Security Setup Guide

## Overview
This document outlines the security measures in place to prevent accidental commits of secrets and sensitive data.

## 🛡️ Protection Layers

### 1. `.gitignore` Protection
Files and patterns that are automatically ignored:

```bash
# Configuration with secrets
conf.py

# Environment files  
.env*

# AWS secrets and credentials
*.pem
*.key
*key*.pem
github-secrets.txt
ec2-instance-info.txt
ec2-elastic-ip-info.txt
aws-credentials.txt
*-credentials.*
*-secrets.*

# Sensitive directories
**/credentials/*
**/keys/*
**/secrets/*
```

### 2. Automated Security Scanning
- **Pre-commit hook**: Automatically runs before each commit
- **Security patterns detection**: Scans for AWS keys, API keys, private keys
- **Forbidden file detection**: Blocks known sensitive file patterns

### 3. Manual Security Check
Run anytime to verify no secrets are staged:
```bash
./tools/security-check.sh
```

## 🚨 What Gets Detected

### Forbidden File Patterns:
- `*.pem` - SSH private keys
- `*.key` - Any key files
- `github-secrets.txt` - GitHub secrets documentation
- `ec2-instance-info.txt` - EC2 instance details
- `*-credentials.*` - Credential files

### Sensitive Content Patterns:
- `AKIA[0-9A-Z]{16}` - AWS Access Key IDs
- `-----BEGIN.*PRIVATE KEY-----` - Private key headers
- `sk-[a-zA-Z0-9]{48}` - OpenAI API keys
- Spotify client secrets

## 📋 Best Practices

### ✅ DO:
- Use environment variables for all secrets in production
- Keep `conf.py` for local development only (already gitignored)
- Store secrets in GitHub repository secrets
- Use the security check script before important commits
- Keep sensitive files in ignored directories

### ❌ DON'T:
- Commit API keys, passwords, or tokens
- Add secret files to git tracking
- Hardcode credentials in source code
- Disable the pre-commit hook without good reason

## 🔧 Manual Override
If you need to bypass the security check (rare cases):
```bash
git commit --no-verify -m "your message"
```

⚠️ **Use with extreme caution and double-check no secrets are included!**

## 🕵️ Manual Verification Commands

### Check for sensitive patterns in all files:
```bash
grep -r "AKIA" . --exclude-dir=.git
grep -r "sk-" . --exclude-dir=.git  
grep -r "BEGIN.*PRIVATE KEY" . --exclude-dir=.git
```

### Check what files are staged for commit:
```bash
git diff --cached --name-only
```

### Check staged content for secrets:
```bash
git diff --cached | grep -E "(AKIA|sk-|BEGIN.*PRIVATE KEY)"
```

## 🚑 Emergency: Remove Secrets from Git History

If secrets were accidentally committed:

### 1. Remove from current commit (before push):
```bash
git reset HEAD~1
# Edit files to remove secrets
git add .
git commit -m "Remove secrets"
```

### 2. Remove from git history (if already pushed):
```bash
# Use git filter-branch or BFG Repo-Cleaner
# Rotate all exposed credentials immediately!
```

### 3. Rotate all exposed credentials:
- Generate new AWS access keys
- Create new API keys
- Update GitHub secrets
- Update application configuration

## 📊 Current Security Status

✅ **Active Protections:**
- Pre-commit hook installed
- Security scanning script ready
- Comprehensive .gitignore patterns
- Sensitive files already excluded

✅ **Safe Files Currently:**
- No secrets in staged files
- All sensitive files properly ignored
- Production uses environment variables only

## 🔄 Regular Maintenance

### Monthly:
- Run full repository scan: `./tools/security-check.sh`
- Review .gitignore patterns
- Update security patterns as needed

### When adding new secrets:
1. Add to environment variables (production)
2. Add to `conf.py` (local development)  
3. Update .gitignore if new file patterns needed
4. Test security check script

Remember: **Security is everyone's responsibility!** 🛡️