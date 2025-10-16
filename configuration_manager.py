"""
Simple Configuration Module
Uses conf.py for local development, environment variables for production
"""
import os

def get_config(key: str, default: str = None):
    """Get configuration value from environment or conf.py fallback"""
    # First try environment variable
    value = os.getenv(key)
    if value:
        return value
    
    # Fallback to conf.py for local development
    try:
        import conf
        return getattr(conf, key, default)
    except ImportError:
        # conf.py doesn't exist, must be production
        if default is None:
            raise ValueError(f"Configuration {key} not found in environment variables")
        return default

# Configuration values
SPOTIFY_CLIENT_ID = get_config('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = get_config('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = get_config('SPOTIFY_REDIRECT_URI')
OPENAI_API_KEY = get_config('OPENAI_API_KEY')

# Optional AWS configuration
AWS_REGION = get_config('AWS_REGION', 'us-east-1')
ENVIRONMENT = get_config('ENVIRONMENT', 'development')

print(f"🔧 Configuration loaded - Environment: {ENVIRONMENT}")