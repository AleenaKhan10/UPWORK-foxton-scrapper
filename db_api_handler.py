import requests
import json
import time
import os
import jwt
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseAPIHandler:
    """
    Comprehensive API handler for property database operations.
    Handles authentication, token refresh, property posting with integrated image uploads.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the API handler with configuration.
        
        Args:
            config: API configuration dictionary
        """
        self.config = config
        self.base_url = config.get('base_url', '').rstrip('/')
        self.listing_endpoint = config.get('listing_endpoint', '/api/Listing/Upsert')
        self.token_refresh_endpoint = config.get('token_refresh_endpoint', '/api/auth/refresh')
        
        # Authentication
        self.access_token = config.get('token', '')
        self.refresh_token = config.get('refresh_token', '')
        self.user_id = config.get('user_id', '')
        
        # Settings
        self.timeout = config.get('timeout', 60)
        self.max_retries = config.get('max_retries', 3)
        self.retry_delay = config.get('retry_delay', 5)
        self.delay_between_requests = config.get('delay_between_requests', 1)
        
        # Location settings
        self.country_id = config.get('country_id', 1)
        self.state_id = config.get('state_id', 1)
        self.city_id = config.get('city_id', 1)
        
        # Control flags
        self.enabled = config.get('enabled', True)
        self.upload_images = config.get('upload_images', True)
        self.debug_mode = config.get('debug_mode', False)
        
        # Initialize headers
        self._update_headers()
        
        # API statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0,
            'images_uploaded': 0,
            'properties_posted': 0
        }
        
        logger.info(f"🔧 API Handler initialized - {'Enabled' if self.enabled else 'Disabled'}")
        if self.enabled and not self.access_token:
            logger.warning("⚠️ API enabled but no access token provided")
    
    def _update_headers(self):
        """Update request headers with current token"""
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "User-Agent": "Foxtons-Property-Scraper/2.0"
        }
    

    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using the refresh token.
        
        Returns:
            True if token was successfully refreshed
        """
        if not self.refresh_token or not self.access_token:
            logger.error("❌ Both access token and refresh token are required for token refresh")
            return False

        refresh_url = f"{self.base_url}/api/Auth/refresh-token"
        payload = {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token
        }

        try:
            logger.info(f"🔄 Attempting token refresh at: {refresh_url}")
            response = requests.post(
                refresh_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
                
            logger.info(f"📡 Refresh response: {response.status_code}")
                
            if response.status_code == 200:
                result = response.json()
                new_access_token = result.get('accessToken') or result.get('access_token') or result.get('token')
                new_refresh_token = result.get('refreshToken') or result.get('refresh_token')
                
                if new_access_token:
                    old_token_preview = self.access_token[:20] + "..." if len(self.access_token) > 20 else self.access_token
                    new_token_preview = new_access_token[:20] + "..." if len(new_access_token) > 20 else new_access_token
                    
                    logger.info(f"🔄 Updating token: {old_token_preview} -> {new_token_preview}")
                    
                    self.access_token = new_access_token
                    if new_refresh_token:
                        self.refresh_token = new_refresh_token
                        logger.info("🔄 Refresh token also updated")
                    
                    self._update_headers()
                    self.stats['token_refreshes'] += 1
                    
                    logger.info("✅ Access token refreshed successfully")
                    return True
                else:
                    logger.warning(f"⚠️ No access token in refresh response: {result}")
                    
            elif response.status_code == 404:
                logger.warning(f"⚠️ Refresh endpoint not found (404): {refresh_url}")
            elif response.status_code == 401:
                logger.error(f"❌ Refresh token is invalid or expired (401)")
                return False  # Don't try other endpoints if refresh token is bad
                
            else:
                logger.warning(f"⚠️ Refresh failed with {response.status_code}: {response.text}")
                
        except Exception as e:
            logger.warning(f"⚠️ Refresh attempt failed: {str(e)}")
        
        logger.error("❌ All token refresh attempts failed")
        return False
    
    def _make_request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """
        Make an API request with automatic token refresh and retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request parameters
            
        Returns:
            Response object or None if all retries failed
        """
        if not self.enabled:
            logger.info("🔧 API calls disabled")
            return None
        
        for attempt in range(self.max_retries):
            try:
                # Update headers in kwargs if not provided
                if 'headers' not in kwargs:
                    kwargs['headers'] = self.headers.copy()
                
                # Add timeout if not provided
                if 'timeout' not in kwargs:
                    kwargs['timeout'] = self.timeout
                
                self.stats['total_requests'] += 1
                
                if self.debug_mode:
                    logger.debug(f"🌐 {method} {url} (attempt {attempt + 1})")
                
                response = requests.request(method, url, **kwargs)
                
                # Handle successful responses
                if response.status_code in [200, 201]:
                    self.stats['successful_requests'] += 1
                    return response
                
                # Handle authentication errors
                elif response.status_code == 401:
                    logger.warning(f"🔐 Authentication error (401) on attempt {attempt + 1}")
                    logger.warning(f"🔐 Response: {response.text}")
                    
                    if attempt < self.max_retries - 1:  # Don't refresh on last attempt
                        logger.info("🔄 Attempting to refresh access token due to 401 error...")
                        
                        if self.refresh_access_token():
                            logger.info("✅ Token refreshed successfully, updating headers and retrying...")
                            # Update the headers for the retry attempt
                            if 'headers' in kwargs:
                                kwargs['headers'] = self.headers.copy()
                            else:
                                kwargs['headers'] = self.headers.copy()
                            
                            # Remove Content-Type if it's a file upload (multipart)
                            if 'files' in kwargs and 'Content-Type' in kwargs['headers']:
                                del kwargs['headers']['Content-Type']
                            
                            continue
                        else:
                            logger.error("❌ Token refresh failed, cannot retry request")
                            break
                    else:
                        logger.error("❌ Authentication failed on final attempt, no more retries")
                
                # Handle other errors
                else:
                    logger.warning(f"⚠️ API error {response.status_code}: {response.text}")
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_delay)
                        continue
                
                # If we reach here, log the final failure
                if attempt == self.max_retries - 1:
                    logger.error(f"❌ Request failed after {self.max_retries} attempts")
                    self.stats['failed_requests'] += 1
                
                return response
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Request timeout (attempt {attempt + 1})")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"🌐 Network error (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                    
            except Exception as e:
                logger.error(f"❌ Unexpected error (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        
        self.stats['failed_requests'] += 1
        return None
    
    def prepare_property_form_data(self, property_data: Dict[str, Any]) -> Tuple[Dict[str, str], List[Tuple[str, Any]]]:
        """
        Prepare property data and images for multipart form upload.
        
        Args:
            property_data: Scraped property data
            
        Returns:
            Tuple of (form_data_dict, files_list)
        """
        # Map data to API format
        api_data = self.map_property_to_api_format(property_data)
        
        # Convert API data to form fields (excluding ListingMedias which will be files)
        form_data = {}
        for key, value in api_data.items():
            if key != 'ListingMedias':
                if isinstance(value, (list, dict)):
                    form_data[key] = json.dumps(value)
                else:
                    form_data[key] = str(value)
        
        # Prepare image files
        files = []
        if self.upload_images:
            images = property_data.get('images', [])
            images_uploaded = 0
            
            for i, image_data in enumerate(images):
                try:
                    local_path = image_data.get('local_path')
                    if local_path and os.path.exists(local_path):
                        # Open file for upload
                        file_obj = open(local_path, 'rb')
                        filename = os.path.basename(local_path)
                        
                        # Add to files list for ListingMedias array
                        files.append(('ListingMedias', (filename, file_obj, 'image/jpeg')))
                        images_uploaded += 1
                        
                        logger.info(f"📤 Prepared image {i+1}: {filename}")
                    else:
                        logger.warning(f"⚠️ Image {i+1} not found: {local_path}")
                        
                except Exception as e:
                    logger.error(f"❌ Error preparing image {i+1}: {str(e)}")
            
            self.stats['images_uploaded'] += images_uploaded
            logger.info(f"✅ Prepared {images_uploaded}/{len(images)} images for upload")
        
        return form_data, files
    
    def _extract_postal_code(self, address: str) -> str:
        """
        Extract postal code from address string.
        
        Args:
            address: Full address string
            
        Returns:
            Postal code or default value
        """
        import re
        
        # UK postal code pattern (e.g., SW11, W1A 0AX, EC1A 1BB)
        postal_patterns = [
            r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b',  # Full UK postcodes (SW11 2AB)
            r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\b'  # Partial UK postcodes (SW11)
        ]
        
        for pattern in postal_patterns:
            match = re.search(pattern, address.upper())
            if match:
                return match.group().strip()
        
        # If no postal code found, return default
        return "Unknown"
    
    def _extract_unit_number(self, address: str) -> str:
        """
        Extract unit/apartment/flat number from address.
        
        Args:
            address: Full address string
            
        Returns:
            Unit number or default value
        """
        import re
        
        # Look for common patterns like "Flat 1", "Apartment 2A", "Unit 5", etc.
        unit_patterns = [
            r'(?:Flat|Apartment|Unit|Apt\.?)\s*(\w+)',
            r'(\d+[A-Z]?)\s*(?:Flat|Apartment|Unit)',
            r'#(\w+)',  # Hash number format
        ]
        
        address_upper = address.upper()
        for pattern in unit_patterns:
            match = re.search(pattern, address_upper, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no unit number found, return default
        return "N/A"

    def map_property_to_api_format(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map scraped property data to API format.
        
        Args:
            property_data: Scraped property data
            
        Returns:
            API-formatted property data
        """
        # Extract and validate data
        address = property_data.get('address', '').strip()
        if not address:
            raise ValueError("Street address is required but not found")
        
        # Extract postal code from address (e.g., "Yvon House, Battersea, SW11" -> "SW11")
        postal_code = self._extract_postal_code(address)
        
        # Extract unit number if available (apartment number, flat number, etc.)
        unit_number = self._extract_unit_number(address)
        
        price_str = property_data.get('price', '').replace('£', '').replace('Â£', '').replace(',', '').strip()
        # Handle other possible pound symbol encodings
        import re
        price_str = re.sub(r'[£¢Â£]', '', price_str)  # Remove various pound symbol encodings
        try:
            price = float(price_str) if price_str else 0.0
        except ValueError:
            logger.warning(f"⚠️ Could not parse price: '{property_data.get('price', '')}'")
            price = 0.0
        
        rooms = property_data.get('rooms', {})
        bedrooms = rooms.get('beds', 0) if isinstance(rooms.get('beds'), int) else 0
        bathrooms = rooms.get('baths', 0) if isinstance(rooms.get('baths'), int) else 0
        
        # Extract total area
        further_details = property_data.get('further_details', {})
        total_sq_ft = further_details.get('Total Sq Ft', '')
        total_area = 0.0
        if isinstance(total_sq_ft, str) and total_sq_ft:
            try:
                area_part = total_sq_ft.split('(')[0].replace(',', '').strip()
                total_area = float(area_part)
            except (ValueError, IndexError):
                total_area = 0.0
        
        # Property condition mapping
        property_type = property_data.get('property_type', '').lower()
        property_condition = 'Good'  # Default
        if 'new' in property_type or 'modern' in property_type:
            property_condition = 'Excellent'
        elif 'refurbished' in property_type or 'renovated' in property_type:
            property_condition = 'Good'
        
        # EPC Rating
        epc_data = property_data.get('epc_rating', {})
        epc_rating = epc_data.get('current', '') if isinstance(epc_data, dict) else ''
        
        # Agent information
        agent_email = property_data.get('agent_email', '')
        if not agent_email or agent_email in ['Not available', 'Error']:
            agent_email = "info@foxtons.co.uk"
        
        agent_name = "Foxtons Agent"
        if '@' in agent_email:
            name_part = agent_email.split('@')[0]
            if name_part.lower() != 'info':
                agent_name = f"Foxtons {name_part.title()}"
        
        # Tube lines from nearest stations
        tube_lines = self._extract_tube_lines(property_data.get('nearest_stations', []))
        
        # Create API payload
        api_data = {
            "ListingId": 0,  # 0 for new listings
            "UserId": self.user_id,
            "CountryId": self.country_id,
            "StateId": self.state_id,
            "CityId": self.city_id,
            "StreetAddress": address,
            "UnitNumber": unit_number,  # Fixed: Use extracted unit number instead of empty string
            "PostalCodeId": 0,
            "PostalCodeText": postal_code,  # Fixed: Use extracted postal code instead of empty string
            "PropertyTypeId": 0,
            "PropertyCondition": property_condition,
            "Price": price,
            "Bedrooms": bedrooms,
            "Bathrooms": bathrooms,
            "TotalArea": total_area,
            "OutsideSpace": 0.0,
            "AgentName": agent_name,
            "AgentEmail": agent_email,
            # Removed ListingMediaToRemove as it causes validation error when empty
            "EPCRating": epc_rating,
            "EPCAccepted": True if epc_rating else False,
            "TubeLines": tube_lines,
            "Description": property_data.get('description', '')
        }
        
        return api_data
    
    def _extract_tube_lines(self, stations: List[Dict[str, Any]]) -> str:
        """Extract tube lines from nearest stations data"""
        tube_lines = []
        for station in stations:
            if isinstance(station, dict):
                station_name = station.get('station_name', '').upper()
                if station_name and station_name not in tube_lines:
                    tube_lines.append(station_name)
        return ', '.join(tube_lines[:3])  # Limit to 3 lines
    
    def post_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a property to the API with images included directly.
        
        Args:
            property_data: Complete property data including images
            
        Returns:
            Result dictionary with status and details
        """
        if not self.enabled:
            logger.info("🔧 API posting disabled")
            return {"status": "disabled", "message": "API posting is disabled"}
        
        if not self.access_token:
            logger.error("❌ No access token provided")
            return {"status": "error", "message": "No access token provided"}
        
        files_to_close = []
        try:
            property_id = property_data.get('property_id', 'unknown')
            logger.info(f"🚀 Posting property {property_id} to API with integrated image upload...")
            
            # Map data to API format
            api_data = self.map_property_to_api_format(property_data)
            
            # Prepare all data as multipart form data
            files = []
            
            # Add all property data fields
            for key, value in api_data.items():
                if isinstance(value, (list, dict)):
                    files.append((key, (None, json.dumps(value), 'application/json')))
                else:
                    files.append((key, (None, str(value), 'text/plain')))
            
            # Add image files
            if self.upload_images:
                images = property_data.get('images', [])
                images_uploaded = 0
                
                for i, image_data in enumerate(images):
                    try:
                        local_path = image_data.get('local_path')
                        if local_path and os.path.exists(local_path):
                            # Open file for upload
                            file_obj = open(local_path, 'rb')
                            filename = os.path.basename(local_path)
                            files_to_close.append(file_obj)
                            
                            # Add to files list for ListingMedias array
                            files.append(('ListingMedias', (filename, file_obj, 'image/jpeg')))
                            images_uploaded += 1
                            
                            logger.info(f"📤 Prepared image {i+1}: {filename}")
                        else:
                            logger.warning(f"⚠️ Image {i+1} not found: {local_path}")
                            
                    except Exception as e:
                        logger.error(f"❌ Error preparing image {i+1}: {str(e)}")
                
                self.stats['images_uploaded'] += images_uploaded
                logger.info(f"✅ Prepared {images_uploaded}/{len(images)} images for upload")
            
            # Post to API using multipart form data
            listing_url = f"{self.base_url}{self.listing_endpoint}"
            
            # Remove Content-Type from headers to let requests set it for multipart
            upload_headers = {k: v for k, v in self.headers.items() if k != 'Content-Type'}
            
            logger.info(f"📡 Posting property to API: {listing_url}")
            
            response = self._make_request(
                'POST', 
                listing_url, 
                files=files,
                headers=upload_headers
            )
            
            if response and response.status_code in [200, 201]:
                result = response.json()
                listing_id = result.get('id') or result.get('listingId') or result.get('ListingId')
                
                self.stats['properties_posted'] += 1
                logger.info(f"✅ Property {property_id} posted successfully with integrated image upload!")
                
                if listing_id:
                    logger.info(f"📋 Listing ID: {listing_id}")
                
                # Add delay between requests
                time.sleep(self.delay_between_requests)
                
                return {
                    "status": "success",
                    "listing_id": listing_id,
                    "message": "Property posted successfully with images",
                    "images_uploaded": len([f for f in files if f[0] == 'ListingMedias']),
                    "api_response": result
                }
            
            elif response:
                error_message = f"API error {response.status_code}: {response.text}"
                logger.error(f"❌ {error_message}")
                
                return {
                    "status": "error",
                    "message": error_message,
                    "http_status": response.status_code,
                    "api_url": listing_url
                }
            
            else:
                return {
                    "status": "error",
                    "message": "No response from API after all retries"
                }
                
        except ValueError as e:
            # Validation errors
            logger.error(f"❌ Validation error for property {property_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Validation error: {str(e)}"
            }
            
        except Exception as e:
            logger.error(f"❌ Unexpected error posting property {property_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }
        
        finally:
            # Close all opened file objects
            for file_obj in files_to_close:
                try:
                    file_obj.close()
                except:
                    pass
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return self.stats.copy()
    
    def reset_statistics(self):
        """Reset API usage statistics"""
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'token_refreshes': 0,
            'images_uploaded': 0,
            'properties_posted': 0
        }
        logger.info("📊 API statistics reset")


def create_api_handler(config_file_path: str = "api_config.py") -> DatabaseAPIHandler:
    """
    Create and configure an API handler instance.
    
    Args:
        config_file_path: Path to the configuration file
        
    Returns:
        Configured DatabaseAPIHandler instance
    """
    try:
        # Try to load configuration from file
        import importlib.util
        spec = importlib.util.spec_from_file_location("api_config", config_file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec from {config_file_path}")
        config_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config_module)
        
        if hasattr(config_module, 'get_api_config'):
            config = config_module.get_api_config()
        else:
            config = config_module.API_CONFIG
            
        logger.info(f"✅ Loaded API configuration from {config_file_path}")
        
    except Exception as e:
        logger.warning(f"⚠️ Could not load config from {config_file_path}: {str(e)}")
        logger.info("🔧 Using default configuration")
        
        # Fallback configuration
        config = {
            "base_url": "https://laddr.com",
            "listing_endpoint": "/api/Listing/Upsert",
            "token_refresh_endpoint": "/api/auth/refresh",
            "token": "",
            "refresh_token": "",
            "user_id": "waqar@lexumsoft.com",
            "country_id": 1,
            "state_id": 1,
            "city_id": 1,
            "enabled": False,  # Disabled by default without proper config
            "upload_images": True,
            "timeout": 60,
            "max_retries": 3,
            "retry_delay": 5,
            "delay_between_requests": 1,
            "debug_mode": False
        }
    
    return DatabaseAPIHandler(config)


# Example usage
if __name__ == "__main__":
    # Test the API handler
    api_handler = create_api_handler()
    
    # Print statistics
    stats = api_handler.get_statistics()
    print("📊 API Handler Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}") 