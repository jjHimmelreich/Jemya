#!/bin/bash
# 🔒 Pre-commit Security Check for Jemya
# Prevents accidental commit of secrets and sensitive files

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔒 Running security check before commit...${NC}"

# Files that should NEVER be committed
FORBIDDEN_FILES=(
    "*.pem"
    "*.key" 
    "*key*.pem"
    "github-secrets.txt"
    "ec2-instance-info.txt"
    "ec2-elastic-ip-info.txt"
    "aws-credentials.txt"
    "*-credentials.*"
    "*-secrets.*"
    "conf.py"
)

# Sensitive patterns that should not appear in committed files
FORBIDDEN_PATTERNS=(
    "AKIA[0-9A-Z]{16}"              # AWS Access Key ID
    "[A-Za-z0-9/+=]{40}"            # AWS Secret Key (basic check)
    "-----BEGIN.*PRIVATE KEY-----"   # Private keys
    "sk-[a-zA-Z0-9]{48}"           # OpenAI API keys
    "SPOTIFY_CLIENT_SECRET.*=.*['\"][^'\"]{32}"  # Spotify secrets
)

ISSUES_FOUND=0

echo "🔍 Checking for forbidden files..."

# Check for forbidden file patterns in staged files
for pattern in "${FORBIDDEN_FILES[@]}"; do
    if git diff --cached --name-only | grep -q "$pattern" 2>/dev/null; then
        echo -e "${RED}❌ Forbidden file pattern found: $pattern${NC}"
        git diff --cached --name-only | grep "$pattern"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
done

echo "🔍 Checking for sensitive patterns in staged content..."

# Check for sensitive patterns in staged file content
for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    if git diff --cached | grep -E "$pattern" >/dev/null 2>&1; then
        echo -e "${RED}❌ Sensitive pattern detected: $pattern${NC}"
        echo -e "${YELLOW}Files containing sensitive data:${NC}"
        git diff --cached --name-only -z | xargs -0 grep -l "$pattern" 2>/dev/null || true
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
done

# Check if conf.py exists and warn
if [ -f "conf.py" ]; then
    echo -e "${YELLOW}⚠️  conf.py exists - make sure it's in .gitignore${NC}"
    if git ls-files --error-unmatch conf.py >/dev/null 2>&1; then
        echo -e "${RED}❌ conf.py is tracked by git! This contains secrets!${NC}"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
fi

# Summary
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ Security check passed - no secrets detected${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}🚨 SECURITY ISSUES FOUND: $ISSUES_FOUND${NC}"
    echo -e "${YELLOW}📋 To fix:${NC}"
    echo "1. Remove sensitive files from staging: git reset HEAD <file>"
    echo "2. Add files to .gitignore"
    echo "3. Remove sensitive content from files"
    echo "4. Use environment variables for secrets"
    echo ""
    echo -e "${RED}❌ COMMIT BLOCKED for security${NC}"
    exit 1
fi