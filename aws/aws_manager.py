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
import ipaddress
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
        self.github_sg_name = "jemya-github-sg"
        self.admin_sg_name = "jemya-admin-sg"
        self.web_sg_name = "jemya-web-traffic"
        self.legacy_sg_name = "jemya-sg"
        
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
            'ec2_role': 'ec2-instance-role-policy.json'
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
        
        # Setup policies
        policies = [
            ('DeploymentPolicy', self._get_policy_document('deployment')),
            ('ECRPolicy', self._get_policy_document('ecr'))
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
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': f"{self.project_name}-instance"},
                    {'Key': 'Project', 'Value': self.project_name}
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
    
    # ========== SSH SECURITY GROUP MANAGEMENT ==========
    
    def fetch_github_actions_ips(self) -> List[str]:
        """Fetch GitHub Actions IP ranges from GitHub API"""
        try:
            response = requests.get('https://api.github.com/meta', timeout=30)
            response.raise_for_status()
            
            data = response.json()
            github_ips = []
            
            for ip_range in data.get('actions', []):
                try:
                    network = ipaddress.ip_network(ip_range, strict=False)
                    if network.version == 4:  # IPv4 only
                        github_ips.append(str(network))
                except ValueError:
                    continue
            
            return github_ips
            
        except Exception as e:
            self._print_error(f"Failed to fetch GitHub Actions IPs: {e}")
            return []
    
    def optimize_ip_ranges(self, ip_ranges: List[str], max_rules: int = 50) -> List[str]:
        """Optimize IP ranges to fit within AWS security group limits"""
        networks_by_prefix = defaultdict(list)
        
        for ip_range in ip_ranges:
            network = ipaddress.ip_network(ip_range)
            networks_by_prefix[network.prefixlen].append(network)
        
        # Sort prefix lengths (prefer larger blocks)
        sorted_prefixes = sorted(networks_by_prefix.keys())
        
        optimized_networks = []
        covered_networks = set()
        
        for prefix_len in sorted_prefixes:
            if len(optimized_networks) >= max_rules:
                break
                
            for network in networks_by_prefix[prefix_len]:
                if len(optimized_networks) >= max_rules:
                    break
                
                is_covered = any(network.subnet_of(covered) for covered in covered_networks)
                
                if not is_covered:
                    optimized_networks.append(network)
                    covered_networks.add(network)
        
        return [str(net) for net in optimized_networks[:max_rules]]
    
    def setup_web_traffic_security_group(self) -> str:
        """Setup web traffic security group for HTTP/HTTPS access"""
        self._print_info("🌐 Setting up web traffic security group")
        
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
    
    def setup_ssh_security_groups(self, admin_ips: List[str] = None):
        """Setup SSH security groups for GitHub Actions and admin access"""
        self._print_header("🛡️ Setting up SSH Security Groups")
        
        # Setup GitHub Actions security group
        github_ips = self.fetch_github_actions_ips()
        if github_ips:
            optimized_ips = self.optimize_ip_ranges(github_ips, 50)
            self._print_success(f"Optimized {len(github_ips)} GitHub Actions IPs to {len(optimized_ips)} rules")
            
            github_sg_id = self._create_or_update_security_group(
                self.github_sg_name,
                "SSH access for GitHub Actions runners - Jemya project",
                optimized_ips
            )
        else:
            github_sg_id = None
        
        # Setup admin security group
        if admin_ips is None:
            admin_ips = []
            
        # Auto-detect current IP
        try:
            response = requests.get('https://api.ipify.org', timeout=10)
            current_ip = response.text.strip()
            if current_ip and f"{current_ip}/32" not in admin_ips:
                if self.auto_mode or input(f"Add your current IP ({current_ip}) to admin access? (y/n): ").lower() == 'y':
                    admin_ips.append(f"{current_ip}/32")
        except Exception:
            pass
        
        if admin_ips:
            admin_sg_id = self._create_or_update_security_group(
                self.admin_sg_name,
                "SSH access for administrators and developers - Jemya project",
                admin_ips
            )
        else:
            admin_sg_id = None
        
        # Setup web traffic security group
        web_sg_id = self.setup_web_traffic_security_group()
        
        # Update instance security groups
        self._update_instance_security_groups(github_sg_id, admin_sg_id, web_sg_id)
        
        return github_sg_id, admin_sg_id
    
    def _create_or_update_security_group(self, name: str, description: str, ip_ranges: List[str]) -> str:
        """Create or update security group with IP ranges"""
        try:
            # Check if security group exists
            response = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'group-name', 'Values': [name]},
                    {'Name': 'vpc-id', 'Values': [self.vpc_id]}
                ]
            )
            
            if response['SecurityGroups']:
                sg_id = response['SecurityGroups'][0]['GroupId']
                self._print_success(f"Found existing security group: {sg_id} ({name})")
            else:
                # Create new security group
                response = self.ec2_client.create_security_group(
                    GroupName=name,
                    Description=description,
                    VpcId=self.vpc_id
                )
                sg_id = response['GroupId']
                self._print_success(f"Created security group: {sg_id} ({name})")
            
            # Clear existing SSH rules
            self._clear_ssh_rules(sg_id, name)
            
            # Add new SSH rules
            self._add_ssh_rules(sg_id, name, ip_ranges)
            
            return sg_id
            
        except ClientError as e:
            self._print_error(f"Failed to create/update security group {name}: {e}")
            return None
    
    def _clear_ssh_rules(self, sg_id: str, sg_name: str):
        """Clear existing SSH rules from security group"""
        try:
            response = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg = response['SecurityGroups'][0]
            
            ssh_rules = [rule for rule in sg['IpPermissions'] 
                        if rule.get('FromPort') == 22 and rule.get('ToPort') == 22]
            
            if ssh_rules:
                self.ec2_client.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=ssh_rules
                )
                self._print_success(f"Cleared {len(ssh_rules)} SSH rules from {sg_name}")
            
        except ClientError as e:
            self._print_warning(f"Failed to clear SSH rules: {e}")
    
    def _add_ssh_rules(self, sg_id: str, sg_name: str, ip_ranges: List[str]):
        """Add SSH rules to security group"""
        if not ip_ranges:
            return
        
        ip_permissions = [{
            'IpProtocol': 'tcp',
            'FromPort': 22,
            'ToPort': 22,
            'IpRanges': [{'CidrIp': ip_range, 'Description': 'SSH access'} 
                        for ip_range in ip_ranges]
        }]
        
        try:
            self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=ip_permissions
            )
            self._print_success(f"Added {len(ip_ranges)} SSH rules to {sg_name}")
            
        except ClientError as e:
            self._print_warning(f"Failed to add SSH rules: {e}")
    
    def _update_instance_security_groups(self, github_sg_id: str, admin_sg_id: str, web_sg_id: str = None):
        """Update EC2 instance security groups"""
        instance = self._find_jemya_instance()
        if not instance:
            self._print_warning("No EC2 instance found to update")
            return
        
        instance_id = instance['InstanceId']
        current_sgs = [sg['GroupId'] for sg in instance['SecurityGroups']]
        
        # Build new security group list
        new_sgs = []
        
        # Add SSH security groups
        if github_sg_id:
            new_sgs.append(github_sg_id)
        if admin_sg_id:
            new_sgs.append(admin_sg_id)
        
        # Add web traffic security group
        if web_sg_id:
            new_sgs.append(web_sg_id)
        
        # Keep existing security groups that have HTTP/HTTPS rules or other non-SSH services
        for sg_id in current_sgs:
            if sg_id not in [github_sg_id, admin_sg_id, web_sg_id]:
                try:
                    response = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
                    sg = response['SecurityGroups'][0]
                    sg_name = sg['GroupName']
                    
                    # Check if this security group has non-SSH rules (HTTP/HTTPS/other services)
                    has_non_ssh_rules = any(
                        rule.get('FromPort') != 22 or rule.get('ToPort') != 22
                        for rule in sg['IpPermissions']
                    )
                    
                    if has_non_ssh_rules or sg_name == 'default':
                        new_sgs.append(sg_id)
                        self._print_info(f"Keeping security group: {sg_id} ({sg_name}) - has non-SSH rules")
                    else:
                        self._print_info(f"Removing SSH-only security group: {sg_id} ({sg_name})")
                        
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
    
    def cleanup_ssh_security_groups(self):
        """Cleanup SSH and web security groups"""
        sg_names = [self.github_sg_name, self.admin_sg_name, self.web_sg_name, self.legacy_sg_name]
        
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
        
        # Security Groups Status
        sg_names = [self.github_sg_name, self.admin_sg_name, self.web_sg_name]
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
                        self._print_success(f"Security Group {sg_name}: {len(web_rules)} HTTP/HTTPS rules")
                    else:
                        # Count SSH rules for SSH SGs
                        ssh_rules = [rule for rule in sg['IpPermissions'] 
                                   if rule.get('FromPort') == 22]
                        self._print_success(f"Security Group {sg_name}: {len(ssh_rules)} SSH rules")
                else:
                    self._print_warning(f"Security Group {sg_name}: Not found")
                    
            except ClientError:
                self._print_warning(f"Security Group {sg_name}: Error checking")
    
    # ========== SSH CONNECTIVITY CHECKS ==========
    
    def check_ssh_connectivity(self, test_github_actions: bool = True):
        """Check SSH connectivity for deployment workflows"""
        self._print_header("🔍 SSH Connectivity Check")
        
        instance = self._find_jemya_instance()
        if not instance:
            self._print_error("No EC2 instance found")
            return False
        
        if instance['State']['Name'] != 'running':
            self._print_error(f"Instance is not running (state: {instance['State']['Name']})")
            return False
        
        if 'PublicIpAddress' not in instance:
            self._print_error("Instance has no public IP address")
            return False
        
        public_ip = instance['PublicIpAddress']
        instance_id = instance['InstanceId']
        
        self._print_info(f"Instance: {instance_id}")
        self._print_info(f"Public IP: {public_ip}")
        
        # Check security groups
        current_sgs = {sg['GroupName']: sg['GroupId'] for sg in instance['SecurityGroups']}
        self._print_info(f"Security Groups: {', '.join(current_sgs.keys())}")
        
        # Test SSH port connectivity
        if not self._test_port_connectivity(public_ip, 22):
            self._print_error("SSH port (22) is not accessible")
            return False
        
        # Check GitHub Actions IP access if requested
        if test_github_actions:
            if not self._check_github_actions_access(current_sgs):
                return False
        
        # Test actual SSH connection if key is available
        key_file = f"{self.project_name}-key.pem"
        if os.path.exists(key_file):
            if self._test_ssh_connection(public_ip, key_file):
                self._print_success("SSH connection successful!")
                return True
            else:
                self._print_error("SSH connection failed")
                return False
        else:
            self._print_warning(f"SSH key file not found: {key_file}")
            self._print_info("Cannot test actual SSH connection without key file")
            self._print_success("Port connectivity check passed")
            return True
    
    def _test_port_connectivity(self, host: str, port: int, timeout: int = 10) -> bool:
        """Test if a port is accessible on a host"""
        import socket
        
        try:
            sock = socket.create_connection((host, port), timeout)
            sock.close()
            self._print_success(f"Port {port} is accessible on {host}")
            return True
        except (socket.timeout, socket.error) as e:
            self._print_error(f"Port {port} is not accessible on {host}: {e}")
            return False
    
    def _check_github_actions_access(self, current_sgs: Dict[str, str]) -> bool:
        """Check if GitHub Actions security group is properly configured"""
        github_sg_id = current_sgs.get(self.github_sg_name)
        
        if not github_sg_id:
            self._print_error(f"GitHub Actions security group '{self.github_sg_name}' not attached to instance")
            return False
        
        try:
            # Check if GitHub Actions SG has SSH rules
            response = self.ec2_client.describe_security_groups(GroupIds=[github_sg_id])
            sg = response['SecurityGroups'][0]
            
            ssh_rules = [rule for rule in sg['IpPermissions'] 
                        if rule.get('FromPort') == 22 and rule.get('ToPort') == 22]
            
            if not ssh_rules:
                self._print_error(f"No SSH rules found in {self.github_sg_name}")
                return False
            
            # Count IP ranges
            total_ranges = sum(len(rule.get('IpRanges', [])) for rule in ssh_rules)
            self._print_success(f"GitHub Actions security group has {total_ranges} SSH IP ranges")
            
            # Test a sample GitHub Actions IP
            if self._test_github_actions_ip_sample():
                self._print_success("GitHub Actions IP ranges appear to be working")
                return True
            else:
                self._print_warning("Could not verify GitHub Actions IP access")
                return True  # Don't fail the check, just warn
                
        except ClientError as e:
            self._print_error(f"Failed to check GitHub Actions security group: {e}")
            return False
    
    def _test_github_actions_ip_sample(self) -> bool:
        """Test if current public IP would be allowed by GitHub Actions rules"""
        try:
            # Get current public IP
            response = requests.get('https://api.ipify.org', timeout=10)
            current_ip = ipaddress.ip_address(response.text.strip())
            
            # Get GitHub Actions IPs
            github_ips = self.fetch_github_actions_ips()
            if not github_ips:
                return False
            
            # Check if current IP would be covered by any GitHub Actions range
            for ip_range in github_ips:
                network = ipaddress.ip_network(ip_range, strict=False)
                if current_ip in network:
                    self._print_info(f"Current IP {current_ip} is covered by GitHub Actions range {ip_range}")
                    return True
            
            self._print_info(f"Current IP {current_ip} is not in GitHub Actions ranges (this is normal)")
            return True
            
        except Exception:
            return False
    
    def _test_ssh_connection(self, host: str, key_file: str, timeout: int = 30) -> bool:
        """Test actual SSH connection to the host"""
        try:
            # Test SSH connection with a simple command
            cmd = [
                'ssh',
                '-i', key_file,
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', f'ConnectTimeout={timeout}',
                '-o', 'BatchMode=yes',  # Non-interactive
                f'ubuntu@{host}',
                'echo "SSH connection successful"'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode == 0:
                self._print_success("SSH connection test passed")
                return True
            else:
                self._print_error(f"SSH connection failed: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self._print_error("SSH connection timed out")
            return False
        except Exception as e:
            self._print_error(f"SSH connection test failed: {e}")
            return False
    
    def fix_deployment_connectivity(self):
        """Fix common deployment connectivity issues"""
        self._print_header("🔧 Fixing Deployment Connectivity Issues")
        
        # Check current status
        if not self.check_ssh_connectivity(test_github_actions=False):
            self._print_info("Attempting to fix connectivity issues...")
            
            # Refresh SSH security groups
            self._print_info("Refreshing SSH security groups...")
            self.setup_ssh_security_groups()
            
            # Wait a moment for changes to propagate
            time.sleep(5)
            
            # Check again
            if self.check_ssh_connectivity():
                self._print_success("Connectivity issues resolved!")
                return True
            else:
                self._print_error("Could not resolve connectivity issues")
                return False
        else:
            self._print_success("No connectivity issues found")
            return True
    
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
        
        # Setup SSH Security
        self.setup_ssh_security_groups()
        
        # Final summary
        self._print_header("🎉 Setup Complete!")
        
        print(f"\n{Colors.BOLD}Infrastructure Summary:{Colors.END}")
        print(f"  🐳 ECR Repository: {repo_uri}")
        print(f"  🖥️  EC2 Instance: {instance_id}")
        
        if access_key and secret_key:
            print(f"\n{Colors.BOLD}GitHub Secrets to Add:{Colors.END}")
            print(f"  AWS_ACCESS_KEY_ID: {access_key}")
            print(f"  AWS_SECRET_ACCESS_KEY: {secret_key}")
            print(f"  AWS_REGION: {self.region}")
            print(f"  ECR_REPOSITORY: {repo_uri}")
        
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
        self.cleanup_ssh_security_groups()
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
  ssh         Manage SSH security groups only
  status      Show current infrastructure status
  check-ssh   Check SSH connectivity for deployment workflows
  fix-ssh     Fix deployment connectivity issues
  
Examples:
  python3 aws_manager.py setup              # Complete setup
  python3 aws_manager.py cleanup --auto     # Automated cleanup
  python3 aws_manager.py ssh --admin-ip 1.2.3.4/32
  python3 aws_manager.py status             # Show current status
  python3 aws_manager.py check-ssh          # Test SSH connectivity
  python3 aws_manager.py fix-ssh            # Fix SSH issues
        """
    )
    
    parser.add_argument('command', choices=['setup', 'cleanup', 'ssh', 'status', 'check-ssh', 'fix-ssh'],
                        help='Command to execute')
    parser.add_argument('--region', default='eu-west-1',
                        help='AWS region (default: eu-west-1)')
    parser.add_argument('--auto', action='store_true',
                        help='Run in automatic mode (no interactive prompts)')
    parser.add_argument('--admin-ip', action='append',
                        help='Admin IP address in CIDR format (for ssh command)')
    
    args = parser.parse_args()
    
    # Create manager
    manager = JemyaAWSManager(region=args.region, auto_mode=args.auto)
    
    # Execute command
    if args.command == 'setup':
        manager.setup_complete_infrastructure()
    elif args.command == 'cleanup':
        manager.cleanup_complete_infrastructure()
    elif args.command == 'ssh':
        manager.setup_ssh_security_groups(admin_ips=args.admin_ip or [])
    elif args.command == 'status':
        manager.show_status()
    elif args.command == 'check-ssh':
        manager.check_ssh_connectivity()
    elif args.command == 'fix-ssh':
        manager.fix_deployment_connectivity()


if __name__ == '__main__':
    main()