#!/bin/bash

# GitHub Actions IP Ranges Fetcher
# 
# This script fetches the latest GitHub Actions runner IP ranges from GitHub's meta API
# and provides them in various formats useful for AWS infrastructure configuration.
#
# Usage:
#   ./get-github-actions-ips.sh            # Show all formats
#   ./get-github-actions-ips.sh --ipv4     # IPv4 ranges only
#   ./get-github-actions-ips.sh --ipv6     # IPv6 ranges only
#   ./get-github-actions-ips.sh --aws      # AWS Security Group format
#   ./get-github-actions-ips.sh --count    # Show count statistics

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

API_ENDPOINT="https://api.github.com/meta"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}🔍 GitHub Actions Runner IP Ranges${NC}"
echo "==================================="

# Fetch data from GitHub API
echo -e "${YELLOW}📡 Fetching latest data from GitHub API...${NC}"
API_DATA=$(curl -s -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28" "$API_ENDPOINT")

if [ $? -ne 0 ] || [ -z "$API_DATA" ]; then
    echo -e "${RED}❌ Failed to fetch data from GitHub API${NC}"
    exit 1
fi

# Extract IPv4 and IPv6 ranges
IPV4_RANGES=$(echo "$API_DATA" | jq -r '.actions[]' | grep -E '^[0-9]+\.' | sort)
IPV6_RANGES=$(echo "$API_DATA" | jq -r '.actions[]' | grep -E '^[0-9a-f:]+:' | sort)
ALL_RANGES=$(echo "$API_DATA" | jq -r '.actions[]' | sort)

# Count statistics
IPV4_COUNT=$(echo "$IPV4_RANGES" | wc -l | tr -d ' ')
IPV6_COUNT=$(echo "$IPV6_RANGES" | wc -l | tr -d ' ')
TOTAL_COUNT=$(echo "$ALL_RANGES" | wc -l | tr -d ' ')

echo -e "${GREEN}✅ Successfully fetched IP ranges${NC}"
echo -e "${BLUE}📊 Statistics:${NC}"
echo "   • IPv4 ranges: $IPV4_COUNT"
echo "   • IPv6 ranges: $IPV6_COUNT"  
echo "   • Total ranges: $TOTAL_COUNT"
echo ""

# Save ranges to files
echo "$IPV4_RANGES" > "$SCRIPT_DIR/github-actions-ipv4-ranges.txt"
echo "$IPV6_RANGES" > "$SCRIPT_DIR/github-actions-ipv6-ranges.txt"
echo "$ALL_RANGES" > "$SCRIPT_DIR/github-actions-all-ranges.txt"

# Parse command line arguments
case "${1:-}" in
    --ipv4)
        echo -e "${BLUE}📋 IPv4 Ranges (${IPV4_COUNT} total):${NC}"
        echo "$IPV4_RANGES"
        ;;
    --ipv6)
        echo -e "${BLUE}📋 IPv6 Ranges (${IPV6_COUNT} total):${NC}"
        echo "$IPV6_RANGES"
        ;;
    --aws)
        echo -e "${BLUE}☁️  AWS Security Group Format:${NC}"
        echo "# Add these to your AWS Security Group rules for GitHub Actions access"
        echo "# Protocol: HTTPS (443) or HTTP (80) depending on your needs"
        echo ""
        echo "# IPv4 Rules:"
        echo "$IPV4_RANGES" | while read -r range; do
            [ -n "$range" ] && echo "aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX --protocol tcp --port 443 --cidr $range"
        done
        echo ""
        echo "# IPv6 Rules:"
        echo "$IPV6_RANGES" | while read -r range; do
            [ -n "$range" ] && echo "aws ec2 authorize-security-group-ingress --group-id sg-XXXXXXXX --protocol tcp --port 443 --ipv6-cidr $range"
        done
        ;;
    --count)
        echo -e "${BLUE}📊 Detailed Statistics:${NC}"
        echo "   • IPv4 ranges: $IPV4_COUNT"
        echo "   • IPv6 ranges: $IPV6_COUNT"
        echo "   • Total ranges: $TOTAL_COUNT"
        echo ""
        echo -e "${BLUE}📁 Files created:${NC}"
        echo "   • $SCRIPT_DIR/github-actions-ipv4-ranges.txt"
        echo "   • $SCRIPT_DIR/github-actions-ipv6-ranges.txt"
        echo "   • $SCRIPT_DIR/github-actions-all-ranges.txt"
        ;;
    *)
        echo -e "${BLUE}📋 All GitHub Actions IP Ranges:${NC}"
        echo ""
        echo -e "${YELLOW}IPv4 Ranges (${IPV4_COUNT} total):${NC}"
        echo "$IPV4_RANGES" | head -10
        [ "$IPV4_COUNT" -gt 10 ] && echo "... ($(($IPV4_COUNT - 10)) more ranges)"
        echo ""
        echo -e "${YELLOW}IPv6 Ranges (${IPV6_COUNT} total):${NC}"
        echo "$IPV6_RANGES" | head -10
        [ "$IPV6_COUNT" -gt 10 ] && echo "... ($(($IPV6_COUNT - 10)) more ranges)"
        echo ""
        echo -e "${BLUE}💡 Usage Examples:${NC}"
        echo "   $0 --ipv4     # Show IPv4 ranges only"
        echo "   $0 --ipv6     # Show IPv6 ranges only"
        echo "   $0 --aws      # AWS Security Group commands"
        echo "   $0 --count    # Show statistics and file locations"
        echo ""
        echo -e "${BLUE}📁 Files saved:${NC}"
        echo "   • github-actions-ipv4-ranges.txt (IPv4 only)"
        echo "   • github-actions-ipv6-ranges.txt (IPv6 only)"
        echo "   • github-actions-all-ranges.txt (all ranges)"
        ;;
esac

echo ""
echo -e "${GREEN}🎯 Use these IP ranges to configure your AWS Security Groups, firewalls,${NC}"
echo -e "${GREEN}   or other network access controls for GitHub Actions runners.${NC}"
echo ""
echo -e "${YELLOW}⚠️  Note: These IP ranges are updated regularly by GitHub.${NC}"
echo -e "${YELLOW}   Run this script periodically to get the latest ranges.${NC}"