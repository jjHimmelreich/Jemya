#!/bin/bash
# 🧹 AWS Infrastructure Cleanup Script for Jemya
# 
# This script safely removes all AWS resources created for Jemya project
# USE WITH CAUTION: This will delete your infrastructure!
#
# Usage:
#   ./cleanup-infrastructure.sh                    # Interactive mode with confirmations
#   ./cleanup-infrastructure.sh --force           # Non-interactive mode (dangerous!)
#   ./cleanup-infrastructure.sh --dry-run         # Show what would be deleted without doing it

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="jemya"
AWS_REGION="eu-west-1"
ECR_REPOSITORY="jemya"

# Flags
FORCE_MODE=false
DRY_RUN=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --force     Skip all confirmations (DANGEROUS!)"
            echo "  --dry-run   Show what would be deleted without actually deleting"
            echo "  --help      Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Helper functions
log_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_section() {
    echo -e "\n${MAGENTA}🔧 $1${NC}"
    echo "================================================"
}

confirm_action() {
    local message="$1"
    if [ "$FORCE_MODE" = true ]; then
        log_warning "FORCE MODE: $message"
        return 0
    fi
    
    echo -e "${YELLOW}❓ $message${NC}"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Skipped by user"
        return 1
    fi
    return 0
}

execute_command() {
    local cmd="$1"
    local description="$2"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would execute: $cmd"
        return 0
    fi
    
    log_info "$description"
    if eval "$cmd"; then
        log_success "$description - Done"
        return 0
    else
        log_error "$description - Failed"
        return 1
    fi
}

# Check AWS CLI
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS CLI not configured or credentials invalid."
        exit 1
    fi
    
    log_success "AWS CLI is configured and working"
}

# Show warning
show_warning() {
    echo -e "${RED}"
    echo "⚠️  ⚠️  ⚠️  DANGER ZONE ⚠️  ⚠️  ⚠️"
    echo ""
    echo "This script will DELETE the following AWS resources:"
    echo "• EC2 instances tagged with Name=jemya-instance"
    echo "• ECR repository: $ECR_REPOSITORY"
    echo "• IAM user: jemya-deployment-user (and access keys)"
    echo "• IAM policies: JemyaGitHubActionsECRPolicy, JemyaGitHubActionsAWSPolicy"
    echo "• Security groups: jemya-sg"
    echo "• Key pairs: jemya-key-*"
    echo ""
    echo "⚠️  THIS CANNOT BE UNDONE! ⚠️"
    echo -e "${NC}"
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "DRY RUN MODE: No resources will actually be deleted"
        return 0
    fi
    
    if [ "$FORCE_MODE" = false ]; then
        echo -e "${YELLOW}Type 'DELETE' to confirm you want to proceed:${NC}"
        read -r confirmation
        if [ "$confirmation" != "DELETE" ]; then
            log_info "Cleanup cancelled by user"
            exit 0
        fi
    fi
}

# Cleanup EC2 instances
cleanup_ec2_instances() {
    log_section "Cleaning up EC2 Instances"
    
    # Find EC2 instances
    local instances=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=jemya-instance" \
                  "Name=instance-state-name,Values=running,stopped,stopping" \
        --query 'Reservations[].Instances[].InstanceId' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || true)
    
    if [ -z "$instances" ] || [ "$instances" = "None" ]; then
        log_info "No EC2 instances found with tag Name=jemya-instance"
        return 0
    fi
    
    for instance_id in $instances; do
        if confirm_action "Terminate EC2 instance: $instance_id"; then
            execute_command \
                "aws ec2 terminate-instances --instance-ids $instance_id --region $AWS_REGION" \
                "Terminating EC2 instance: $instance_id"
        fi
    done
}

# Cleanup ECR repository
cleanup_ecr_repository() {
    log_section "Cleaning up ECR Repository"
    
    # Check if ECR repository exists
    if aws ecr describe-repositories --repository-names "$ECR_REPOSITORY" --region "$AWS_REGION" &>/dev/null; then
        if confirm_action "Delete ECR repository: $ECR_REPOSITORY (and all images)"; then
            execute_command \
                "aws ecr delete-repository --repository-name $ECR_REPOSITORY --force --region $AWS_REGION" \
                "Deleting ECR repository: $ECR_REPOSITORY"
        fi
    else
        log_info "ECR repository '$ECR_REPOSITORY' not found"
    fi
}

