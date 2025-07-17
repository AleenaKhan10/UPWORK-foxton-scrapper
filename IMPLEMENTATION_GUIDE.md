# Foxtons Scraper - Enhanced Implementation Guide

## Overview

This guide documents the comprehensive improvements made to the Foxtons property scraper system. The enhancements address data integrity, API authentication management, image upload optimization, and robust error handling.

## 🆕 What's New

### 1. **Dedicated Database API Handler** (`db_api_handler.py`)
- **Centralized API Management**: All API operations are now handled through a single, robust handler
- **Automatic Token Refresh**: Detects token expiration and automatically refreshes using refresh tokens
- **Retry Logic**: Built-in retry mechanisms with exponential backoff
- **Enhanced Error Handling**: Comprehensive error classification and recovery
- **Image Upload Integration**: Seamlessly uploads images as part of property posting
- **Statistics Tracking**: Monitors API usage, success rates, and performance metrics

### 2. **Advanced JSON Data Manager** (`json_data_manager.py`)
- **Data Validation**: Validates property data structure before saving
- **Automatic Backups**: Creates timestamped backups before each save operation
- **Data Integrity**: Ensures JSON serialization compatibility
- **Error Recovery**: Attempts to repair common data issues automatically
- **Duplicate Prevention**: Tracks scraped URLs to avoid duplicate processing
- **Comprehensive Logging**: Detailed logging for debugging and monitoring

### 3. **Enhanced API Configuration** (`api_config.py`)
- **Token Management**: Built-in token expiration checking and refresh capabilities
- **Environment Variables**: Support for production deployment with environment variables
- **Validation Framework**: Comprehensive configuration validation with clear error messages
- **Debug Support**: Enhanced debugging capabilities with request/response logging

### 4. **Improved Main Scraper** (`listing_details.py`)
- **Modular Architecture**: Uses the new API handler and data manager
- **Fallback Support**: Maintains backward compatibility with legacy systems
- **Enhanced Error Handling**: Better error recovery and data preservation
- **Progress Tracking**: Improved progress reporting and statistics

## 🏗️ Architecture

```
┌─────────────────────┐    ┌──────────────────────┐    ┌─────────────────────┐
│   listing_details.py│    │   db_api_handler.py  │    │ json_data_manager.py│
│   (Main Scraper)    │────│   (API Management)   │    │  (Data Persistence) │
└─────────────────────┘    └──────────────────────┘    └─────────────────────┘
           │                           │                           │
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       │
                               ┌───────▼────────┐
                               │  api_config.py │
                               │ (Configuration)│
                               └────────────────┘
```

## 🚀 Key Features

### **Robust Authentication Management**
- **JWT Token Validation**: Automatically checks token expiration
- **Refresh Token Support**: Seamlessly refreshes expired tokens
- **Fallback Handling**: Graceful degradation when authentication fails
- **Security**: Secure token storage and transmission

### **Intelligent Data Handling**
- **Data Validation**: Ensures all property records meet required schema
- **Backup System**: Automatic backups prevent data loss
- **Repair Mechanisms**: Automatically fixes common data issues
- **Serialization Safety**: Handles complex objects and ensures JSON compatibility

### **Enhanced Image Management**
- **Integrated Upload**: Images uploaded as part of property posting (no separate API calls)
- **Progress Tracking**: Real-time progress reporting for image uploads
- **Error Recovery**: Continues processing even if some images fail
- **Rate Limiting**: Respects API rate limits to prevent blocking

### **Comprehensive Error Handling**
- **Categorized Errors**: Different handling for validation, network, and authentication errors
- **Retry Logic**: Automatic retries with exponential backoff
- **Graceful Degradation**: System continues operating even with partial failures
- **Detailed Logging**: Comprehensive logging for debugging and monitoring

## 📋 Configuration

### **API Configuration** (`api_config.py`)

```python
API_CONFIG = {
    # Authentication
    "token": "your_access_token_here",
    "refresh_token": "your_refresh_token_here",  # NEW
    
    # API Endpoints
    "base_url": "https://laddr.com",
    "listing_endpoint": "/api/Listing/Upsert",
    "media_upload_endpoint": "/api/Media/Upload",
    "token_refresh_endpoint": "/api/auth/refresh",  # NEW
    
    # Enhanced Settings
    "auto_refresh_token": True,  # NEW
    "token_refresh_buffer": 300,  # NEW - Refresh 5 minutes before expiration
    "debug_mode": False,  # NEW
    
    # Rate Limiting
    "delay_between_requests": 1,
    "delay_between_images": 0.5,
    
    # Retry Configuration
    "max_retries": 3,
    "retry_delay": 5,
    "timeout": 60
}
```

### **Environment Variables Support** (NEW)

```bash
# Production deployment
export API_BASE_URL="https://api.laddr.com"
export API_ACCESS_TOKEN="your_token"
export API_REFRESH_TOKEN="your_refresh_token"
export API_ENABLED="true"
export API_DEBUG_MODE="false"
```

## 🔧 Usage

### **Basic Usage**
```python
from listing_details import PropertyDetailsScraper

# Initialize with enhanced components
scraper = PropertyDetailsScraper(
    csv_file_path="foxtons_secondary_urls_collection.csv",
    images_dir="property_images",
    output_file="property_details.json"
)

# Start scraping with automatic API posting and image uploads
scraper.scrape_all_properties()
```

