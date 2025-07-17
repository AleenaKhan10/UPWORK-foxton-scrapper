# API Configuration for Property Scraper
# Update these settings according to your API environment

import os
import jwt
from datetime import datetime, timezone

API_CONFIG = {
    # API Base URL - Correct Azure endpoint provided by user
    "base_url": "https://laddr-api.azurewebsites.net",
    
    # API Endpoints - Confirmed working endpoints
    "listing_endpoint": "/api/Listing/Upsert",
    "token_refresh_endpoint": "/api/auth/refresh",
    
    # Authentication Tokens
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ3YXFhckBsZXh1bXNvZnQuY29tIiwianRpIjoiYzdjODIxYzAtNTBiZC00NGVmLTk4MGItNzIzZjkzODM5ZjAzIiwiaHR0cDovL3NjaGVtYXMueG1sc29hcC5vcmcvd3MvMjAwNS8wNS9pZGVudGl0eS9jbGFpbXMvbmFtZWlkZW50aWZpZXIiOiJiNGU5NTYwZC1hNjBiLTQ3MzYtYWI1Yy0xMTRlOTViNDUyYWUiLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1lIjoiV2FxYXIgS2hhbiIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6IlVzZXIiLCJleHAiOjE3NTI3MTQ4ODIsImlzcyI6ImxhZGRyLmNvbSIsImF1ZCI6ImxhZGRyLmNvbSJ9.taqKB_UC2IrcLvMUl4eC2aBpDYRd_Jy6SpI7GdIpa6g",
    "refresh_token": "hV5sj31a5vLFhe3BZAmD3IzxwO3HVzq3H515twXBYKaS/I5DZHldVil6IPAQHdCWAUkQLCj1qj/W5GyArWeBDA==",  # Add refresh token here when available
    
    # User Information (from the provided token data)
    "user_id": 1,
    
    # Location IDs - Update these based on your database structure
    "country_id": 1,  # UK
    "state_id": 1,    # England/Greater London
    "city_id": 1,     # London
    
    # API Control Settings
    "enabled": True,  # Set to False to disable API posting completely
    "upload_images": True,  # Set to False to skip image uploads
    
    # Request Settings
    "timeout": 60,    # Request timeout in seconds (increased for image uploads)
    "max_retries": 3,  # Maximum number of retry attempts
    "retry_delay": 5,  # Delay between retries in seconds
    
    # Rate Limiting
    "delay_between_requests": 1,  # Delay between API requests in seconds
    "delay_between_images": 0.5,  # Delay between image uploads in seconds
    
    # Debug Settings
    "debug_mode": True,  # Set to True for verbose logging
    "save_api_requests": False,  # Set to True to save API request/response data
    
    # Token Management
    "auto_refresh_token": False,  # Automatically refresh tokens when expired
    "token_refresh_buffer": 300,  # Refresh token 5 minutes before expiration
}

def check_token_expiration(token):
    """
    Check if a JWT token is expired or will expire soon.
    
    Args:
        token (str): JWT token to check
        
    Returns:
        dict: Dictionary with expiration info
    """
    if not token:
        return {
            "is_expired": True,
            "expires_at": None,
            "expires_in": None,
            "message": "No token provided"
        }
    
    try:
        # Decode without verification to get expiration
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = decoded.get('exp')
        
        if not exp_timestamp:
            return {
                "is_expired": True,
                "expires_at": None,
                "expires_in": None,
                "message": "No expiration claim in token"
            }
        
        current_time = datetime.now(timezone.utc).timestamp()
        expires_in = exp_timestamp - current_time
        expires_at = datetime.fromtimestamp(exp_timestamp, timezone.utc)
        
        # Check if token expires within buffer time
        buffer_time = API_CONFIG.get('token_refresh_buffer', 300)
        is_expired = expires_in <= buffer_time
        
        return {
            "is_expired": is_expired,
            "expires_at": expires_at.isoformat(),
            "expires_in": max(0, expires_in),
            "message": f"Token {'expires soon' if is_expired else 'is valid'}"
        }
        
    except Exception as e:
        return {
            "is_expired": True,
            "expires_at": None,
            "expires_in": None,
            "message": f"Error checking token: {str(e)}"
        }

