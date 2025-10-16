#!/bin/bash
# 🔄 AWS Key Rotation Script
# Add to crontab: 0 2 1 */3 * /path/to/rotate-aws-keys.sh

set -e

# Configuration
DEPLOYMENT_USER="jemya-github-actions"
GITHUB_REPO="jjHimmelreich/Jemya"
LOG_FILE="/tmp/aws-key-rotation.log"

echo "$(date): Starting AWS key rotation for user: $DEPLOYMENT_USER" >> $LOG_FILE

# Check if required tools are available
command -v aws >/dev/null 2>&1 || { echo "AWS CLI is required but not installed." >&2; exit 1; }
command -v gh >/dev/null 2>&1 || { echo "GitHub CLI is required but not installed." >&2; exit 1; }

# Get current access key ID
CURRENT_KEYS=$(aws iam list-access-keys --user-name $DEPLOYMENT_USER --output json)
OLD_KEY_ID=$(echo $CURRENT_KEYS | jq -r '.AccessKeyMetadata[0].AccessKeyId')

echo "$(date): Current key ID: $OLD_KEY_ID" >> $LOG_FILE

# Create new access key
NEW_KEY_OUTPUT=$(aws iam create-access-key --user-name $DEPLOYMENT_USER --output json)
NEW_ACCESS_KEY=$(echo $NEW_KEY_OUTPUT | jq -r '.AccessKey.AccessKeyId')
NEW_SECRET_KEY=$(echo $NEW_KEY_OUTPUT | jq -r '.AccessKey.SecretAccessKey')

echo "$(date): Created new key ID: $NEW_ACCESS_KEY" >> $LOG_FILE

# Test new credentials
AWS_ACCESS_KEY_ID="$NEW_ACCESS_KEY" \
AWS_SECRET_ACCESS_KEY="$NEW_SECRET_KEY" \
aws sts get-caller-identity > /dev/null

if [ $? -eq 0 ]; then
    echo "$(date): New credentials verified successfully" >> $LOG_FILE
else
    echo "$(date): ERROR - New credentials verification failed" >> $LOG_FILE
    # Clean up the failed key
    aws iam delete-access-key --user-name $DEPLOYMENT_USER --access-key-id $NEW_ACCESS_KEY
    exit 1
fi

# Update GitHub secrets
echo "$NEW_SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --repo $GITHUB_REPO --body-file -
echo "$NEW_ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --repo $GITHUB_REPO --body-file -

echo "$(date): Updated GitHub secrets" >> $LOG_FILE

# Wait for propagation
sleep 30

# Delete old access key
aws iam delete-access-key --user-name $DEPLOYMENT_USER --access-key-id $OLD_KEY_ID

echo "$(date): Deleted old key ID: $OLD_KEY_ID" >> $LOG_FILE
echo "$(date): AWS key rotation completed successfully" >> $LOG_FILE

# Optional: Send notification (uncomment and configure)
# curl -X POST -H 'Content-type: application/json' \
#     --data "{\"text\":\"🔄 AWS keys rotated successfully for $DEPLOYMENT_USER\"}" \
#     $SLACK_WEBHOOK_URL