### **Advanced Usage**
```python
from db_api_handler import create_api_handler
from json_data_manager import create_data_manager

# Create components separately for custom configuration
api_handler = create_api_handler("custom_api_config.py")
data_manager = create_data_manager("custom_data.json", max_backups=20)

# Use in scraper
scraper = PropertyDetailsScraper(
    csv_file_path="properties.csv",
    images_dir="images",
    output_file="results.json"
)
```

### **Testing Integration**
```python
# Run comprehensive tests
python test_integration.py
```

## 📊 Monitoring and Statistics

### **API Handler Statistics**
- Total requests made
- Success/failure rates
- Token refresh count
- Images uploaded
- Properties posted

### **Data Manager Statistics**
- Total records processed
- Valid/invalid record counts
- Successful saves
- Backups created

### **Access Statistics**
```python
# Get API statistics
stats = api_handler.get_statistics()
print(f"Success rate: {stats['successful_requests']/stats['total_requests']*100:.1f}%")

# Get data manager statistics
data_stats = data_manager.get_statistics()
print(f"Valid records: {data_stats['valid_records']}/{data_stats['total_records']}")
```

## 🛠️ Error Recovery

### **Automatic Recovery Mechanisms**
1. **Token Expiration**: Automatically refreshes tokens
2. **Network Issues**: Retries with exponential backoff
3. **Data Corruption**: Repairs common data issues
4. **Partial Failures**: Continues processing remaining items

### **Manual Recovery**
```python
# Repair data issues
repaired_count = data_manager.repair_data()
print(f"Repaired {repaired_count} records")

# Reset API statistics
api_handler.reset_statistics()

# Validate configuration
from api_config import validate_config
validation = validate_config()
if not validation['is_valid']:
    print("Configuration issues:", validation['errors'])
```

## 🔍 Debugging

### **Enable Debug Mode**
```python
# In api_config.py
API_CONFIG["debug_mode"] = True
API_CONFIG["save_api_requests"] = True
```

### **Check Token Status**
```python
from api_config import check_token_expiration
token_info = check_token_expiration("your_token")
print(f"Token status: {token_info['message']}")
```

### **Validate Data**
```python
# Validate existing data
validation = data_manager.validate_data_structure(data_manager.data)
if validation['invalid_records'] > 0:
    print(f"Found {validation['invalid_records']} invalid records")
    for i, errors in validation['property_errors'].items():
        print(f"Record {i}: {errors}")
```

## 🚨 Troubleshooting

### **Common Issues**

1. **"API Handler not available"**
   - Check that `db_api_handler.py` is in the correct directory
   - Verify API configuration is valid

2. **"Token expired" errors**
   - Ensure refresh token is configured
   - Check token expiration with `check_token_expiration()`

3. **"Data validation failed"**
   - Use `data_manager.repair_data()` to fix common issues
   - Check specific validation errors

4. **"Image upload failed"**
   - Verify image files exist in the specified paths
   - Check API endpoint configuration
   - Review rate limiting settings

### **Log File Locations**
- Application logs: Console output with timestamps
- API requests: Saved to files when `save_api_requests` is enabled
- Backup files: `backups/` directory with timestamped names

## 🔄 Migration Guide

### **From Legacy System**
1. **Backup existing data**: Copy `property_details.json`
2. **Update configuration**: Add new fields to `api_config.py`
3. **Install new modules**: Ensure all new files are in place
4. **Test integration**: Run `test_integration.py`
5. **Gradual rollout**: Test with a small dataset first

### **Configuration Migration**
```python
# Old configuration
OLD_CONFIG = {
    "base_url": "https://api.laddr.com",
    "token": "your_token",
    "enabled": True
}

# New configuration (add these fields)
NEW_FIELDS = {
    "refresh_token": "",
    "token_refresh_endpoint": "/api/auth/refresh",
    "auto_refresh_token": True,
    "debug_mode": False
}
```

## 📈 Performance Improvements

### **Speed Enhancements**
- **Parallel Processing**: Can process multiple properties concurrently
- **Smart Caching**: Avoids re-processing already scraped properties
- **Optimized Requests**: Reduced API calls through batching

### **Memory Management**
- **Streaming Data**: Processes large datasets without memory issues
- **Cleanup Routines**: Automatic cleanup of temporary files
- **Resource Management**: Proper browser and connection management

## 🔒 Security Enhancements

### **Token Security**
- **Automatic Rotation**: Tokens refreshed before expiration
- **Secure Storage**: No hardcoded tokens in production
- **Environment Variables**: Support for secure token management

### **Data Protection**
- **Backup Encryption**: Can be extended to encrypt backups
- **Access Control**: API handler manages all external communications
- **Audit Trail**: Comprehensive logging for security monitoring

## 📝 Best Practices

### **Configuration**
1. Use environment variables in production
2. Enable debug mode during development
3. Set appropriate rate limits
4. Configure proper backup retention

### **Monitoring**
1. Check API statistics regularly
2. Monitor token expiration
3. Review error logs
4. Validate data integrity

### **Deployment**
1. Test configuration before deployment
2. Use staged rollouts
3. Monitor initial performance
4. Have rollback procedures ready

## 🎯 Future Enhancements

### **Planned Features**
- **Distributed Processing**: Support for multiple worker instances
- **Real-time Monitoring**: Web dashboard for monitoring
- **Advanced Analytics**: Property market analysis features
- **API Rate Optimization**: Dynamic rate limiting based on API responses

### **Extensibility**
The modular architecture makes it easy to add:
- New data sources
- Additional API endpoints
- Custom validation rules
- Enhanced image processing

---

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section
2. Run the integration tests
3. Review log files
4. Validate configuration

Remember to always backup your data before making changes! 