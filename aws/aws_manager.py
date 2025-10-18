#!/usr/bin/env python3
"""
Jemya AWS Infrastructure Manager
===============================

Complete AWS infrastructure management for the Jemya project.
Handles ECR, IAM, EC2, Security Groups, and deployment setup.

Usage:
    python3 aws_manager.py setup              # Complete infrastructure setup
    python3 aws_manager.py cleanup            # Clean up all resources
    python3 aws_manager.py ssh                # Manage SSH security groups
    python3 aws_manager.py policies           # Check/update IAM policies
    python3 aws_manager.py status             # Show current status
"""

import argparse
import boto3
import json
import logging
import os
import requests
import subprocess
import sys
import time
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Set
from botocore.exceptions import ClientError, NoCredentialsError


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


class JemyaAWSManager:
    """Complete AWS infrastructure management for Jemya project"""
    
    def __init__(self, region: str = 'eu-west-1', auto_mode: bool = False):
        self.region = region
        self.auto_mode = auto_mode
        self.project_name = "jemya"
        self.logger = self._setup_logging()
        
        # AWS clients
        try:
            self.ec2_client = boto3.client('ec2', region_name=region)
            self.ec2_resource = boto3.resource('ec2', region_name=region)
            self.ecr_client = boto3.client('ecr', region_name=region)
            self.iam_client = boto3.client('iam')
            self.sts_client = boto3.client('sts')
            self.ssm_client = boto3.client('ssm', region_name=region)
        except NoCredentialsError:
            self._print_error("AWS credentials not configured")
            sys.exit(1)
        
        # Get account info
        try:
            self.account_id = self.sts_client.get_caller_identity()['Account']
        except Exception as e:
            self._print_error(f"Failed to get AWS account info: {e}")
            sys.exit(1)
        
        # Security group names
        self.web_sg_name = "jemya-web-traffic"
        self.admin_sg_name = "jemya-admin-ssh"
        
        # Get VPC ID
        self.vpc_id = self._get_vpc_id()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(level=logging.INFO, format='%(message)s')
        return logging.getLogger(__name__)
    
    def _print_header(self, title: str, char: str = '='):
        """Print a formatted header"""
        print(f"\n{Colors.BOLD}{Colors.CYAN}{title}{Colors.END}")
        print(char * len(title))
    
    def _print_success(self, message: str):
        """Print success message"""
        print(f"{Colors.GREEN}✅ {message}{Colors.END}")
    
    def _print_info(self, message: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")
    
    def _print_warning(self, message: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")
    
    def _print_error(self, message: str):
        """Print error message"""
        print(f"{Colors.RED}❌ {message}{Colors.END}")
    
    def _get_vpc_id(self) -> str:
        """Get the default VPC ID"""
        try:
            response = self.ec2_client.describe_vpcs(
                Filters=[{'Name': 'is-default', 'Values': ['true']}]
            )
            if response['Vpcs']:
                return response['Vpcs'][0]['VpcId']
            else:
                self._print_error("No default VPC found")
                sys.exit(1)
        except ClientError as e:
            self._print_error(f"Failed to get VPC: {e}")
            sys.exit(1)
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met"""
        self._print_header("🔍 Checking Prerequisites")
        
        try:
            # Check AWS credentials
            self._print_success(f"AWS credentials configured (Account: {self.account_id})")
            
            # Check internet connectivity
            response = requests.get('https://api.github.com/meta', timeout=10)
            if response.status_code == 200:
                self._print_success("GitHub API accessible")
            else:
                self._print_warning("GitHub API not accessible")
            
            # Check required tools
            tools = ['docker', 'git']
            for tool in tools:
                try:
                    subprocess.run([tool, '--version'], 
                                 capture_output=True, check=True)
                    self._print_success(f"{tool} installed")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self._print_warning(f"{tool} not found (may be needed later)")
            
            return True
            
        except Exception as e:
            self._print_error(f"Prerequisites check failed: {e}")
            return False
    
    # ========== ECR MANAGEMENT ==========
    
    def setup_ecr(self) -> str:
        """Setup ECR repository"""
        self._print_header("🐳 Setting up ECR Repository")
        
        try:
            # Check if repository exists
            response = self.ecr_client.describe_repositories(
                repositoryNames=[self.project_name]
            )
            repo_uri = response['repositories'][0]['repositoryUri']
            self._print_success(f"ECR repository exists: {repo_uri}")
            return repo_uri
            
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            # Create repository
            self._print_info(f"Creating ECR repository: {self.project_name}")
            
            response = self.ecr_client.create_repository(
                repositoryName=self.project_name,
                imageScanningConfiguration={'scanOnPush': True},
                encryptionConfiguration={'encryptionType': 'AES256'}
            )
            
            repo_uri = response['repository']['repositoryUri']
            self._print_success(f"Created ECR repository: {repo_uri}")
            return repo_uri
            
        except ClientError as e:
            self._print_error(f"Failed to setup ECR: {e}")
            sys.exit(1)
    
    def cleanup_ecr(self):
        """Cleanup ECR repository"""
        try:
            # List images first
            response = self.ecr_client.list_images(repositoryName=self.project_name)
            if response['imageIds']:
                self._print_info(f"Deleting {len(response['imageIds'])} images")
                self.ecr_client.batch_delete_image(
                    repositoryName=self.project_name,
                    imageIds=response['imageIds']
                )
            
            # Delete repository
            self.ecr_client.delete_repository(
                repositoryName=self.project_name,
                force=True
            )
            self._print_success("ECR repository deleted")
            
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            self._print_info("ECR repository not found")
        except ClientError as e:
            self._print_error(f"Failed to cleanup ECR: {e}")
    
    # ========== IAM MANAGEMENT ==========
    
    def _get_policy_document(self, policy_type: str) -> Dict:
        """Get policy document from file"""
        policy_files = {
            'deployment': 'github-actions-user-aws-deployment-policy.json',
            'ecr': 'github-actions-user-ecr-policy.json',
            'ec2_role': 'ec2-instance-role-policy.json',
            'session_manager': 'session-manager-policy.json'
        }
        
        filename = policy_files.get(policy_type)
        if not filename:
            raise ValueError(f"Unknown policy type: {policy_type}")
        
        filepath = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            self._print_error(f"Policy file not found: {filename}")
            sys.exit(1)
    
    def setup_iam_user(self) -> Tuple[str, str]:
        """Setup IAM user for GitHub Actions"""
        self._print_header("👤 Setting up IAM User")
        
        username = f"{self.project_name}-github-actions"
        
        try:
            # Check if user exists
            self.iam_client.get_user(UserName=username)
            self._print_success(f"IAM user exists: {username}")
            
        except self.iam_client.exceptions.NoSuchEntityException:
            # Create user
            self._print_info(f"Creating IAM user: {username}")
            self.iam_client.create_user(
                UserName=username,
                Tags=[
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'Purpose', 'Value': 'GitHub-Actions-Deployment'}
                ]
            )
            self._print_success(f"Created IAM user: {username}")
        
        # Setup policies (including Session Manager for SSH-less deployment)
        policies = [
            ('DeploymentPolicy', self._get_policy_document('deployment')),
            ('ECRPolicy', self._get_policy_document('ecr')),
            ('SessionManagerPolicy', self._get_policy_document('session_manager'))
        ]
        
        for policy_name, policy_doc in policies:
            full_policy_name = f"{self.project_name}-{policy_name}"
            
            try:
                # Create or update policy
                policy_arn = f"arn:aws:iam::{self.account_id}:policy/{full_policy_name}"
                
                try:
                    self.iam_client.get_policy(PolicyArn=policy_arn)
                    # Update policy
                    self.iam_client.create_policy_version(
                        PolicyArn=policy_arn,
                        PolicyDocument=json.dumps(policy_doc),
                        SetAsDefault=True
                    )
                    self._print_success(f"Updated policy: {full_policy_name}")
                    
                except self.iam_client.exceptions.NoSuchEntityException:
                    # Create policy
                    self.iam_client.create_policy(
                        PolicyName=full_policy_name,
                        PolicyDocument=json.dumps(policy_doc),
                        Description=f"Policy for {self.project_name} {policy_name}"
                    )
                    self._print_success(f"Created policy: {full_policy_name}")
                
                # Attach policy to user
                self.iam_client.attach_user_policy(
                    UserName=username,
                    PolicyArn=policy_arn
                )
                
            except ClientError as e:
                self._print_error(f"Failed to setup policy {policy_name}: {e}")
        
        # Generate access keys if needed
        try:
            keys = self.iam_client.list_access_keys(UserName=username)
            if not keys['AccessKeyMetadata']:
                self._print_info("Creating access keys")
                response = self.iam_client.create_access_key(UserName=username)
                access_key = response['AccessKey']['AccessKeyId']
                secret_key = response['AccessKey']['SecretAccessKey']
                
                self._print_success("Created access keys")
                return access_key, secret_key
            else:
                self._print_info("Access keys already exist")
                return None, None
                
        except ClientError as e:
            self._print_error(f"Failed to create access keys: {e}")
            return None, None
    
    def cleanup_iam_user(self):
        """Cleanup IAM user and policies"""
        username = f"{self.project_name}-github-actions"
        
        try:
            # Detach and delete policies
            policies = ['DeploymentPolicy', 'ECRPolicy']
            for policy_name in policies:
                full_policy_name = f"{self.project_name}-{policy_name}"
                policy_arn = f"arn:aws:iam::{self.account_id}:policy/{full_policy_name}"
                
                try:
                    self.iam_client.detach_user_policy(
                        UserName=username,
                        PolicyArn=policy_arn
                    )
                    self.iam_client.delete_policy(PolicyArn=policy_arn)
                    self._print_success(f"Deleted policy: {full_policy_name}")
                except self.iam_client.exceptions.NoSuchEntityException:
                    pass
            
            # Delete access keys
            keys = self.iam_client.list_access_keys(UserName=username)
            for key in keys['AccessKeyMetadata']:
                self.iam_client.delete_access_key(
                    UserName=username,
                    AccessKeyId=key['AccessKeyId']
                )
            
            # Delete user
            self.iam_client.delete_user(UserName=username)
            self._print_success(f"Deleted IAM user: {username}")
            
        except self.iam_client.exceptions.NoSuchEntityException:
            self._print_info("IAM user not found")
        except ClientError as e:
            self._print_error(f"Failed to cleanup IAM user: {e}")
    
    # ========== EC2 MANAGEMENT ==========
    
    def setup_ec2_iam_role(self) -> str:
        """Setup IAM role for EC2 instance with Session Manager support"""
        role_name = f"{self.project_name}-ec2-role"
        
        # Trust policy for EC2
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        try:
            # Check if role exists
            self.iam_client.get_role(RoleName=role_name)
            self._print_success(f"EC2 IAM role exists: {role_name}")
        except self.iam_client.exceptions.NoSuchEntityException:
            # Create role
            self._print_info(f"Creating EC2 IAM role: {role_name}")
            self.iam_client.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy),
                Tags=[
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'Purpose', 'Value': 'EC2-Instance-Role'}
                ]
            )
            self._print_success(f"Created EC2 IAM role: {role_name}")
        
        # Attach Session Manager policy (AWS managed)
        ssm_policy_arn = 'arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore'
        try:
            self.iam_client.attach_role_policy(
                RoleName=role_name,
                PolicyArn=ssm_policy_arn
            )
            self._print_success("Attached Session Manager policy to EC2 role")
        except self.iam_client.exceptions.ClientError as e:
            if 'already attached' in str(e):
                self._print_success("Session Manager policy already attached")
            else:
                raise
        
        # Attach custom EC2 policies if they exist
        try:
            custom_policy = self._get_policy_document('ec2_role')
            custom_policy_name = f"{self.project_name}-EC2Policy"
            policy_arn = f"arn:aws:iam::{self.account_id}:policy/{custom_policy_name}"
            
            try:
                self.iam_client.get_policy(PolicyArn=policy_arn)
                self.iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                self._print_success(f"Attached custom policy: {custom_policy_name}")
            except self.iam_client.exceptions.NoSuchEntityException:
                # Create and attach custom policy
                self.iam_client.create_policy(
                    PolicyName=custom_policy_name,
                    PolicyDocument=json.dumps(custom_policy),
                    Description=f"Custom policy for {self.project_name} EC2 instances"
                )
                self.iam_client.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn=policy_arn
                )
                self._print_success(f"Created and attached custom policy: {custom_policy_name}")
        except (FileNotFoundError, ValueError):
            self._print_info("No custom EC2 policy found, using only Session Manager policy")
        
        # Create instance profile
        profile_name = f"{self.project_name}-ec2-profile"
        try:
            self.iam_client.get_instance_profile(InstanceProfileName=profile_name)
            self._print_success(f"Instance profile exists: {profile_name}")
        except self.iam_client.exceptions.NoSuchEntityException:
            self.iam_client.create_instance_profile(
                InstanceProfileName=profile_name,
                Tags=[
                    {'Key': 'Project', 'Value': self.project_name}
                ]
            )
            # Add role to instance profile
            self.iam_client.add_role_to_instance_profile(
                InstanceProfileName=profile_name,
                RoleName=role_name
            )
            self._print_success(f"Created instance profile: {profile_name}")
        
        return profile_name
    
    def setup_ec2_instance(self) -> str:
        """Setup EC2 instance"""
        self._print_header("🖥️ Setting up EC2 Instance")
        
        # Check if instance exists
        instance = self._find_jemya_instance()
        if instance:
            self._print_success(f"EC2 instance exists: {instance['InstanceId']}")
            return instance['InstanceId']
        
        # Create key pair if needed
        key_name = f"{self.project_name}-key"
        try:
            self.ec2_client.describe_key_pairs(KeyNames=[key_name])
            self._print_success(f"Key pair exists: {key_name}")
        except self.ec2_client.exceptions.ClientError:
            self._print_info(f"Creating key pair: {key_name}")
            response = self.ec2_client.create_key_pair(KeyName=key_name)
            
            # Save private key
            key_file = f"{key_name}.pem"
            with open(key_file, 'w') as f:
                f.write(response['KeyMaterial'])
            os.chmod(key_file, 0o600)
            self._print_success(f"Created key pair: {key_name} (saved to {key_file})")
        
        # Create security group
        sg_id = self._create_basic_security_group()
        
        # Setup IAM role for Session Manager
        instance_profile = self.setup_ec2_iam_role()
        
        # Launch instance
        self._print_info("Launching EC2 instance")
        
        # Get latest Ubuntu AMI
        ami_response = self.ec2_client.describe_images(
            Filters=[
                {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-22.04-amd64-server-*']},
                {'Name': 'owner-id', 'Values': ['099720109477']}  # Canonical
            ],
            Owners=['099720109477']
        )
        
        if not ami_response['Images']:
            self._print_error("No Ubuntu AMI found")
            sys.exit(1)
        
        # Sort by creation date and get latest
        latest_ami = sorted(ami_response['Images'], 
                          key=lambda x: x['CreationDate'], reverse=True)[0]
        
        response = self.ec2_client.run_instances(
            ImageId=latest_ami['ImageId'],
            MinCount=1,
            MaxCount=1,
            InstanceType='t3.micro',  # Free tier eligible
            KeyName=key_name,
            SecurityGroupIds=[sg_id],
            SubnetId=self._get_default_subnet(),
            IamInstanceProfile={
                'Name': instance_profile
            },
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f"{self.project_name}-instance"},
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'SessionManager', 'Value': 'enabled'}
                ]
            }],
            UserData=self._get_user_data_script()
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        self._print_success(f"Launched EC2 instance: {instance_id}")
        
        # Wait for instance to be running
        self._print_info("Waiting for instance to be running...")
        waiter = self.ec2_client.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])
        
        self._print_success("EC2 instance is running")
        return instance_id
    
    def _create_basic_security_group(self) -> str:
        """Create basic security group for EC2 instance"""
        sg_name = f"{self.project_name}-basic-sg"
        
        try:
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [sg_name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            if response['SecurityGroups']:
                return response['SecurityGroups'][0]['GroupId']
        except ClientError:
            pass
        
        # Create security group
        response = self.ec2_client.create_security_group(
            GroupName=sg_name,
            Description=f"Basic security group for {self.project_name}",
            VpcId=self.vpc_id
        )
        
        sg_id = response['GroupId']
        
        # Add basic rules (HTTP/HTTPS)
        self.ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 80,
                    'ToPort': 80,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP'}]
                },
                {
                    'IpProtocol': 'tcp',
                    'FromPort': 443,
                    'ToPort': 443,
                    'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS'}]
                }
            ]
        )
        
        self._print_success(f"Created basic security group: {sg_id}")
        return sg_id
    
    def _get_default_subnet(self) -> str:
        """Get default subnet ID"""
        response = self.ec2_client.describe_subnets(
            Filters=[
                {'Name': 'vpc-id', 'Values': [self.vpc_id]},
                {'Name': 'default-for-az', 'Values': ['true']}
            ]
        )
        if response['Subnets']:
            return response['Subnets'][0]['SubnetId']
        
        # Fallback to any subnet in the VPC
        response = self.ec2_client.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [self.vpc_id]}]
        )
        if response['Subnets']:
            return response['Subnets'][0]['SubnetId']
        
        self._print_error("No subnets found in VPC")
        sys.exit(1)
    
    def _get_user_data_script(self) -> str:
        """Get user data script for EC2 instance initialization"""
        return """#!/bin/bash
# Update system
apt-get update
apt-get install -y docker.io docker-compose nginx git

# Start services
systemctl start docker
systemctl enable docker
systemctl start nginx
systemctl enable nginx

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Create application directory
mkdir -p /home/ubuntu/jemya
chown ubuntu:ubuntu /home/ubuntu/jemya

# Basic nginx configuration
cat > /etc/nginx/sites-available/default << 'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    
    root /var/www/html;
    index index.html index.htm index.nginx-debian.html;
    
    server_name _;
    
    location / {
        try_files $uri $uri/ =404;
    }
}
EOF

systemctl reload nginx

# Signal completion
echo "User data script completed" > /var/log/user-data.log
"""
    
    def _find_jemya_instance(self) -> Optional[Dict]:
        """Find Jemya EC2 instance"""
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': [f'{self.project_name}-instance']},
                    {'Name': 'instance-state-name', 'Values': ['running', 'stopped', 'pending']}
                ]
            )
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    return instance
            return None
            
        except ClientError:
            return None
    
    def cleanup_ec2_instance(self):
        """Cleanup EC2 instance and related resources"""
        # Find and terminate instance
        instance = self._find_jemya_instance()
        if instance:
            instance_id = instance['InstanceId']
            self._print_info(f"Terminating instance: {instance_id}")
            
            self.ec2_client.terminate_instances(InstanceIds=[instance_id])
            
            # Wait for termination
            waiter = self.ec2_client.get_waiter('instance_terminated')
            waiter.wait(InstanceIds=[instance_id])
            
            self._print_success("EC2 instance terminated")
        else:
            self._print_info("No EC2 instance found")
        
        # Delete key pair
        key_name = f"{self.project_name}-key"
        try:
            self.ec2_client.delete_key_pair(KeyName=key_name)
            self._print_success(f"Deleted key pair: {key_name}")
        except ClientError:
            pass
        
        # Delete basic security group
        sg_name = f"{self.project_name}-basic-sg"
        try:
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [sg_name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                self.ec2_client.delete_security_group(GroupId=sg_id)
                self._print_success(f"Deleted basic security group: {sg_id}")
        except ClientError:
            pass
    
    # ========== SECURITY GROUP MANAGEMENT ==========
    
    def setup_web_traffic_security_group(self) -> str:
        """Setup web traffic security group for HTTP/HTTPS access"""
        self._print_header("🌐 Setting up Web Security Group")
        
        try:
            # Check if security group exists
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [self.web_sg_name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                self._print_success(f"Found existing web traffic security group: {sg_id}")
                return sg_id
            
            # Create new security group
            response = self.ec2_client.create_security_group(
                GroupName=self.web_sg_name,
                Description="HTTP and HTTPS access for Jemya web application",
                VpcId=self.vpc_id
            )
            
            sg_id = response['GroupId']
            
            # Add HTTP and HTTPS rules
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 80,
                        'ToPort': 80,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTP access'}]
                    },
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 443,
                        'ToPort': 443,
                        'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'HTTPS access'}]
                    }
                ]
            )
            
            # Add tags
            self.ec2_client.create_tags(
                Resources=[sg_id],
                Tags=[
                    {'Key': 'Name', 'Value': self.web_sg_name},
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'Purpose', 'Value': 'Web-Traffic'}
                ]
            )
            
            self._print_success(f"Created web traffic security group: {sg_id}")
            return sg_id
            
        except ClientError as e:
            self._print_error(f"Failed to create web traffic security group: {e}")
            return None
    
    def setup_admin_ssh_security_group(self) -> str:
        """Setup admin SSH security group for current IP"""
        self._print_header("🔐 Setting up Admin SSH Access")
        
        # Get current public IP
        try:
            response = requests.get('https://api.ipify.org', timeout=10)
            current_ip = response.text.strip()
            self._print_info(f"Detected current public IP: {current_ip}")
        except Exception as e:
            self._print_error(f"Failed to get current IP: {e}")
            return None
        
        # Ask for confirmation unless in auto mode
        if not self.auto_mode:
            confirm = input(f"{Colors.CYAN}Add/update SSH access for IP {current_ip}? (y/N): {Colors.END}").lower()
            if confirm != 'y':
                self._print_info("SSH setup cancelled")
                return None
        
        try:
            # Check if security group exists
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [self.admin_sg_name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                self._print_success(f"Found existing admin SSH security group: {sg_id}")
                
                # Update the IP address
                self._update_admin_ssh_ip(sg_id, current_ip)
                return sg_id
            
            # Create new security group
            response = self.ec2_client.create_security_group(
                GroupName=self.admin_sg_name,
                Description="SSH access for admin/developer",
                VpcId=self.vpc_id
            )
            
            sg_id = response['GroupId']
            
            # Add SSH rule for current IP
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': f'{current_ip}/32', 'Description': 'Admin SSH access'}]
                    }
                ]
            )
            
            # Add tags
            self.ec2_client.create_tags(
                Resources=[sg_id],
                Tags=[
                    {'Key': 'Name', 'Value': self.admin_sg_name},
                    {'Key': 'Project', 'Value': self.project_name},
                    {'Key': 'Purpose', 'Value': 'Admin-SSH'}
                ]
            )
            
            self._print_success(f"Created admin SSH security group: {sg_id}")
            self._print_success(f"Added SSH access for IP: {current_ip}")
            return sg_id
            
        except ClientError as e:
            self._print_error(f"Failed to create admin SSH security group: {e}")
            return None
    
    def _update_admin_ssh_ip(self, sg_id: str, new_ip: str):
        """Update admin SSH security group with new IP"""
        try:
            # Get current rules
            response = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg = response['SecurityGroups'][0]
            
            # Find SSH rules to remove
            ssh_rules = [rule for rule in sg['IpPermissions'] 
                        if rule.get('FromPort') == 22 and rule.get('ToPort') == 22]
            
            # Check if IP is already configured
            current_ips = []
            for rule in ssh_rules:
                for ip_range in rule.get('IpRanges', []):
                    current_ips.append(ip_range['CidrIp'])
            
            if f"{new_ip}/32" in current_ips:
                self._print_success(f"SSH access already configured for IP: {new_ip}")
                return
            
            if current_ips:
                self._print_info(f"Replacing existing SSH IPs: {', '.join(current_ips)}")
            
            # Remove old SSH rules
            if ssh_rules:
                self.ec2_client.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=ssh_rules
                )
                self._print_info("Removed old SSH rules")
            
            # Add new SSH rule
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=[
                    {
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': f'{new_ip}/32', 'Description': 'Admin SSH access'}]
                    }
                ]
            )
            
            self._print_success(f"Updated SSH access for IP: {new_ip}")
            
        except ClientError as e:
            self._print_error(f"Failed to update SSH IP: {e}")
    
    def remove_admin_ssh_access(self):
        """Remove admin SSH security group"""
        self._print_header("🚫 Removing Admin SSH Access")
        
        # Ask for confirmation unless in auto mode
        if not self.auto_mode:
            confirm = input(f"{Colors.YELLOW}Remove SSH access completely? (y/N): {Colors.END}").lower()
            if confirm != 'y':
                self._print_info("SSH removal cancelled")
                return
        
        try:
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [self.admin_sg_name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                
                # Remove from instance first
                instance = self._find_jemya_instance()
                if instance:
                    self._remove_sg_from_instance(instance['InstanceId'], sg_id)
                
                # Delete security group
                self.ec2_client.delete_security_group(GroupId=sg_id)
                self._print_success(f"Removed admin SSH security group: {sg_id}")
            else:
                self._print_info("Admin SSH security group not found")
                
        except ClientError as e:
            self._print_error(f"Failed to remove admin SSH security group: {e}")
    
    def _remove_sg_from_instance(self, instance_id: str, sg_to_remove: str):
        """Remove a security group from an instance"""
        try:
            # Get current security groups
            response = self.ec2_client.describe_instances(InstanceIds=[instance_id])
            instance = response['Reservations'][0]['Instances'][0]
            current_sgs = [sg['GroupId'] for sg in instance['SecurityGroups'] if sg['GroupId'] != sg_to_remove]
            
            # Update instance security groups
            self.ec2_client.modify_instance_attribute(
                InstanceId=instance_id,
                Groups=current_sgs
            )
            self._print_info(f"Removed security group from instance: {sg_to_remove}")
            
        except ClientError as e:
            self._print_warning(f"Failed to remove security group from instance: {e}")
    
    def _update_instance_security_groups(self, web_sg_id: str, admin_ssh_sg_id: str = None):
        """Update EC2 instance security groups"""
        instance = self._find_jemya_instance()
        if not instance:
            self._print_warning("No EC2 instance found to update")
            return
        
        instance_id = instance['InstanceId']
        current_sgs = [sg['GroupId'] for sg in instance['SecurityGroups']]
        
        # Build new security group list
        new_sgs = []
        
        # Add web traffic security group
        if web_sg_id:
            new_sgs.append(web_sg_id)
            
        # Add admin SSH security group if provided
        if admin_ssh_sg_id:
            new_sgs.append(admin_ssh_sg_id)
        
        # Keep existing security groups (default, etc.)
        for sg_id in current_sgs:
            if sg_id not in [web_sg_id, admin_ssh_sg_id]:
                try:
                    response = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
                    sg = response['SecurityGroups'][0]
                    sg_name = sg['GroupName']
                    
                    # Always keep default SG and basic security groups
                    new_sgs.append(sg_id)
                    self._print_info(f"Keeping security group: {sg_id} ({sg_name})")
                        
                except ClientError:
                    # If we can't describe the SG, keep it to be safe
                    new_sgs.append(sg_id)
                    pass
        
        # Remove duplicates
        new_sgs = list(dict.fromkeys(new_sgs))
        
        if new_sgs != current_sgs:
            try:
                self.ec2_client.modify_instance_attribute(
                    InstanceId=instance_id,
                    Groups=new_sgs
                )
                self._print_success(f"Updated instance security groups: {len(new_sgs)} groups")
            except ClientError as e:
                self._print_error(f"Failed to update instance security groups: {e}")
    
    def cleanup_web_security_groups(self):
        """Cleanup web and admin security groups"""
        sg_names = [self.web_sg_name, self.admin_sg_name]
        
        for sg_name in sg_names:
            try:
                response = self.ec2_client.describe_security_groups(
                    Filters=[
                        {'Name': 'group-name', 'Values': [sg_name]},
                        {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                    ]
                )
                
                for sg in response['SecurityGroups']:
                    self.ec2_client.delete_security_group(GroupId=sg['GroupId'])
                    self._print_success(f"Deleted security group: {sg['GroupId']} ({sg_name})")
                    
            except ClientError:
                pass
    
    # ========== STATUS AND REPORTING ==========
    
    def show_status(self):
        """Show current infrastructure status"""
        self._print_header("📊 Jemya Infrastructure Status")
        
        # ECR Status
        try:
            response = self.ecr_client.describe_repositories(repositoryNames=[self.project_name])
            repo_uri = response['repositories'][0]['repositoryUri']
            self._print_success(f"ECR Repository: {repo_uri}")
            
            # Check for images
            images = self.ecr_client.list_images(repositoryName=self.project_name)
            self._print_info(f"Container Images: {len(images['imageIds'])}")
            
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            self._print_warning("ECR Repository: Not found")
        
        # IAM User Status
        username = f"{self.project_name}-github-actions"
        try:
            self.iam_client.get_user(UserName=username)
            self._print_success(f"IAM User: {username}")
            
            # Check policies
            policies = self.iam_client.list_attached_user_policies(UserName=username)
            self._print_info(f"Attached Policies: {len(policies['AttachedPolicies'])}")
            
        except self.iam_client.exceptions.NoSuchEntityException:
            self._print_warning("IAM User: Not found")
        
        # EC2 Instance Status
        instance = self._find_jemya_instance()
        if instance:
            self._print_success(f"EC2 Instance: {instance['InstanceId']} ({instance['State']['Name']})")
            
            if instance['State']['Name'] == 'running' and 'PublicIpAddress' in instance:
                self._print_info(f"Public IP: {instance['PublicIpAddress']}")
            
            # Security groups
            sg_names = [sg['GroupName'] for sg in instance['SecurityGroups']]
            self._print_info(f"Security Groups: {', '.join(sg_names)}")
            
        else:
            self._print_warning("EC2 Instance: Not found")
        
        # Security Group Status
        sg_names = [self.web_sg_name, self.admin_sg_name]
        for sg_name in sg_names:
            try:
                response = self.ec2_client.describe_security_groups(
                    Filters=[
                        {'Name': 'group-name', 'Values': [sg_name]},
                        {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                    ]
                )
                
                if response['SecurityGroups']:
                    sg = response['SecurityGroups'][0]
                    if sg_name == self.web_sg_name:
                        # Count HTTP/HTTPS rules for web traffic SG
                        web_rules = [rule for rule in sg['IpPermissions'] 
                                   if rule.get('FromPort') in [80, 443]]
                        self._print_success(f"Web Security Group: {len(web_rules)} HTTP/HTTPS rules")
                    elif sg_name == self.admin_sg_name:
                        # Count SSH rules and show IP
                        ssh_rules = [rule for rule in sg['IpPermissions'] 
                                   if rule.get('FromPort') == 22]
                        if ssh_rules and ssh_rules[0].get('IpRanges'):
                            ip_range = ssh_rules[0]['IpRanges'][0]['CidrIp']
                            self._print_success(f"Admin SSH Group: {ip_range}")
                        else:
                            self._print_success(f"Admin SSH Group: {len(ssh_rules)} SSH rules")
                else:
                    if sg_name == self.web_sg_name:
                        self._print_warning("Web Security Group: Not found")
                    elif sg_name == self.admin_sg_name:
                        self._print_info("Admin SSH Group: Not configured")
                    
            except ClientError:
                if sg_name == self.web_sg_name:
                    self._print_warning("Web Security Group: Error checking")
                elif sg_name == self.admin_sg_name:
                    self._print_warning("Admin SSH Group: Error checking")
    

    
    def deploy_application(self, force_rebuild: bool = False, image_tag: str = "latest", deploy_only: bool = False):
        """Deploy the application using Session Manager"""
        self._print_header("🚀 Deploying Jemya Application")
        
        # Get instance details
        instance = self._find_jemya_instance()
        if not instance:
            self._print_error("No EC2 instance found. Please run setup first.")
            return False
            
        instance_id = instance['InstanceId']
        self._print_info(f"Target instance: {instance_id}")
        self._print_info(f"Image tag: {image_tag}")
        
        # Get ECR repository URI
        ecr_repo = self._get_ecr_repository_uri()
        if not ecr_repo:
            self._print_error("No ECR repository found. Please run setup first.")
            return False
            
        self._print_info(f"ECR repository: {ecr_repo}")
        
        try:
            # Skip build phase if deploy_only is True (for CI/CD where image is already built)
            if not deploy_only:
                # Build and push Docker image
                self._print_info("Building and pushing Docker image...")
                
                # Get current directory (should be project root)
                current_dir = os.getcwd()
                
                # Get current git commit for tagging
                try:
                    commit_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=current_dir).decode().strip()[:8]
                    print(f"📝 Using commit SHA for tagging: {commit_sha}")
                except subprocess.CalledProcessError:
                    commit_sha = "local"
                    print("⚠️  Git not available, using 'local' tag")
                
                build_commands = [
                    f"cd {current_dir}",
                    f"aws ecr get-login-password --region {self.region} | docker login --username AWS --password-stdin {ecr_repo}",
                    f"docker build -t jemya .",
                    f"docker tag jemya:latest {ecr_repo}:{commit_sha}",
                    f"docker tag jemya:latest {ecr_repo}:latest",
                    f"docker push {ecr_repo}:{commit_sha}",
                    f"docker push {ecr_repo}:latest"
                ]
                
                for cmd in build_commands:
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode != 0:
                        self._print_error(f"Build command failed: {cmd}")
                        self._print_error(f"Error: {result.stderr}")
                        return False
                
                self._print_success("Docker image built and pushed successfully")
            else:
                self._print_info("Skipping build phase - deploying pre-built image from ECR")
            
            # Deploy to EC2 using Session Manager
            self._print_info("Deploying to EC2 instance...")
            
            # Blue-Green Deployment: Find available port for new container
            self._print_info("Implementing blue-green deployment...")
            
            # Define our two ports for blue-green deployment
            blue_port = "8501"
            green_port = "8502"
            
            # Check which ports are currently in use
            port_check_cmd = f"""
            echo "=== Port Status ==="
            if sudo netstat -tlnp 2>/dev/null | grep ':{blue_port} ' || sudo ss -tlnp 2>/dev/null | grep ':{blue_port} '; then
                echo "Port {blue_port}: IN USE"
            else
                echo "Port {blue_port}: FREE"
            fi
            
            if sudo netstat -tlnp 2>/dev/null | grep ':{green_port} ' || sudo ss -tlnp 2>/dev/null | grep ':{green_port} '; then
                echo "Port {green_port}: IN USE"
            else
                echo "Port {green_port}: FREE"
            fi
            """
            port_status = self._get_ssm_command_output(instance_id, port_check_cmd)
            self._print_info("Checking port availability:")
            print(port_status)
            
            # Determine which port to use for new container
            if f"Port {blue_port}: FREE" in port_status:
                new_port = blue_port
                current_port = green_port
                new_container = "jemya-blue"
                old_container = "jemya-green" 
            elif f"Port {green_port}: FREE" in port_status:
                new_port = green_port
                current_port = blue_port
                new_container = "jemya-green"
                old_container = "jemya-blue"
            else:
                self._print_error("Both ports 8501 and 8502 are in use - cannot perform blue-green deployment")
                self._print_info("Falling back to stop-and-start deployment...")
                # Force cleanup and use 8501
                cleanup_cmd = "sudo docker stop jemya-blue jemya-green jemya jemya-app 2>/dev/null || true; sudo docker rm -f jemya-blue jemya-green jemya jemya-app 2>/dev/null || true"
                self._run_ssm_command(instance_id, cleanup_cmd)
                new_port = blue_port
                current_port = None
                new_container = "jemya-blue"
                old_container = None
            
            self._print_info(f"Using port {new_port} for new container: {new_container}")
            if old_container:
                self._print_info(f"Will replace container: {old_container} (port {current_port})")
            
            # Login to ECR on the instance
            login_cmd = f"aws ecr get-login-password --region {self.region} | sudo docker login --username AWS --password-stdin {ecr_repo}"
            if not self._run_ssm_command(instance_id, login_cmd):
                return False
            
            # Pull latest image
            pull_cmd = f"sudo docker pull {ecr_repo}:{image_tag}"
            if not self._run_ssm_command(instance_id, pull_cmd):
                return False
            
            # Start new container on new port (Blue-Green deployment)
            self._print_info(f"Starting new container '{new_container}' on port {new_port}...")
            run_cmd = f"sudo docker run -d --name {new_container} -p 127.0.0.1:{new_port}:8501 --restart unless-stopped {ecr_repo}:{image_tag}"
            if not self._run_ssm_command(instance_id, run_cmd):
                self._print_error("Failed to start new container")
                return False
            
            # Wait for container to start and perform health check
            self._print_info("Waiting for new container to become healthy...")
            health_check_cmd = f"""
            for i in {{1..30}}; do
                if sudo docker inspect {new_container} --format '{{{{.State.Health.Status}}}}' 2>/dev/null | grep -q healthy; then
                    echo "Container is healthy"
                    break
                elif sudo docker inspect {new_container} --format '{{{{.State.Status}}}}' 2>/dev/null | grep -q running; then
                    echo "Container is running (attempt $i/30)"
                    sleep 2
                else
                    echo "Container failed to start properly"
                    sudo docker logs {new_container} 2>/dev/null || echo "No logs available"
                    exit 1
                fi
                if [ $i -eq 30 ]; then
                    echo "Container health check timeout"
                    exit 1
                fi
            done
            """
            if not self._run_ssm_command(instance_id, health_check_cmd):
                self._print_error("New container failed health check - rolling back")
                rollback_cmd = f"sudo docker stop {new_container} 2>/dev/null || true; sudo docker rm -f {new_container} 2>/dev/null || true"
                self._run_ssm_command(instance_id, rollback_cmd)
                return False
            
            # Update nginx configuration to point to new port (Blue-Green switch)
            self._print_info(f"Switching nginx to new container (port {new_port})...")
            nginx_update_cmd = f"""
            sudo cp /etc/nginx/conf.d/jemya.conf /etc/nginx/conf.d/jemya.conf.backup
            sudo sed -i 's/proxy_pass http:\\/\\/localhost:[0-9]*/proxy_pass http:\\/\\/localhost:{new_port}/' /etc/nginx/conf.d/jemya.conf
            sudo nginx -t && sudo systemctl reload nginx
            """
            if not self._run_ssm_command(instance_id, nginx_update_cmd):
                self._print_error("Failed to update nginx configuration - rolling back")
                # Restore nginx config
                restore_cmd = "sudo cp /etc/nginx/conf.d/jemya.conf.backup /etc/nginx/conf.d/jemya.conf 2>/dev/null || true; sudo systemctl reload nginx 2>/dev/null || true"
                self._run_ssm_command(instance_id, restore_cmd)
                # Remove new container
                rollback_cmd = f"sudo docker stop {new_container} 2>/dev/null || true; sudo docker rm -f {new_container} 2>/dev/null || true"
                self._run_ssm_command(instance_id, rollback_cmd)
                return False
            
            # Verify nginx switch was successful
            self._print_info("Verifying nginx configuration...")
            verify_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{new_port} || echo 'CURL_FAILED'"
            if not self._run_ssm_command(instance_id, verify_cmd):
                self._print_error("New container not responding - keeping old container active")
                return False
            
            # Clean up old container (Blue-Green deployment complete)
            if old_container:
                self._print_info(f"Cleaning up old container '{old_container}'...")
                cleanup_old_cmd = f"sudo docker stop {old_container} 2>/dev/null || true; sudo docker rm -f {old_container} 2>/dev/null || true"
                self._run_ssm_command(instance_id, cleanup_old_cmd)
            else:
                self._print_info("No old container to clean up (fresh deployment)")
            
            # Also clean up legacy containers
            legacy_cleanup_cmd = "sudo docker stop jemya jemya-app 2>/dev/null || true; sudo docker rm -f jemya jemya-app 2>/dev/null || true"
            self._run_ssm_command(instance_id, legacy_cleanup_cmd)
            
            # Final status check
            status_cmd = f"sudo docker ps --filter name={new_container} --format 'table {{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Ports}}}}'"
            if self._run_ssm_command(instance_id, status_cmd):
                self._print_success("Blue-Green deployment completed successfully!")
                
                # Get public IP
                public_ip = instance.get('PublicIpAddress')
                if public_ip:
                    self._print_success(f"Application available at: https://{public_ip}")
                    self._print_info(f"HTTP requests will automatically redirect to HTTPS")
                    self._print_info(f"Active container: {new_container} on port {new_port}")
                
                return True
            else:
                self._print_error("Deployment verification failed")
                return False
                
        except Exception as e:
            self._print_error(f"Deployment failed: {e}")
            return False
    
    def _run_ssm_command(self, instance_id: str, command: str) -> bool:
        """Run a command on EC2 instance via Session Manager"""
        try:
            response = self.ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={'commands': [command]}
            )
            
            command_id = response['Command']['CommandId']
            
            # Wait for command to complete
            waiter = self.ssm_client.get_waiter('command_executed')
            waiter.wait(
                CommandId=command_id,
                InstanceId=instance_id,
                WaiterConfig={'Delay': 2, 'MaxAttempts': 30}
            )
            
            # Get command result
            result = self.ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            
            if result['Status'] == 'Success':
                if result.get('StandardOutputContent'):
                    print(result['StandardOutputContent'])
                return True
            else:
                self._print_error(f"Command failed with status: {result['Status']}")
                if result.get('StandardErrorContent'):
                    self._print_error(f"Error output: {result['StandardErrorContent']}")
                if result.get('StandardOutputContent'):
                    self._print_error(f"Standard output: {result['StandardOutputContent']}")
                return False
                
        except Exception as e:
            self._print_error(f"Failed to run SSM command: {e}")
            return False
    
    def _get_ssm_command_output(self, instance_id: str, command: str) -> str:
        """Get output from SSM command without printing"""
        try:
            response = self.ssm_client.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={'commands': [command]}
            )
            
            command_id = response['Command']['CommandId']
            
            # Wait for command to complete
            waiter = self.ssm_client.get_waiter('command_executed')
            waiter.wait(
                CommandId=command_id,
                InstanceId=instance_id,
                WaiterConfig={'Delay': 2, 'MaxAttempts': 30}
            )
            
            # Get command result
            result = self.ssm_client.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id
            )
            
            if result['Status'] == 'Success':
                return result.get('StandardOutputContent', '')
            else:
                return ''
                
        except Exception as e:
            return ''
    
    def _get_ecr_repository_uri(self) -> str:
        """Get ECR repository URI"""
        try:
            response = self.ecr_client.describe_repositories(
                repositoryNames=['jemya']
            )
            
            if response['repositories']:
                return response['repositories'][0]['repositoryUri']
            return None
            
        except self.ecr_client.exceptions.RepositoryNotFoundException:
            return None
        except Exception as e:
            self._print_error(f"Failed to get ECR repository: {e}")
            return None
    
    # ========== MAIN COMMANDS ==========
    
    def setup_complete_infrastructure(self):
        """Setup complete infrastructure"""
        self._print_header("🚀 Complete Infrastructure Setup")
        
        if not self.check_prerequisites():
            return
        
        # Setup ECR
        repo_uri = self.setup_ecr()
        
        # Setup IAM
        access_key, secret_key = self.setup_iam_user()
        
        # Setup EC2
        instance_id = self.setup_ec2_instance()
        
        # Setup web security group for HTTP/HTTPS access
        web_sg_id = self.setup_web_traffic_security_group()
        if web_sg_id:
            self._update_instance_security_groups(web_sg_id)
        
        # Final summary
        self._print_header("🎉 Setup Complete!")
        
        print(f"\n{Colors.BOLD}Infrastructure Summary:{Colors.END}")
        print(f"  🐳 ECR Repository: {repo_uri}")
        print(f"  🖥️  EC2 Instance: {instance_id}")
        print(f"  🔧 Session Manager: Enabled (SSH-less deployment)")
        print(f"  🔐 IAM Role: {self.project_name}-ec2-role (with Session Manager access)")
        
        if access_key and secret_key:
            print(f"\n{Colors.BOLD}GitHub Secrets to Add:{Colors.END}")
            print(f"  AWS_ACCESS_KEY_ID: {access_key}")
            print(f"  AWS_SECRET_ACCESS_KEY: {secret_key}")
            print(f"  AWS_REGION: {self.region}")
            print(f"  ECR_REPOSITORY: {repo_uri}")
        
        print(f"\n{Colors.BOLD}Deployment Method:{Colors.END}")
        print(f"  🚀 Use Session Manager for deployments (no SSH required)")
        print(f"  📝 Deploy command: python3 aws_manager.py deploy")
        
        self._print_warning("Save the access keys securely - they won't be shown again!")
    
    def cleanup_complete_infrastructure(self):
        """Cleanup complete infrastructure"""
        self._print_header("🧹 Complete Infrastructure Cleanup")
        
        if not self.auto_mode:
            response = input(f"{Colors.YELLOW}⚠️  This will delete ALL Jemya AWS resources. Continue? (type 'yes'): {Colors.END}")
            if response.lower() != 'yes':
                print("Cleanup cancelled")
                return
        
        # Cleanup in reverse order
        self.cleanup_web_security_groups()
        self.cleanup_ec2_instance()
        self.cleanup_iam_user()
        self.cleanup_ecr()
        
        self._print_header("✅ Cleanup Complete!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Jemya AWS Infrastructure Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  setup       Complete infrastructure setup (ECR, IAM, EC2, Security Groups)
  cleanup     Clean up all AWS resources
  status      Show current infrastructure status
  deploy      Deploy application using Session Manager
  ssh         Manage admin SSH access (add/update current IP)
  
Examples:
  python3 aws_manager.py setup                          # Complete setup
  python3 aws_manager.py cleanup --auto                 # Automated cleanup
  python3 aws_manager.py status                         # Show current status
  python3 aws_manager.py deploy                         # Deploy latest image
  python3 aws_manager.py deploy --image-tag 1a2b3c4d   # Deploy specific commit
  python3 aws_manager.py ssh                            # Add/update SSH access for current IP
        """
    )
    
    parser.add_argument('command', choices=['setup', 'cleanup', 'status', 'deploy', 'ssh'],
                        help='Command to execute')
    parser.add_argument('--region', default='eu-west-1',
                        help='AWS region (default: eu-west-1)')
    parser.add_argument('--auto', action='store_true',
                        help='Run in automatic mode (no interactive prompts)')
    parser.add_argument('--remove', action='store_true',
                        help='Remove SSH access (only used with ssh command)')
    parser.add_argument('--image-tag', default='latest',
                        help='Docker image tag to deploy (default: latest)')
    parser.add_argument('--deploy-only', action='store_true',
                        help='Skip build phase and deploy pre-built image from ECR (for CI/CD)')

    
    args = parser.parse_args()
    
    # Create manager
    manager = JemyaAWSManager(region=args.region, auto_mode=args.auto)
    
    # Execute command
    if args.command == 'setup':
        manager.setup_complete_infrastructure()
    elif args.command == 'cleanup':
        manager.cleanup_complete_infrastructure()
    elif args.command == 'status':
        manager.show_status()
    elif args.command == 'deploy':
        success = manager.deploy_application(image_tag=args.image_tag, deploy_only=args.deploy_only)
        if not success:
            sys.exit(1)
    elif args.command == 'ssh':
        if args.remove:
            manager.remove_admin_ssh_access()
        else:
            ssh_sg_id = manager.setup_admin_ssh_security_group()
            if ssh_sg_id:
                manager._update_instance_security_groups(None, ssh_sg_id)


if __name__ == '__main__':
    main()