def validate_config():
    """
    Validate the API configuration and check token status.
    
    Returns:
        dict: Validation results
    """
    errors = []
    warnings = []
    
    # Required fields validation
    required_fields = ["base_url", "token"]
    for field in required_fields:
        if not API_CONFIG.get(field):
            errors.append(f"{field} is required")
    
    # Numeric fields validation
    numeric_fields = ["country_id", "state_id", "city_id", "timeout", "max_retries"]
    for field in numeric_fields:
        if API_CONFIG.get(field, 0) <= 0:
            errors.append(f"{field} must be greater than 0")
    
    # URL validation
    base_url = API_CONFIG.get("base_url", "")
    if base_url and not (base_url.startswith("http://") or base_url.startswith("https://")):
        errors.append("base_url must start with http:// or https://")
    
    # Basic token presence check (no expiration validation)
    if not API_CONFIG.get("token"):
        warnings.append("No access token provided")
    
    # Refresh token check
    if not API_CONFIG.get("refresh_token") and API_CONFIG.get("auto_refresh_token", False):
        warnings.append("Auto refresh enabled but no refresh token provided")
    
    # Endpoint validation
    endpoints = ["listing_endpoint", "token_refresh_endpoint"]
    for endpoint in endpoints:
        if not API_CONFIG.get(endpoint, "").startswith("/"):
            warnings.append(f"{endpoint} should start with '/'")
    
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "token_info": check_token_expiration(API_CONFIG.get("token")) # Keep token info for now, but it's not validated
    }

def get_api_config():
    """
    Get validated API configuration.
    
    Returns:
        dict: API configuration or disabled config if validation fails
    """
    validation = validate_config()
    
    if validation["is_valid"]:
        print("✅ API Configuration validated successfully")
        
        # Show warnings if any
        if validation["warnings"]:
            print("⚠️ Configuration warnings:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
        
        # Show token info
        token_info = validation["token_info"]
        if not token_info["is_expired"]:
            expires_at = token_info["expires_at"]
            if expires_at:
                print(f"🔑 Token expires at: {expires_at}")
        
        return API_CONFIG
    else:
        print("❌ API Configuration Errors:")
        for error in validation["errors"]:
            print(f"  - {error}")
        
        if validation["warnings"]:
            print("⚠️ Configuration warnings:")
            for warning in validation["warnings"]:
                print(f"  - {warning}")
        
        # Return disabled configuration if validation fails
        disabled_config = API_CONFIG.copy()
        disabled_config["enabled"] = False
        return disabled_config

def update_tokens(new_access_token, new_refresh_token=None):
    """
    Update tokens in the configuration (for runtime updates).
    
    Args:
        new_access_token (str): New access token
        new_refresh_token (str, optional): New refresh token
    """
    global API_CONFIG
    
    API_CONFIG["token"] = new_access_token
    if new_refresh_token:
        API_CONFIG["refresh_token"] = new_refresh_token
    
    print("🔄 Tokens updated in configuration")

def get_environment_config():
    """
    Load configuration from environment variables (useful for production).
    
    Returns:
        dict: Configuration from environment variables
    """
    env_config = {
        "base_url": os.getenv("API_BASE_URL", API_CONFIG["base_url"]),
        "token": os.getenv("API_ACCESS_TOKEN", API_CONFIG["token"]),
        "refresh_token": os.getenv("API_REFRESH_TOKEN", API_CONFIG["refresh_token"]),
        "user_id": os.getenv("API_USER_ID", API_CONFIG["user_id"]),
        "enabled": os.getenv("API_ENABLED", str(API_CONFIG["enabled"])).lower() == "true",
        "debug_mode": os.getenv("API_DEBUG_MODE", str(API_CONFIG["debug_mode"])).lower() == "true",
    }
    
    # Update main config with environment values
    config = API_CONFIG.copy()
    config.update({k: v for k, v in env_config.items() if v})
    
    return config

# Load configuration with validation on import
if __name__ == "__main__":
    # Test configuration when run directly
    print("🔧 Testing API Configuration...")
    config = get_api_config()
    
    token_info = check_token_expiration(config.get("token"))
    print(f"\n📊 Token Status:")
    print(f"  Valid: {not token_info['is_expired']}")
    print(f"  Message: {token_info['message']}")
    if token_info["expires_at"]:
        print(f"  Expires: {token_info['expires_at']}")
    if token_info["expires_in"] is not None:
        print(f"  Expires in: {token_info['expires_in']:.0f} seconds")
    
    print(f"\n🌐 API Endpoints:")
    print(f"  Base URL: {config['base_url']}")
    print(f"  Listing: {config['base_url']}{config['listing_endpoint']}")
    print(f"  Token Refresh: {config['base_url']}{config['token_refresh_endpoint']}")
    
    print(f"\n🎛️ Settings:")
    print(f"  Enabled: {config['enabled']}")
    print(f"  Upload Images: {config['upload_images']}")
    print(f"  Debug Mode: {config['debug_mode']}") 