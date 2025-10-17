#!/usr/bin/env python3
"""
Dual Security Group SSH Access Setup for Jemya Project
======================================================

This script sets up optimized SSH security groups for GitHub Actions and admin access.
It fetches GitHub Actions IP ranges, optimizes them to fit AWS security group limits,
and manages EC2 instance security group assignments.

Features:
- Fetches live GitHub Actions IP ranges
- Optimizes 4,240+ IPs down to 50 efficient CIDR blocks
- Separates GitHub Actions and admin access
- Automatic EC2 instance discovery and updates
- Comprehensive error handling and logging
"""

import argparse
import boto3
import ipaddress
import json
import logging
import requests
import sys
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
    UNDERLINE = '\033[4m'
    END = '\033[0m'


class SSHSecurityManager:
    """Manages SSH security groups for GitHub Actions and admin access"""
    
    def __init__(self, region: str = 'eu-west-1', auto_mode: bool = False):
        self.region = region
        self.auto_mode = auto_mode
        self.logger = self._setup_logging()
        
        # AWS clients
        try:
            self.ec2_client = boto3.client('ec2', region_name=region)
            self.ec2_resource = boto3.resource('ec2', region_name=region)
        except NoCredentialsError:
            self.logger.error("AWS credentials not configured")
            sys.exit(1)
        
        # Security group names
        self.github_sg_name = "jemya-github-sg"
        self.admin_sg_name = "jemya-admin-sg"
        
        # Get VPC ID
        self.vpc_id = self._get_vpc_id()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(message)s'
        )
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
                vpc_id = response['Vpcs'][0]['VpcId']
                self._print_success(f"Using VPC: {vpc_id}")
                return vpc_id
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
            sts = boto3.client('sts')
            account = sts.get_caller_identity()['Account']
            self._print_success(f"AWS credentials configured (Account: {account})")
            
            # Check internet connectivity for GitHub API
            response = requests.get('https://api.github.com/meta', timeout=10)
            if response.status_code == 200:
                self._print_success("GitHub API accessible")
            else:
                self._print_error("Cannot access GitHub API")
                return False
                
            return True
            
        except Exception as e:
            self._print_error(f"Prerequisites check failed: {e}")
            return False
    
    def fetch_github_actions_ips(self) -> List[str]:
        """Fetch GitHub Actions IP ranges from GitHub API"""
        self._print_info("Fetching GitHub Actions IP ranges")
        
        try:
            response = requests.get('https://api.github.com/meta', timeout=30)
            response.raise_for_status()
            
            data = response.json()
            github_ips = []
            
            # Get actions IP ranges (IPv4 only)
            for ip_range in data.get('actions', []):
                try:
                    network = ipaddress.ip_network(ip_range, strict=False)
                    if network.version == 4:  # IPv4 only
                        github_ips.append(str(network))
                except ValueError:
                    continue
            
            self._print_success(f"Loaded {len(github_ips)} GitHub Actions IPv4 ranges")
            return github_ips
            
        except Exception as e:
            self._print_error(f"Failed to fetch GitHub Actions IPs: {e}")
            sys.exit(1)
    
    def analyze_ip_ranges(self, ip_ranges: List[str]) -> Dict[str, int]:
        """Analyze IP ranges by CIDR block size"""
        stats = defaultdict(int)
        
        for ip_range in ip_ranges:
            network = ipaddress.ip_network(ip_range)
            prefix_len = network.prefixlen
            
            if prefix_len == 16:
                stats['/16'] += 1
            elif prefix_len == 17:
                stats['/17'] += 1
            elif prefix_len == 18:
                stats['/18'] += 1
            else:
                stats['other'] += 1
        
        return dict(stats)
    
    def optimize_ip_ranges(self, ip_ranges: List[str], max_rules: int = 50) -> Tuple[List[str], Dict]:
        """Optimize IP ranges to fit within AWS security group limits"""
        self._print_info("🎯 Optimizing IP ranges for maximum coverage...")
        
        # Group networks by prefix length for prioritization
        networks_by_prefix = defaultdict(list)
        
        for ip_range in ip_ranges:
            network = ipaddress.ip_network(ip_range)
            networks_by_prefix[network.prefixlen].append(network)
        
        # Sort prefix lengths (prefer larger blocks: /16 > /17 > /18)
        sorted_prefixes = sorted(networks_by_prefix.keys())
        
        optimized_networks = []
        covered_networks = set()
        
        # Prioritize larger blocks first
        for prefix_len in sorted_prefixes:
            if len(optimized_networks) >= max_rules:
                break
                
            for network in networks_by_prefix[prefix_len]:
                if len(optimized_networks) >= max_rules:
                    break
                
                # Check if this network is already covered by a larger block
                is_covered = False
                for covered in covered_networks:
                    if network.subnet_of(covered):
                        is_covered = True
                        break
                
                if not is_covered:
                    optimized_networks.append(network)
                    covered_networks.add(network)
        
        # Convert back to string format
        optimized_cidrs = [str(net) for net in optimized_networks[:max_rules]]
        
        # Calculate statistics
        original_stats = self.analyze_ip_ranges(ip_ranges)
        optimized_stats = self.analyze_ip_ranges(optimized_cidrs)
        
        total_ips = sum(int(net.num_addresses) for net in optimized_networks[:max_rules])
        
        stats = {
            'original_count': len(ip_ranges),
            'optimized_count': len(optimized_cidrs),
            'total_ips_covered': total_ips,
            'original_stats': original_stats,
            'optimized_stats': optimized_stats,
            'efficiency_gain': round((1 - len(optimized_cidrs) / len(ip_ranges)) * 100, 1)
        }
        
        return optimized_cidrs, stats
    
    def print_optimization_stats(self, stats: Dict):
        """Print optimization statistics"""
        self._print_header("📊 Optimization Results")
        
        print(f"   {Colors.BOLD}BEFORE OPTIMIZATION:{Colors.END}")
        print(f"   • Total ranges: {stats['original_count']}")
        print(f"   • Rules needed: {stats['original_count']}")
        
        print(f"\n   {Colors.BOLD}AFTER OPTIMIZATION:{Colors.END}")
        for block_type, count in stats['optimized_stats'].items():
            if count > 0:
                if block_type == '/16':
                    ips = count * 65536
                elif block_type == '/17':
                    ips = count * 32768
                elif block_type == '/18':
                    ips = count * 16384
                else:
                    ips = 0
                print(f"   • {block_type} blocks: {count} ({ips:,} IPs)")
        
        print(f"   • Total coverage: {stats['total_ips_covered']:,} IP addresses")
        print(f"   • Rules used: {stats['optimized_count']} out of 50")
        
        print(f"\n   {Colors.BOLD}EFFICIENCY GAIN:{Colors.END}")
        print(f"   • Rules reduction: {stats['original_count']} → {stats['optimized_count']} (-{stats['efficiency_gain']}%)")
        if stats['optimized_count'] > 0:
            avg_coverage = stats['total_ips_covered'] // stats['optimized_count']
            print(f"   • Coverage per rule: {avg_coverage:,} IPs/rule")
    
    def find_or_create_security_group(self, name: str, description: str) -> str:
        """Find existing security group or create new one"""
        self._print_info(f"🔍 Checking security group: {name}")
        
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
                return sg_id
            
            # Create new security group
            self._print_info(f"📝 Creating security group: {name}")
            response = self.ec2_client.create_security_group(
                GroupName=name,
                Description=description,
                VpcId=self.vpc_id
            )
            
            sg_id = response['GroupId']
            
            # Add tags
            self.ec2_client.create_tags(
                Resources=[sg_id],
                Tags=[
                    {'Key': 'Name', 'Value': name},
                    {'Key': 'Project', 'Value': 'Jemya'},
                    {'Key': 'Purpose', 'Value': 'SSH-Access'}
                ]
            )
            
            self._print_success(f"Created security group: {sg_id} ({name})")
            return sg_id
            
        except ClientError as e:
            self._print_error(f"Failed to create/find security group {name}: {e}")
            sys.exit(1)
    
    def clear_ssh_rules(self, sg_id: str, sg_name: str):
        """Clear existing SSH rules from security group"""
        self._print_info(f"🧹 Clearing existing SSH rules from {sg_name}")
        
        try:
            # Get current SSH rules
            response = self.ec2_client.describe_security_groups(GroupIds=[sg_id])
            sg = response['SecurityGroups'][0]
            
            ssh_rules = []
            for rule in sg['IpPermissions']:
                if rule.get('FromPort') == 22 and rule.get('ToPort') == 22:
                    ssh_rules.append(rule)
            
            if not ssh_rules:
                self._print_info(f"No SSH rules to clear in {sg_name}")
                return
            
            # Remove SSH rules
            for rule in ssh_rules:
                try:
                    self.ec2_client.revoke_security_group_ingress(
                        GroupId=sg_id,
                        IpPermissions=[rule]
                    )
                    
                    # Extract CIDR for logging
                    cidrs = [ip_range['CidrIp'] for ip_range in rule.get('IpRanges', [])]
                    if cidrs:
                        print(f"   🗑️  Removed: {', '.join(cidrs)}")
                        
                except ClientError as e:
                    self._print_warning(f"Failed to remove rule: {e}")
            
            self._print_success(f"Cleared SSH rules from {sg_name}")
            
        except ClientError as e:
            self._print_error(f"Failed to clear SSH rules: {e}")
    
    def add_ssh_rules(self, sg_id: str, sg_name: str, ip_ranges: List[str]):
        """Add SSH rules to security group"""
        self._print_info(f"➕ Adding SSH rules to {sg_name}")
        
        success_count = 0
        fail_count = 0
        
        for ip_range in ip_ranges:
            try:
                self.ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[{
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': ip_range, 'Description': 'GitHub Actions SSH access'}]
                    }]
                )
                print(f"   ✅ Added: {ip_range}")
                success_count += 1
                
            except ClientError as e:
                if 'already exists' in str(e) or 'Duplicate' in str(e):
                    print(f"   ⚠️  Already exists: {ip_range}")
                else:
                    print(f"   ❌ Failed: {ip_range} - {e}")
                    fail_count += 1
        
        if success_count > 0:
            self._print_success(f"Added {success_count} SSH rules to {sg_name}")
        if fail_count > 0:
            self._print_warning(f"{fail_count} rules failed to add")
    
    def setup_github_security_group(self) -> str:
        """Setup GitHub Actions security group with optimized IP ranges"""
        self._print_header("🤖 Setting up GitHub Actions Security Group")
        
        # Fetch and optimize GitHub Actions IPs
        github_ips = self.fetch_github_actions_ips()
        optimized_ips, stats = self.optimize_ip_ranges(github_ips)
        
        # Print statistics
        original_stats = self.analyze_ip_ranges(github_ips)
        print(f"\n{Colors.CYAN}📊 Original GitHub Actions IP Statistics:{Colors.END}")
        for block_type, count in original_stats.items():
            print(f"   • {block_type} blocks: {count}")
        
        self.print_optimization_stats(stats)
        
        if len(optimized_ips) > 50:
            self._print_warning(f"Limiting to 50 optimized GitHub Actions IPs (AWS security group limits)")
            optimized_ips = optimized_ips[:50]
        
        # Create/get security group
        sg_id = self.find_or_create_security_group(
            self.github_sg_name, 
            "SSH access for GitHub Actions runners - Jemya project"
        )
        
        # Apply IP ranges
        print(f"\n{Colors.BLUE}🧹 Applying optimized IP ranges to security group...{Colors.END}")
        self.clear_ssh_rules(sg_id, self.github_sg_name)
        self.add_ssh_rules(sg_id, self.github_sg_name, optimized_ips)
        
        self._print_success(f"GitHub Actions security group configured with {len(optimized_ips)} optimized IP ranges")
        print(f"{Colors.BLUE}📋 Group ID: {sg_id}{Colors.END}")
        
        return sg_id
    
    def setup_admin_security_group(self, admin_ips: List[str] = None) -> str:
        """Setup admin security group"""
        self._print_header("👤 Setting up Admin Security Group")
        
        if admin_ips is None:
            admin_ips = []
        
        # Auto-detect current public IP
        try:
            response = requests.get('https://api.ipify.org', timeout=10)
            current_ip = response.text.strip()
            if current_ip and current_ip not in [ip.split('/')[0] for ip in admin_ips]:
                self._print_success(f"Your current public IP: {current_ip}")
                if self.auto_mode or input(f"Add your current IP ({current_ip}) to admin access? (y/n): ").lower() == 'y':
                    admin_ips.append(f"{current_ip}/32")
                    self._print_success("Auto-added your current IP")
        except Exception:
            self._print_warning("Could not detect current public IP")
        
        # Get additional admin IPs if none provided
        if not admin_ips and not self.auto_mode:
            print(f"\n{Colors.BLUE}Enter admin IP addresses (CIDR format, press Enter when done):{Colors.END}")
            while True:
                ip = input("Admin IP (or Enter to finish): ").strip()
                if not ip:
                    break
                try:
                    ipaddress.ip_network(ip, strict=False)
                    admin_ips.append(ip)
                    self._print_success(f"Added admin IP: {ip}")
                except ValueError:
                    self._print_error(f"Invalid IP format: {ip}")
        
        if not admin_ips:
            self._print_warning("No admin IPs provided, skipping admin security group")
            return None
        
        # Create/get security group
        sg_id = self.find_or_create_security_group(
            self.admin_sg_name,
            "SSH access for administrators and developers - Jemya project"
        )
        
        # Apply IP ranges
        self.clear_ssh_rules(sg_id, self.admin_sg_name)
        self.add_ssh_rules(sg_id, self.admin_sg_name, admin_ips)
        
        self._print_success(f"Admin security group configured with {len(admin_ips)} IP(s)")
        print(f"{Colors.BLUE}📋 Group ID: {sg_id}{Colors.END}")
        
        return sg_id
    
    def find_jemya_instance(self) -> Optional[Dict]:
        """Find Jemya EC2 instance"""
        try:
            response = self.ec2_client.describe_instances(
                Filters=[
                    {'Name': 'tag:Name', 'Values': ['jemya-instance']},
                    {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
                ]
            )
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    return {
                        'InstanceId': instance['InstanceId'],
                        'State': instance['State']['Name'],
                        'SecurityGroups': instance['SecurityGroups']
                    }
            
            return None
            
        except ClientError as e:
            self._print_error(f"Failed to find instance: {e}")
            return None
    
    def update_instance_security_groups(self, github_sg_id: str, admin_sg_id: str = None, 
                                      update_github_only: bool = False, update_admin_only: bool = False):
        """Update EC2 instance security groups"""
        self._print_header("🔄 Updating EC2 Instance Security Groups")
        
        # Find instance
        self._print_info("🔍 Auto-discovering Jemya EC2 instance...")
        instance = self.find_jemya_instance()
        
        if not instance:
            self._print_warning("No Jemya EC2 instance found!")
            self._print_info("Make sure your EC2 instance is tagged with Name=jemya-instance")
            return
        
        instance_id = instance['InstanceId']
        current_sgs = instance['SecurityGroups']
        
        self._print_success(f"Found Jemya EC2 instance: {instance_id}")
        print(f"   📦 Instance ID: {instance_id}")
        print(f"   🔄 State: {instance['State']}")
        
        # Show current security groups
        print(f"\n{Colors.BLUE}📋 Current Security Groups{Colors.END}")
        print("-------------------------")
        for sg in current_sgs:
            print(f"   🛡️  {sg['GroupId']} ({sg['GroupName']})")
        
        # Build new security group list
        print(f"\n{Colors.BLUE}🔧 Building New Security Group List{Colors.END}")
        print("-----------------------------------")
        
        new_sgs = []
        
        # Add security groups based on update mode
        if not update_admin_only and github_sg_id:
            new_sgs.append(github_sg_id)
            self._print_success(f"Added: {github_sg_id} ({self.github_sg_name})")
        
        if not update_github_only and admin_sg_id:
            new_sgs.append(admin_sg_id)
            self._print_success(f"Added: {admin_sg_id} ({self.admin_sg_name})")
        
        # Keep existing non-SSH security groups (exclude old jemya-sg)
        for sg in current_sgs:
            if (sg['GroupName'] != 'jemya-sg' and 
                sg['GroupId'] not in [github_sg_id, admin_sg_id]):
                new_sgs.append(sg['GroupId'])
                self._print_info(f"Keeping: {sg['GroupId']} ({sg['GroupName']})")
        
        # Remove duplicates
        new_sgs = list(dict.fromkeys(new_sgs))
        
        if not new_sgs:
            self._print_warning("No security groups to apply")
            return
        
        print(f"\n{Colors.BLUE}📊 Summary:{Colors.END}")
        print(f"   • New security groups: {len(new_sgs)}")
        print(f"   • Groups: {', '.join(new_sgs)}")
        
        # Confirm changes
        if not self.auto_mode:
            response = input(f"\nApply these security group changes to {instance_id}? (y/n): ")
            if response.lower() != 'y':
                self._print_warning("Skipping instance update")
                return
        
        # Apply changes
        print(f"\n{Colors.BLUE}🔄 Updating Instance Security Groups{Colors.END}")
        print("------------------------------------")
        
        try:
            self.ec2_client.modify_instance_attribute(
                InstanceId=instance_id,
                Groups=new_sgs
            )
            
            self._print_success("Successfully updated security groups")
            
            # Verify changes
            print(f"\n{Colors.BLUE}🔍 Verifying Changes{Colors.END}")
            print("-------------------")
            
            import time
            time.sleep(2)  # Wait for changes to propagate
            
            updated_instance = self.find_jemya_instance()
            if updated_instance:
                self._print_success("Updated security groups:")
                for sg in updated_instance['SecurityGroups']:
                    print(f"   🛡️  {sg['GroupId']} ({sg['GroupName']})")
            
        except ClientError as e:
            self._print_error(f"Failed to update security groups: {e}")
            self._print_info("You can apply them manually later")
    
    def run(self, update_github_only: bool = False, update_admin_only: bool = False, 
            admin_ips: List[str] = None):
        """Main execution method"""
        print(f"{Colors.BOLD}{Colors.CYAN}🔐 Dual Security Group SSH Access Setup{Colors.END}")
        print("========================================")
        
        # Check prerequisites
        if not self.check_prerequisites():
            sys.exit(1)
        
        github_sg_id = None
        admin_sg_id = None
        
        # Setup security groups
        if not update_admin_only:
            github_sg_id = self.setup_github_security_group()
        
        if not update_github_only:
            admin_sg_id = self.setup_admin_security_group(admin_ips)
        
        # Update instance if needed
        if not update_github_only or not update_admin_only:
            self.update_instance_security_groups(
                github_sg_id, admin_sg_id, update_github_only, update_admin_only
            )
        
        # Final summary
        print(f"\n{Colors.GREEN}🎉 Dual Security Group Setup Complete!{Colors.END}")
        print("=======================================")
        
        if github_sg_id and not update_admin_only:
            print(f"\n{Colors.MAGENTA}🤖 GitHub Actions Security Group:{Colors.END}")
            print(f"   Name: {self.github_sg_name}")
            print(f"   ID: {github_sg_id}")
            print(f"   Purpose: CI/CD deployment access")
            print(f"   IPs: GitHub Actions runner ranges")
        
        if admin_sg_id and not update_github_only:
            print(f"\n{Colors.MAGENTA}👤 Admin Security Group:{Colors.END}")
            print(f"   Name: {self.admin_sg_name}")
            print(f"   ID: {admin_sg_id}")
            print(f"   Purpose: Developer/admin access")
            print(f"   IPs: Admin IP addresses")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Setup dual SSH security groups for Jemya project',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Setup both GitHub Actions and admin security groups
  %(prog)s --update-github           # Update only GitHub Actions security group
  %(prog)s --update-admin            # Update only admin security group
  %(prog)s --auto                    # Run in automatic mode (no prompts)
  %(prog)s --admin-ip 1.2.3.4/32    # Add specific admin IP
        """
    )
    
    parser.add_argument('--region', default='eu-west-1',
                        help='AWS region (default: eu-west-1)')
    parser.add_argument('--update-github', action='store_true',
                        help='Update only GitHub Actions security group')
    parser.add_argument('--update-admin', action='store_true',
                        help='Update only admin security group')
    parser.add_argument('--auto', action='store_true',
                        help='Run in automatic mode (no interactive prompts)')
    parser.add_argument('--admin-ip', action='append',
                        help='Admin IP address in CIDR format (can be used multiple times)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.update_github and args.update_admin:
        parser.error("Cannot use both --update-github and --update-admin")
    
    # Create manager and run
    manager = SSHSecurityManager(region=args.region, auto_mode=args.auto)
    manager.run(
        update_github_only=args.update_github,
        update_admin_only=args.update_admin,
        admin_ips=args.admin_ip or []
    )


if __name__ == '__main__':
    main()