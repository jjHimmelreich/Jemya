"""
Smart Configuration Loader for Jemya Playlist Generator
Automatically selects the appropriate configuration based on environment:
- Local development: Uses conf.py (with hardcoded tokens)
- AWS deployment: Uses conf_aws.py (with environment variables)
"""
import os
import sys

def is_aws_environment():
    """Detect if we're running on AWS"""
    aws_indicators = [
        'AWS_EXECUTION_ENV',        # AWS Lambda/App Runner
        'AWS_REGION',               # AWS environment variable
        'ECS_CONTAINER_METADATA_URI', # ECS/Fargate
        'LAMBDA_RUNTIME_DIR',       # Lambda
        'APP_RUNNER_ENV'            # Custom indicator for App Runner
    ]
    
    return any(os.getenv(indicator) for indicator in aws_indicators)

def is_production_environment():
    """Check if ENVIRONMENT is set to production"""
    return os.getenv('ENVIRONMENT', '').lower() == 'production'

# Determine which configuration to use
if is_aws_environment() or is_production_environment():
    print("🌐 Loading AWS/Production configuration...")
    try:
        from conf_aws import *
        ENVIRONMENT = 'production'
        print("✅ AWS configuration loaded successfully")
    except ImportError as e:
        print(f"❌ Failed to load AWS configuration: {e}")
        print("💡 Falling back to local configuration...")
        from conf import *
        ENVIRONMENT = 'development'
else:
    print("🏠 Loading local development configuration...")
    try:
        from conf import *
        ENVIRONMENT = 'development'
        print("✅ Local configuration loaded successfully")
    except ImportError as e:
        print(f"❌ Failed to load local configuration: {e}")
        print("💡 Attempting AWS configuration...")
        try:
            from conf_aws import *
            ENVIRONMENT = 'production'
            print("✅ AWS configuration loaded as fallback")
        except ImportError as e2:
            print(f"❌ No configuration available: {e2}")
            sys.exit(1)

# Display configuration info (without exposing secrets)
print(f"🔧 Environment: {ENVIRONMENT}")
if ENVIRONMENT == 'development':
    print(f"🎯 Spotify Redirect URI: {SPOTIFY_REDIRECT_URI}")
else:
    print("🔒 Using environment variables for sensitive data")

# Validate required configuration
required_vars = ['SPOTIFY_CLIENT_ID', 'SPOTIFY_CLIENT_SECRET', 'SPOTIFY_REDIRECT_URI', 'OPENAI_API_KEY']
missing_vars = []

for var in required_vars:
    if var not in globals() or not globals()[var]:
        missing_vars.append(var)

if missing_vars:
    print(f"❌ Missing required configuration: {', '.join(missing_vars)}")
    if ENVIRONMENT == 'production':
        print("💡 Make sure environment variables are set in AWS App Runner")
    else:
        print("💡 Check your conf.py file")
    sys.exit(1)

print("✅ All required configuration loaded successfully")