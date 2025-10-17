#!/bin/bash

# 🔐 Dual Security Group SSH Access Setup
# 
# This script creates and manages two separate security groups:
# 1. jemya-github-sg: For GitHub Actions runner access only
# 2. jemya-admin-sg: For admin/developer access only
#
# It also automatically applies these security groups to your EC2 instance.
#
# Benefits:
# - Better security isolation
# - Easier management and auditing
# - Can be applied independently to different resources
# - Clear separation of concerns
#
# Usage:
#   ./setup-dual-ssh-security.sh                    # Interactive setup
#   ./setup-dual-ssh-security.sh --auto             # Auto setup and apply
#   ./setup-dual-ssh-security.sh --update-github    # Update GitHub IPs only

# Configuration
AWS_REGION="${AWS_REGION:-eu-west-1}"
#   ./setup-dual-ssh-security.sh --update-admin     # Update admin IPs only

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_SG_NAME="jemya-github-sg"
ADMIN_SG_NAME="jemya-admin-sg"
SSH_PORT=22
AUTO_MODE=false
UPDATE_GITHUB_ONLY=false
UPDATE_ADMIN_ONLY=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --auto)
            AUTO_MODE=true
            shift
            ;;
        --update-github)
            UPDATE_GITHUB_ONLY=true
            shift
            ;;
        --update-admin)
            UPDATE_ADMIN_ONLY=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "OPTIONS:"
            echo "  --auto             Automatic setup (no prompts)"
            echo "  --update-github    Update GitHub Actions IPs only"
            echo "  --update-admin     Update admin IPs only"
            echo "  --help             Show this help message"
            echo ""
            echo "Security Groups Created:"
            echo "  $GITHUB_SG_NAME    GitHub Actions runners only"
            echo "  $ADMIN_SG_NAME      Admin/developer access only"
            echo ""
            echo "Examples:"
            echo "  $0                      # Interactive setup"
            echo "  $0 --auto              # Auto setup both groups"
            echo "  $0 --update-github     # Update GitHub IPs only"
            echo "  $0 --update-admin      # Update admin IPs only"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${CYAN}🔐 Dual Security Group SSH Access Setup${NC}"
echo "========================================"
echo ""

# Check prerequisites
echo -e "${BLUE}🔍 Checking Prerequisites${NC}"
echo "-------------------------"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ AWS CLI installed${NC}"

