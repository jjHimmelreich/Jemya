# 🔐 AWS IAM Security Best Practices for GitHub Actions

## 🎯 **Deployment User Strategy**

### **✅ DO: Create Dedicated Deployment User**
- **Separate user** for CI/CD deployments only
- **Minimal permissions** (principle of least privilege)
- **Easy to audit** and revoke if needed
- **No console access** (programmatic only)

### **❌ DON'T: Use Personal AWS Account**
- Never use your personal AWS credentials
- Don't use admin or power user permissions
- Avoid using root account credentials

## 🛡️ **Required Permissions Breakdown**

### **1. Amazon ECR (Container Registry)**
```json
{
  "Effect": "Allow",
  "Action": [
    "ecr:GetAuthorizationToken",      // Login to ECR
    "ecr:BatchCheckLayerAvailability", // Check if layers exist
    "ecr:GetDownloadUrlForLayer",     // Download existing layers
    "ecr:BatchGetImage",              // Pull images if needed
    "ecr:InitiateLayerUpload",        // Start uploading new layers
    "ecr:UploadLayerPart",           // Upload layer chunks
    "ecr:CompleteLayerUpload",        // Complete layer upload
    "ecr:PutImage"                    // Push final image
  ],
  "Resource": "arn:aws:ecr:*:*:repository/jemya"
}
```

### **2. AWS App Runner (Deployment Service)**
```json
{
  "Effect": "Allow", 
  "Action": [
    "apprunner:UpdateService",        // Update existing service
    "apprunner:DescribeService"       // Check service status
  ],
  "Resource": "arn:aws:apprunner:*:*:service/jemya-service/*"
}
```

### **3. IAM PassRole (Required for App Runner)**
```json
{
  "Effect": "Allow",
  "Action": [
    "iam:PassRole"                    // Allow App Runner to use service roles
  ],
  "Resource": [
    "arn:aws:iam::*:role/AppRunnerInstanceRole-Jemya",
    "arn:aws:iam::*:role/AppRunnerECRAccessRole-Jemya"
  ]
}
```

## 🚀 **Setup Process**

### **Step 1: Create the User**
```bash
# Run the automated script
./create-deployment-user.sh
```

### **Step 2: Add to GitHub Secrets**
Go to GitHub: **Settings** → **Secrets and variables** → **Actions**

Add these secrets:
- `AWS_ACCESS_KEY_ID`: The access key from script output
- `AWS_SECRET_ACCESS_KEY`: The secret key from script output  
- `AWS_REGION`: Your AWS region (e.g., `us-east-1`)

### **Step 3: Verify Permissions**
The user can ONLY:
- ✅ Push Docker images to ECR repository `jemya`
- ✅ Update App Runner service `jemya-service`
- ✅ Pass required IAM roles to App Runner
- ❌ Access any other AWS services
- ❌ Create or delete resources
- ❌ Access AWS Console

## 🔒 **Security Features**

### **Resource Restrictions**
- **ECR**: Only access to `jemya` repository
- **App Runner**: Only access to `jemya-service` 
- **IAM**: Only pass specific pre-created roles
- **Region**: Can be restricted to specific regions

### **Action Limitations**
- **No Create/Delete**: Can't create new resources
- **No Admin Rights**: No administrative permissions
- **No Console Access**: Programmatic access only
- **Scoped Resources**: Limited to Jemya application

### **Audit Trail**
- All actions logged in AWS CloudTrail
- User tagged with purpose and application
- Easy to identify deployment activities

## 🔄 **Key Rotation Best Practices**

### **Regular Rotation (Every 90 Days)**
```bash
# Rotate access keys
aws iam create-access-key --user-name jemya-github-actions
# Update GitHub secrets with new keys
# Delete old access key
aws iam delete-access-key --user-name jemya-github-actions --access-key-id OLD_KEY_ID
```

### **Emergency Revocation**
```bash
# Immediately disable user
aws iam attach-user-policy --user-name jemya-github-actions --policy-arn arn:aws:iam::aws:policy/AWSDenyAll

# Or delete access keys
aws iam list-access-keys --user-name jemya-github-actions
aws iam delete-access-key --user-name jemya-github-actions --access-key-id KEY_ID
```

## 📊 **Monitoring & Alerts**

### **CloudTrail Events to Monitor**
- `ecr:PutImage` - Image pushes
- `apprunner:UpdateService` - Service deployments
- Failed authentication attempts

### **CloudWatch Alarms**
- Set up alerts for unusual deployment patterns
- Monitor failed deployment attempts
- Track resource usage

## 🚨 **Security Incident Response**

### **If Credentials Are Compromised**
1. **Immediately disable access keys**
2. **Check CloudTrail for unauthorized activity**
3. **Rotate all credentials**
4. **Review and update security policies**
5. **Notify security team if applicable**

### **Prevention**
- ✅ Never log credentials in GitHub Actions output
- ✅ Use GitHub Environments for additional protection
- ✅ Enable branch protection for main branch
- ✅ Require code review for deployment changes
- ✅ Monitor AWS costs for unusual activity

## 🎯 **Alternative: OIDC (Advanced)**

For even better security, consider **AWS IAM OIDC** provider:
- No long-lived credentials
- Temporary tokens per workflow run
- Even more secure than access keys
- Requires additional setup but eliminates credential management

```yaml
# Example OIDC configuration (advanced users)
- name: Configure AWS credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::123456789012:role/GitHubActionsRole
    web-identity-token-file: ${{ env.AWS_WEB_IDENTITY_TOKEN_FILE }}
    aws-region: us-east-1
```

---

**🛡️ Remember: Security is about layers. This setup provides strong security while maintaining deployment functionality.**