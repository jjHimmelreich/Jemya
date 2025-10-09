"""
Configuration module for Jemya Playlist Generator
Supports both local development and AWS cloud deployment
"""
import os
from typing import Optional

def get_env_var(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with fallback to default"""
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is required but not set")
    return value

# Spotify API Configuration
SPOTIFY_CLIENT_ID = get_env_var('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = get_env_var('SPOTIFY_CLIENT_SECRET')

# Dynamic redirect URI based on environment
if os.getenv('AWS_EXECUTION_ENV'):
    # Running on AWS - use the App Runner URL
    SPOTIFY_REDIRECT_URI = get_env_var('SPOTIFY_REDIRECT_URI')
else:
    # Local development
    SPOTIFY_REDIRECT_URI = get_env_var('SPOTIFY_REDIRECT_URI', 'http://localhost:5555/callback')

# OpenAI API Configuration
OPENAI_API_KEY = get_env_var('OPENAI_API_KEY')

# AWS Configuration (optional - for enhanced features)
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET')
AWS_DYNAMODB_TABLE = os.getenv('AWS_DYNAMODB_TABLE')

# Application Configuration
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

print(f"Configuration loaded for environment: {ENVIRONMENT}")
if DEBUG:
    print(f"Spotify Redirect URI: {SPOTIFY_REDIRECT_URI}")
    print(f"AWS Region: {AWS_REGION}")