if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured!${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✅ AWS credentials configured (Account: $AWS_ACCOUNT_ID)${NC}"

if ! command -v jq &> /dev/null; then
    echo -e "${RED}❌ jq not found! Please install jq${NC}"
    exit 1
fi
echo -e "${GREEN}✅ jq installed${NC}"

echo ""

# Get VPC ID (use default VPC)
echo -e "${BLUE}🌐 Finding VPC${NC}"
echo "-------------"

VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION" 2>/dev/null || echo "None")

if [ "$VPC_ID" = "None" ] || [ "$VPC_ID" = "null" ]; then
    # Get any VPC if no default
    VPC_ID=$(aws ec2 describe-vpcs --query 'Vpcs[0].VpcId' --output text --region "$AWS_REGION" 2>/dev/null || echo "None")
    
    if [ "$VPC_ID" = "None" ] || [ "$VPC_ID" = "null" ]; then
        echo -e "${RED}❌ No VPC found!${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✅ Using VPC: $VPC_ID${NC}"

# Function to create or get security group
create_or_get_sg() {
    local sg_name="$1"
    local description="$2"
    
    echo -e "${BLUE}🔍 Checking security group: $sg_name${NC}"
    
    # Check if security group exists
    sg_id=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$sg_name" \
        --query 'SecurityGroups[0].GroupId' \
        --output text --region "$AWS_REGION" 2>/dev/null || echo "None")
    
    if [ "$sg_id" = "None" ] || [ "$sg_id" = "null" ]; then
        echo -e "${YELLOW}📝 Creating security group: $sg_name${NC}"
        
        sg_id=$(aws ec2 create-security-group \
            --group-name "$sg_name" \
            --description "$description" \
            --vpc-id "$VPC_ID" \
            --query 'GroupId' \
            --output text --region "$AWS_REGION")
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ Created security group: $sg_id ($sg_name)${NC}"
            
            # Add tags
            aws ec2 create-tags \
                --resources "$sg_id" \
                --tags Key=Name,Value="$sg_name" Key=Project,Value="Jemya" Key=Purpose,Value="SSH-Access" \
                --region "$AWS_REGION" 2>/dev/null || true
        else
            echo -e "${RED}❌ Failed to create security group: $sg_name${NC}"
            exit 1
        fi
    else
        echo -e "${GREEN}✅ Found existing security group: $sg_id ($sg_name)${NC}"
    fi
    
    echo "$sg_id"
}

# Function to clear SSH rules from security group
clear_ssh_rules() {
    local sg_id="$1"
    local sg_name="$2"
    
    echo -e "${YELLOW}🧹 Clearing existing SSH rules from $sg_name${NC}"
    
    # Get current SSH rules using simpler approach
    local existing_cidrs=$(aws ec2 describe-security-groups \
        --group-ids "$sg_id" \
        --region "$AWS_REGION" \
        --query "SecurityGroups[0].IpPermissions[?FromPort==\`$SSH_PORT\`].IpRanges[].CidrIp" \
        --output text 2>/dev/null)
    
    if [ -n "$existing_cidrs" ] && [ "$existing_cidrs" != "None" ]; then
        echo "$existing_cidrs" | tr '\t' '\n' | while read -r cidr; do
            if [ -n "$cidr" ] && [ "$cidr" != "None" ]; then
                aws ec2 revoke-security-group-ingress \
                    --group-id "$sg_id" \
                    --protocol tcp \
                    --port "$SSH_PORT" \
                    --cidr "$cidr" \
                    --region "$AWS_REGION" \
                    2>/dev/null && echo "   🗑️  Removed: $cidr" || echo "   ⚠️  Failed to remove: $cidr"
            fi
        done
        echo -e "${GREEN}✅ Cleared SSH rules from $sg_name${NC}"
    else
        echo -e "${BLUE}ℹ️  No SSH rules to clear in $sg_name${NC}"
    fi
}

# Function to add SSH rules to security group
add_ssh_rules() {
    local sg_id="$1"
    local sg_name="$2"
    local description_prefix="$3"
    shift 3
    local ip_ranges=("$@")
    
    echo -e "${YELLOW}➕ Adding SSH rules to $sg_name${NC}"
    
    for ip in "${ip_ranges[@]}"; do
        aws ec2 authorize-security-group-ingress \
            --group-id "$sg_id" \
            --protocol tcp \
            --port "$SSH_PORT" \
            --cidr "$ip" \
            --region "$AWS_REGION" \
            2>/dev/null && echo "   ✅ Added: $ip" || echo "   ⚠️  Failed/exists: $ip"
    done
}

# Setup GitHub Actions security group
setup_github_sg() {
    if [ "$UPDATE_ADMIN_ONLY" = true ]; then
        return
    fi
    
    echo ""
    echo -e "${MAGENTA}🤖 Setting up GitHub Actions Security Group${NC}"
    echo "============================================="
    
    GITHUB_SG_ID=$(create_or_get_sg "$GITHUB_SG_NAME" "SSH access for GitHub Actions runners - Jemya project")
    
    # Fetch GitHub Actions IP ranges
    echo -e "${BLUE}📡 Fetching GitHub Actions IP ranges${NC}"
    
    if [ -f "$SCRIPT_DIR/get-github-actions-ips.sh" ]; then
        "$SCRIPT_DIR/get-github-actions-ips.sh" --count > /dev/null
        
        if [ -f "$SCRIPT_DIR/github-actions-ipv4-ranges.txt" ]; then
            # Use while loop for better compatibility instead of readarray
            GITHUB_IPS=()
            while IFS= read -r line; do
                GITHUB_IPS+=("$line")
            done < "$SCRIPT_DIR/github-actions-ipv4-ranges.txt"
            echo -e "${GREEN}✅ Loaded ${#GITHUB_IPS[@]} GitHub Actions IPv4 ranges${NC}"
        else
            echo -e "${RED}❌ Failed to load GitHub Actions IP ranges${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠️  Fetching GitHub Actions IPs manually...${NC}"
        # Use while loop for better compatibility instead of readarray
        GITHUB_IPS=()
        while IFS= read -r line; do
            GITHUB_IPS+=("$line")
        done < <(curl -s -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            https://api.github.com/meta | \
            jq -r '.actions[]' | \
            grep -E '^[0-9]+\.' | \
            sort)
    fi
    
    # Print original statistics
    echo -e "${CYAN}📊 Original GitHub Actions IP Statistics:${NC}"
    echo "   • Total IP ranges: ${#GITHUB_IPS[@]}"
    
    # Analyze CIDR distribution
    original_16=$(printf '%s\n' "${GITHUB_IPS[@]}" | grep -c '/16$' 2>/dev/null || echo 0)
    original_17=$(printf '%s\n' "${GITHUB_IPS[@]}" | grep -c '/17$' 2>/dev/null || echo 0)
    original_18=$(printf '%s\n' "${GITHUB_IPS[@]}" | grep -c '/18$' 2>/dev/null || echo 0)
    original_other=$(( ${#GITHUB_IPS[@]} - original_16 - original_17 - original_18 ))
    
    echo "   • /16 blocks: $original_16"
    echo "   • /17 blocks: $original_17" 
    echo "   • /18 blocks: $original_18"
    echo "   • Other blocks: $original_other"
    echo ""
    
    # Optimize GitHub IPs using largest CIDR blocks for maximum coverage with minimum rules
    echo -e "${BLUE}🎯 Optimizing IP ranges for maximum coverage...${NC}"
    
    # Create optimized list prioritizing largest CIDR blocks (/16, /17, /18)
    OPTIMIZED_IPS=()
    
    # Add /16 blocks (65,536 IPs each) - highest priority
    while IFS= read -r ip; do
        if [[ "$ip" =~ /16$ ]]; then
            OPTIMIZED_IPS+=("$ip")
        fi
    done < <(printf '%s\n' "${GITHUB_IPS[@]}")
    
    # Add /17 blocks (32,768 IPs each) - high priority
    while IFS= read -r ip; do
        if [[ "$ip" =~ /17$ ]]; then
            OPTIMIZED_IPS+=("$ip")
        fi
    done < <(printf '%s\n' "${GITHUB_IPS[@]}")
    
    # Add /18 blocks (16,384 IPs each) - medium priority
    while IFS= read -r ip; do
        if [[ "$ip" =~ /18$ ]]; then
            OPTIMIZED_IPS+=("$ip")
        fi
    done < <(printf '%s\n' "${GITHUB_IPS[@]}")
    
    # Limit to AWS security group limits (max ~60 rules)
    MAX_GITHUB_IPS=50
    if [ ${#OPTIMIZED_IPS[@]} -gt $MAX_GITHUB_IPS ]; then
        echo -e "${YELLOW}⚠️  Limiting to $MAX_GITHUB_IPS optimized GitHub Actions IPs (AWS security group limits)${NC}"
        OPTIMIZED_IPS=("${OPTIMIZED_IPS[@]:0:$MAX_GITHUB_IPS}")
    fi
    
    # Calculate coverage
    ip_16_count=$(printf '%s\n' "${OPTIMIZED_IPS[@]}" | grep -c '/16$' 2>/dev/null || echo 0)
    ip_17_count=$(printf '%s\n' "${OPTIMIZED_IPS[@]}" | grep -c '/17$' 2>/dev/null || echo 0)
    ip_18_count=$(printf '%s\n' "${OPTIMIZED_IPS[@]}" | grep -c '/18$' 2>/dev/null || echo 0)
    
    # Ensure variables are numbers
    ip_16_count=${ip_16_count:-0}
    ip_17_count=${ip_17_count:-0}
    ip_18_count=${ip_18_count:-0}
    
    total_ips=$(( (ip_16_count * 65536) + (ip_17_count * 32768) + (ip_18_count * 16384) ))
    
    echo -e "${GREEN}📊 Optimization Results:${NC}"
    echo -e "${YELLOW}   BEFORE OPTIMIZATION:${NC}"
    echo "   • Total ranges: ${#GITHUB_IPS[@]}"
    echo "   • Rules needed: ${#GITHUB_IPS[@]}"
    echo ""
    echo -e "${GREEN}   AFTER OPTIMIZATION:${NC}"
    echo "   • /16 blocks: $ip_16_count ($(( ip_16_count * 65536 )) IPs)"
    echo "   • /17 blocks: $ip_17_count ($(( ip_17_count * 32768 )) IPs)"
    echo "   • /18 blocks: $ip_18_count ($(( ip_18_count * 16384 )) IPs)"
    echo "   • Total coverage: $total_ips IP addresses"
    echo "   • Rules used: ${#OPTIMIZED_IPS[@]} out of $MAX_GITHUB_IPS"
    echo ""
    echo -e "${CYAN}   EFFICIENCY GAIN:${NC}"
    if [ ${#GITHUB_IPS[@]} -gt 0 ] && [ ${#OPTIMIZED_IPS[@]} -gt 0 ]; then
        reduction_percent=$(( (${#GITHUB_IPS[@]} - ${#OPTIMIZED_IPS[@]}) * 100 / ${#GITHUB_IPS[@]} ))
        coverage_per_rule=$(( total_ips / ${#OPTIMIZED_IPS[@]} ))
        echo "   • Rules reduction: ${#GITHUB_IPS[@]} → ${#OPTIMIZED_IPS[@]} (-$reduction_percent%)"
        echo "   • Coverage per rule: $coverage_per_rule IPs/rule"
    else
        echo "   • Unable to calculate efficiency (empty arrays)"
    fi
    echo "   • /17 blocks: $ip_17_count ($(( ip_17_count * 32768 )) IPs)"
    echo "   • /18 blocks: $ip_18_count ($(( ip_18_count * 16384 )) IPs)"
    echo "   • Total coverage: $total_ips IP addresses"
    echo "   • Rules used: ${#OPTIMIZED_IPS[@]} out of $MAX_GITHUB_IPS"
    
    # Clear existing rules and add optimized ones
    clear_ssh_rules "$GITHUB_SG_ID" "$GITHUB_SG_NAME"
    add_ssh_rules "$GITHUB_SG_ID" "$GITHUB_SG_NAME" "GitHub Actions" "${OPTIMIZED_IPS[@]}"
    
    echo -e "${GREEN}✅ GitHub Actions security group configured with ${#OPTIMIZED_IPS[@]} optimized IP ranges${NC}"
    echo -e "${BLUE}📋 Group ID: $GITHUB_SG_ID${NC}"
}

# Setup Admin security group  
setup_admin_sg() {
    if [ "$UPDATE_GITHUB_ONLY" = true ]; then
        return
    fi
    
    echo ""
    echo -e "${MAGENTA}👤 Setting up Admin Security Group${NC}"
    echo "=================================="
    
    ADMIN_SG_ID=$(create_or_get_sg "$ADMIN_SG_NAME" "SSH access for administrators and developers - Jemya project")
    
    # Get current public IP
    echo -e "${BLUE}🌐 Detecting your current IP${NC}"
    YOUR_IP=$(curl -s https://ifconfig.me 2>/dev/null || curl -s https://ipinfo.io/ip 2>/dev/null || echo "unknown")
    
    ADMIN_IPS=()
    
    if [ "$YOUR_IP" != "unknown" ]; then
        echo -e "${GREEN}✅ Your current public IP: $YOUR_IP${NC}"
        
        if [ "$AUTO_MODE" = false ]; then
            read -p "Add your current IP ($YOUR_IP) to admin access? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                ADMIN_IPS+=("$YOUR_IP/32")
            fi
        else
            ADMIN_IPS+=("$YOUR_IP/32")
            echo -e "${GREEN}✅ Auto-added your current IP${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Could not detect your current IP${NC}"
    fi
    
    # Allow adding additional admin IPs
    if [ "$AUTO_MODE" = false ] && [ ${#ADMIN_IPS[@]} -gt 0 ]; then
        echo ""
        echo -e "${BLUE}Would you like to add additional admin IP addresses?${NC}"
        while true; do
            read -p "Enter admin IP (or press Enter to continue): " admin_ip
            if [ -z "$admin_ip" ]; then
                break
            fi
            
            # Validate IP format (basic)
            if [[ "$admin_ip" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
                ADMIN_IPS+=("$admin_ip/32")
                echo -e "${GREEN}✅ Added admin IP: $admin_ip${NC}"
            else
                echo -e "${RED}❌ Invalid IP format: $admin_ip${NC}"
            fi
        done
    fi
    
    if [ ${#ADMIN_IPS[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No admin IPs configured. You may not be able to SSH to your instances.${NC}"
        if [ "$AUTO_MODE" = false ]; then
            read -p "Continue anyway? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 0
            fi
        fi
    else
        # Clear existing rules and add new ones
        clear_ssh_rules "$ADMIN_SG_ID" "$ADMIN_SG_NAME"
        add_ssh_rules "$ADMIN_SG_ID" "$ADMIN_SG_NAME" "Admin" "${ADMIN_IPS[@]}"
        
        echo -e "${GREEN}✅ Admin security group configured with ${#ADMIN_IPS[@]} IP(s)${NC}"
    fi
    
    echo -e "${BLUE}📋 Group ID: $ADMIN_SG_ID${NC}"
}

# Update EC2 instance with new security groups
update_instance_security_groups() {
    echo ""
    echo -e "${MAGENTA}🔄 Updating EC2 Instance Security Groups${NC}"
    echo "========================================"
    
    # Auto-discover Jemya instance (same logic as deployment workflow)
    echo -e "${BLUE}🔍 Auto-discovering Jemya EC2 instance...${NC}"
    
    INSTANCE_INFO=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=jemya-instance" \
                  "Name=instance-state-name,Values=running,stopped" \
        --query 'Reservations[0].Instances[0].[InstanceId,Tags[?Key==`Name`].Value|[0],State.Name]' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "None	None	None")
    
    if [ "$INSTANCE_INFO" = "None	None	None" ] || [ -z "$INSTANCE_INFO" ]; then
        echo -e "${YELLOW}⚠️  No Jemya EC2 instance found!${NC}"
        echo -e "${BLUE}💡 Make sure your EC2 instance is tagged with Name=jemya-instance${NC}"
        echo -e "${BLUE}💡 You can apply security groups manually later${NC}"
        return 0
    fi
    
    # Parse instance info
    INSTANCE_ID=$(echo "$INSTANCE_INFO" | cut -d$'\t' -f1)
    INSTANCE_NAME=$(echo "$INSTANCE_INFO" | cut -d$'\t' -f2)
    INSTANCE_STATE=$(echo "$INSTANCE_INFO" | cut -d$'\t' -f3)
    
    echo -e "${GREEN}✅ Found Jemya EC2 instance:${NC}"
    echo "   📦 Instance ID: $INSTANCE_ID"
    echo "   🏷️  Name: $INSTANCE_NAME"
    echo "   🔄 State: $INSTANCE_STATE"
    
    # Get current security groups
    echo ""
    echo -e "${BLUE}📋 Current Security Groups${NC}"
    echo "-------------------------"
    
    CURRENT_SGS=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].SecurityGroups[].{GroupId:GroupId,GroupName:GroupName}' \
        --output json --region "$AWS_REGION")
    
    echo "$CURRENT_SGS" | jq -r '.[] | "   🛡️  " + .GroupId + " (" + .GroupName + ")"'
    
    # Build new security group list
    echo ""
    echo -e "${BLUE}🔧 Building New Security Group List${NC}"
    echo "-----------------------------------"
    
    NEW_SGS=()
    
    # Add GitHub and Admin security groups if they were created/updated
    if [ "$UPDATE_ADMIN_ONLY" = false ] && [ -n "${GITHUB_SG_ID:-}" ]; then
        NEW_SGS+=("$GITHUB_SG_ID")
        echo -e "${GREEN}✅ Added: $GITHUB_SG_ID ($GITHUB_SG_NAME)${NC}"
    fi
    
    if [ "$UPDATE_GITHUB_ONLY" = false ] && [ -n "${ADMIN_SG_ID:-}" ]; then
        NEW_SGS+=("$ADMIN_SG_ID")
        echo -e "${GREEN}✅ Added: $ADMIN_SG_ID ($ADMIN_SG_NAME)${NC}"
    fi
    
    # Keep existing non-SSH security groups (exclude old jemya-sg)
    echo "$CURRENT_SGS" | jq -r '.[] | select(.GroupName != "jemya-sg") | .GroupId' | while read -r sg_id; do
        if [ "$sg_id" != "${GITHUB_SG_ID:-}" ] && [ "$sg_id" != "${ADMIN_SG_ID:-}" ]; then
            NEW_SGS+=("$sg_id")
            sg_name=$(echo "$CURRENT_SGS" | jq -r '.[] | select(.GroupId == "'"$sg_id"'") | .GroupName')
            echo -e "${BLUE}ℹ️  Keeping: $sg_id ($sg_name)${NC}"
        fi
    done
    
    # Remove duplicates
    NEW_SGS=($(printf "%s\n" "${NEW_SGS[@]}" | sort -u))
    
    if [ ${#NEW_SGS[@]} -eq 0 ]; then
        echo -e "${YELLOW}⚠️  No security groups to apply${NC}"
        return 0
    fi
    
    echo ""
    echo -e "${BLUE}📊 Summary:${NC}"
    echo "   • New security groups: ${#NEW_SGS[@]}"
    echo "   • Groups: ${NEW_SGS[*]}"
    
    if [ "$AUTO_MODE" = false ]; then
        echo ""
        read -p "Apply these security group changes to $INSTANCE_ID? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}Skipping instance update${NC}"
            return 0
        fi
    fi
    
    # Apply security group changes
    echo ""
    echo -e "${BLUE}🔄 Updating Instance Security Groups${NC}"
    echo "------------------------------------"
    
    # Convert array to space-separated string
    SG_LIST=$(IFS=' '; echo "${NEW_SGS[*]}")
    
    aws ec2 modify-instance-attribute \
        --instance-id "$INSTANCE_ID" \
        --groups $SG_LIST \
        --region "$AWS_REGION"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Successfully updated security groups${NC}"
        
        # Verify changes
        echo ""
        echo -e "${BLUE}🔍 Verifying Changes${NC}"
        echo "-------------------"
        
        sleep 2  # Wait for changes to propagate
        
        UPDATED_SGS=$(aws ec2 describe-instances \
            --instance-ids "$INSTANCE_ID" \
            --query 'Reservations[0].Instances[0].SecurityGroups[].{GroupId:GroupId,GroupName:GroupName}' \
            --output json --region "$AWS_REGION")
        
        echo -e "${GREEN}✅ Updated security groups:${NC}"
        echo "$UPDATED_SGS" | jq -r '.[] | "   🛡️  " + .GroupId + " (" + .GroupName + ")"'
    else
        echo -e "${RED}❌ Failed to update security groups${NC}"
        echo -e "${YELLOW}💡 You can apply them manually later${NC}"
    fi
}

# Main execution
if [ "$UPDATE_GITHUB_ONLY" = false ] && [ "$UPDATE_ADMIN_ONLY" = false ]; then
    echo -e "${BLUE}This will create two separate security groups:${NC}"
    echo "  🤖 $GITHUB_SG_NAME - For GitHub Actions runners only"
    echo "  👤 $ADMIN_SG_NAME - For admin/developer access only"
    echo ""
fi

setup_github_sg
setup_admin_sg

# Update EC2 instance if security groups were created/updated
if [ "$UPDATE_GITHUB_ONLY" = false ] || [ "$UPDATE_ADMIN_ONLY" = false ]; then
    update_instance_security_groups
fi

echo ""
echo -e "${GREEN}🎉 Dual Security Group Setup Complete!${NC}"
echo "======================================="
echo ""

# Show final summary
echo -e "${BLUE}📋 Security Groups Created:${NC}"

if [ "$UPDATE_ADMIN_ONLY" = false ]; then
    echo ""
    echo -e "${MAGENTA}🤖 GitHub Actions Security Group:${NC}"
    echo "   Name: $GITHUB_SG_NAME"
    echo "   ID: ${GITHUB_SG_ID:-"(not updated)"}"
    echo "   Purpose: CI/CD deployment access"
    echo "   IPs: GitHub Actions runner ranges"
fi

if [ "$UPDATE_GITHUB_ONLY" = false ]; then
    echo ""
    echo -e "${MAGENTA}👤 Admin Security Group:${NC}"
    echo "   Name: $ADMIN_SG_NAME"
    echo "   ID: ${ADMIN_SG_ID:-"(not updated)"}"
    echo "   Purpose: Developer/admin access"
    echo "   IPs: Admin IP addresses"
fi

echo ""
echo -e "${GREEN}🎉 Dual Security Group Setup Complete!${NC}"
echo "======================================="
echo ""

# Show final summary
echo -e "${BLUE}📋 Security Groups Created:${NC}"

if [ "$UPDATE_ADMIN_ONLY" = false ]; then
    echo ""
    echo -e "${MAGENTA}🤖 GitHub Actions Security Group:${NC}"
    echo "   Name: $GITHUB_SG_NAME"
    echo "   ID: ${GITHUB_SG_ID:-"(not updated)"}"
    echo "   Purpose: CI/CD deployment access"
    echo "   IPs: GitHub Actions runner ranges"
fi

if [ "$UPDATE_GITHUB_ONLY" = false ]; then
    echo ""
    echo -e "${MAGENTA}👤 Admin Security Group:${NC}"
    echo "   Name: $ADMIN_SG_NAME"
    echo "   ID: ${ADMIN_SG_ID:-"(not updated)"}"
    echo "   Purpose: Developer/admin access"
    echo "   IPs: Admin IP addresses"
fi

echo ""
echo -e "${GREEN}✅ Benefits of this setup:${NC}"
echo "   • Better security isolation"
echo "   • Easier management and auditing"
echo "   • Independent control over access types"
echo "   • Clear separation of concerns"
echo "   • Automatic application to EC2 instance"
echo "   • Can attach groups individually to different resources"

echo ""
echo -e "${CYAN}💡 Management Commands:${NC}"
echo "   • Update GitHub IPs: $0 --update-github"
echo "   • Update admin IPs: $0 --update-admin" 
echo "   • Full auto setup: $0 --auto"