# Cleanup IAM resources
cleanup_iam_resources() {
    log_section "Cleaning up IAM Resources"
    
    # IAM User: jemya-deployment-user
    local iam_user="jemya-deployment-user"
    if aws iam get-user --user-name "$iam_user" &>/dev/null; then
        if confirm_action "Delete IAM user: $iam_user (and all access keys)"; then
            # Delete access keys first
            local access_keys=$(aws iam list-access-keys --user-name "$iam_user" --query 'AccessKeyMetadata[].AccessKeyId' --output text 2>/dev/null || true)
            for key in $access_keys; do
                execute_command \
                    "aws iam delete-access-key --user-name $iam_user --access-key-id $key" \
                    "Deleting access key: $key"
            done
            
            # Detach policies
            local attached_policies=$(aws iam list-attached-user-policies --user-name "$iam_user" --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null || true)
            for policy_arn in $attached_policies; do
                execute_command \
                    "aws iam detach-user-policy --user-name $iam_user --policy-arn $policy_arn" \
                    "Detaching policy: $policy_arn"
            done
            
            # Delete user
            execute_command \
                "aws iam delete-user --user-name $iam_user" \
                "Deleting IAM user: $iam_user"
        fi
    else
        log_info "IAM user '$iam_user' not found"
    fi
    
    # IAM Policies
    local policies=("JemyaGitHubActionsECRPolicy" "JemyaGitHubActionsAWSPolicy")
    for policy_name in "${policies[@]}"; do
        local policy_arn="arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/$policy_name"
        if aws iam get-policy --policy-arn "$policy_arn" &>/dev/null; then
            if confirm_action "Delete IAM policy: $policy_name"; then
                execute_command \
                    "aws iam delete-policy --policy-arn $policy_arn" \
                    "Deleting IAM policy: $policy_name"
            fi
        else
            log_info "IAM policy '$policy_name' not found"
        fi
    done
}

# Cleanup Security Groups
cleanup_security_groups() {
    log_section "Cleaning up Security Groups"
    
    local sg_name="jemya-sg"
    local sg_id=$(aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$sg_name" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || echo "None")
    
    if [ "$sg_id" != "None" ] && [ -n "$sg_id" ]; then
        if confirm_action "Delete security group: $sg_name ($sg_id)"; then
            execute_command \
                "aws ec2 delete-security-group --group-id $sg_id --region $AWS_REGION" \
                "Deleting security group: $sg_name"
        fi
    else
        log_info "Security group '$sg_name' not found"
    fi
}

# Cleanup Key Pairs
cleanup_key_pairs() {
    log_section "Cleaning up Key Pairs"
    
    local key_pairs=$(aws ec2 describe-key-pairs \
        --filters "Name=key-name,Values=jemya-key-*" \
        --query 'KeyPairs[].KeyName' \
        --output text \
        --region "$AWS_REGION" 2>/dev/null || true)
    
    if [ -z "$key_pairs" ] || [ "$key_pairs" = "None" ]; then
        log_info "No key pairs found with pattern 'jemya-key-*'"
        return 0
    fi
    
    for key_name in $key_pairs; do
        if confirm_action "Delete key pair: $key_name"; then
            execute_command \
                "aws ec2 delete-key-pair --key-name $key_name --region $AWS_REGION" \
                "Deleting key pair: $key_name"
        fi
    done
}

# Main cleanup function
main() {
    echo -e "${BLUE}"
    echo "🧹 Jemya Infrastructure Cleanup Script"
    echo "======================================"
    echo -e "${NC}"
    
    # Check prerequisites
    check_aws_cli
    
    # Show warning and get confirmation
    show_warning
    
    # Perform cleanup
    cleanup_ec2_instances
    cleanup_ecr_repository
    cleanup_iam_resources
    cleanup_security_groups
    cleanup_key_pairs
    
    # Final message
    echo -e "\n${GREEN}"
    echo "🎉 Infrastructure cleanup completed!"
    echo ""
    if [ "$DRY_RUN" = true ]; then
        echo "DRY RUN: No resources were actually deleted"
    else
        echo "All specified Jemya AWS resources have been removed"
        echo "You can now run setup-infrastructure.sh to rebuild from scratch"
    fi
    echo -e "${NC}"
}

# Run main function
main "$@"