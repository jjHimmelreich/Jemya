import boto3
import json
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    """
    AWS Lambda function to rotate IAM user access keys
    Triggered by CloudWatch Events every 90 days
    """
    
    # Configuration
    USERNAME = os.environ['IAM_USERNAME']  # jemya-github-actions
    GITHUB_REPO = os.environ['GITHUB_REPO']  # owner/repo
    GITHUB_TOKEN = os.environ['GITHUB_TOKEN']  # GitHub PAT with repo:write access
    
    iam = boto3.client('iam')
    
    try:
        # 1. Get current access keys
        current_keys = iam.list_access_keys(UserName=USERNAME)
        old_key_id = current_keys['AccessKeyMetadata'][0]['AccessKeyId']
        
        # 2. Create new access key
        new_key = iam.create_access_key(UserName=USERNAME)
        new_access_key_id = new_key['AccessKey']['AccessKeyId']
        new_secret_key = new_key['AccessKey']['SecretAccessKey']
        
        # 3. Update GitHub secrets (you'd need to implement GitHub API calls)
        update_github_secrets(GITHUB_REPO, GITHUB_TOKEN, {
            'AWS_ACCESS_KEY_ID': new_access_key_id,
            'AWS_SECRET_ACCESS_KEY': new_secret_key
        })
        
        # 4. Wait a bit for propagation
        import time
        time.sleep(30)
        
        # 5. Delete old access key
        iam.delete_access_key(UserName=USERNAME, AccessKeyId=old_key_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully rotated keys for user {USERNAME}',
                'new_key_id': new_access_key_id,
                'rotation_date': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error rotating keys: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def update_github_secrets(repo, token, secrets):
    """Update GitHub repository secrets via API"""
    import requests
    import base64
    from nacl import encoding, public
    
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Get repository public key
    key_url = f'https://api.github.com/repos/{repo}/actions/secrets/public-key'
    key_response = requests.get(key_url, headers=headers, timeout=30)
    public_key = key_response.json()
    
    for secret_name, secret_value in secrets.items():
        # Encrypt the secret
        public_key_obj = public.PublicKey(public_key['key'].encode(), encoding.Base64Encoder())
        sealed_box = public.SealedBox(public_key_obj)
        encrypted = sealed_box.encrypt(secret_value.encode())
        encrypted_value = base64.b64encode(encrypted).decode()
        
        # Update the secret
        secret_url = f'https://api.github.com/repos/{repo}/actions/secrets/{secret_name}'
        secret_data = {
            'encrypted_value': encrypted_value,
            'key_id': public_key['key_id']
        }
        requests.put(secret_url, headers=headers, json=secret_data, timeout=30)