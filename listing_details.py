#!/usr/bin/env python3
"""
Property Details Scraper using Selenium
Reads property URLs from CSV and scrapes detailed information from each property page.
Enhanced with API integration for database posting.
"""

import csv
import json
import os
import time
import requests
from datetime import datetime
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import re

# Import our custom modules
try:
    from db_api_handler import create_api_handler
    from json_data_manager import create_data_manager
except ImportError as e:
    print(f"⚠️ Warning: Could not import custom modules: {e}")
    print("   Make sure db_api_handler.py and json_data_manager.py are in the same directory")
    
    # Fallback functions for compatibility
    create_api_handler = lambda *args, **kwargs: None
    create_data_manager = lambda *args, **kwargs: None

class PropertyDetailsScraper:
    def __init__(self, csv_file_path, images_dir="property_images", output_file="property_details.json", 
                 api_config=None):
        self.csv_file_path = csv_file_path
        self.images_dir = images_dir
        self.output_file = output_file
        
        # Initialize new data manager
        self.data_manager = create_data_manager(output_file)
        if self.data_manager:
            print(f"✅ JSON Data Manager initialized")
        else:
            print(f"⚠️ Using fallback data handling")
        self.scraped_data = []
        
        # Initialize API handler
        self.api_handler = create_api_handler()
        if self.api_handler:
            print(f"✅ API Handler initialized")
        else:
            print(f"⚠️ API Handler not available - using fallback")
        
        # Always setup API config for backward compatibility
        self.api_config = api_config or {}
        self.setup_api_config()
        
        # Create images directory if it doesn't exist
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        
        # Setup Chrome options for stability
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        # chrome_options.add_argument("--headless")  # Uncomment to run headless
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
    
    def setup_api_config(self):
        """Setup API configuration with defaults"""
        # Default API configuration
        default_config = {
            "base_url": "https://api.laddr.com",  # Update with actual API base URL
            "listing_endpoint": "/api/Listing/Upsert",
            "token": self.api_config.get("token", ""),
            "user_id": "waqar@lexumsoft.com",  # From the provided token data
            "country_id": 1,  # Default to UK - you may need to adjust
            "state_id": 1,    # Default - you may need to adjust  
            "city_id": 1,     # Default - you may need to adjust
            "enabled": True,  # Set to False to disable API posting
            "timeout": 30,    # API request timeout
            "max_retries": 3, # Maximum API retry attempts
            "retry_delay": 5  # Delay between retries
        }
        
        # Merge with provided config
        self.api_config = {**default_config, **self.api_config}
        
        # Setup headers
        self.api_headers = {
            "Authorization": f"Bearer {self.api_config['token']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Foxtons-Property-Scraper/1.0"
        }
        
        print(f"🔧 API Integration {'Enabled' if self.api_config['enabled'] else 'Disabled'}")
        if self.api_config['enabled'] and not self.api_config['token']:
            print("⚠️ Warning: API enabled but no token provided")
    
    def parse_price(self, price_str):
        """Extract numeric price from price string"""
        if not price_str:
            return 0.0
        
        # Remove currency symbols and commas, extract numbers
        price_cleaned = re.sub(r'[£,\s]', '', price_str)
        
        # Handle different price formats
        numbers = re.findall(r'\d+', price_cleaned)
        if numbers:
            # Take the first number as the main price
            return float(numbers[0])
        return 0.0
    
    def parse_area(self, area_str):
        """Extract numeric area from area string (sq ft)"""
        if not area_str:
            return 0.0
        
        # Look for area in different formats: "1,500 sq ft", "1500 Sq M", etc.
        area_match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)', area_str)
        if area_match:
            area_num = area_match.group(1).replace(',', '')
            return float(area_num)
        return 0.0
    
    def extract_address_parts(self, full_address):
        """Extract street address from full address"""
        if not full_address:
            return ""
        
        # Split by comma and take the first meaningful part
        parts = full_address.split(',')
        if parts:
            # Skip empty parts and return the first substantial address part
            for part in parts:
                part = part.strip()
                if len(part) > 3:  # Avoid very short parts
                    return part
        
        return full_address.strip()
    
    def extract_tube_lines(self, stations_data):
        """Extract tube lines from nearest stations data"""
        if not stations_data:
            return ""
        
        tube_lines = []
        for station in stations_data:
            station_info = station.get('station_info', '')
            station_name = station.get('station_name', '')
            
            # Look for common tube line indicators
            combined_text = f"{station_info} {station_name}".lower()
            
            # Common London tube line patterns
            line_patterns = [
                r'(central|northern|piccadilly|district|circle|hammersmith|metropolitan|jubilee|bakerloo|victoria|elizabeth|waterloo)[\s&]*(?:city)?[\s]*line',
                r'(dlr|overground)',
            ]
            
            for pattern in line_patterns:
                matches = re.findall(pattern, combined_text)
                for match in matches:
                    if match not in tube_lines:
                        tube_lines.append(match.title())
        
        return ", ".join(tube_lines) if tube_lines else ""
    
    def map_to_api_format(self, property_data):
        """Map scraped property data to API format"""
        try:
            # Extract required data with defaults
            rooms = property_data.get('rooms', {})
            bedrooms = rooms.get('beds', 0) or rooms.get('bedrooms', 0)
            bathrooms = rooms.get('baths', 0) or rooms.get('bathrooms', 0)
            
            # Parse area from further_details
            further_details = property_data.get('further_details', {})
            total_area = 0.0
            
            # Look for area in different possible fields
            area_fields = ['Total Sq Ft', 'Area', 'Floor Area', 'Total Area']
            for field in area_fields:
                if field in further_details:
                    total_area = self.parse_area(further_details[field])
                    break
            
            # If no area found, try to estimate based on bedrooms (rough estimate)
            if total_area == 0 and bedrooms > 0:
                # Very rough estimate: 500 sq ft per bedroom + 200 base
                total_area = (bedrooms * 500) + 200
            
            # Parse price
            price = self.parse_price(property_data.get('price', ''))
            
            # Extract EPC rating
            epc_rating = ""
            epc_data = property_data.get('epc_rating', {})
            if isinstance(epc_data, dict):
                current_rating = epc_data.get('current', '')
                if current_rating and current_rating != "Not available":
                    epc_rating = current_rating
            elif isinstance(epc_data, str):
                epc_rating = epc_data
            
            # Map property condition - default to "New" if not specified
            property_condition = "New"  # API default from the schema
            
            # Extract agent email
            agent_email = property_data.get('agent_email', '')
            if not agent_email or agent_email in ['Not available', 'Error']:
                agent_email = "info@foxtons.co.uk"  # Default fallback
            
            # Extract agent name from email or use default
            agent_name = "Foxtons Agent"
            if '@' in agent_email:
                name_part = agent_email.split('@')[0]
                if name_part.lower() != 'info':
                    agent_name = f"Foxtons {name_part.title()}"
            
            # Create API payload
            api_data = {
                "ListingId": 0,  # 0 for new listings
                "UserId": self.api_config['user_id'],
                "CountryId": self.api_config['country_id'],
                "StateId": self.api_config['state_id'], 
                "CityId": self.api_config['city_id'],
                "StreetAddress": self.extract_address_parts(property_data.get('address', '')),
                "UnitNumber": "",  # Not typically available in Foxtons data
                "PostalCodeId": 0,  # Would need postal code lookup
                "PostalCodeText": "",  # Could extract from address if needed
                "PropertyTypeId": 0,  # Would need property type mapping
                "PropertyCondition": property_condition,
                "Price": price,
                "Bedrooms": bedrooms,
                "Bathrooms": bathrooms,
                "TotalArea": total_area,
                "OutsideSpace": 0.0,  # Not typically specified separately
                "AgentName": agent_name,
                "AgentEmail": agent_email,
                "ListingMedias": [],  # Will be populated with uploaded image IDs
                "ListingMediaToRemove": [],
                "EPCRating": epc_rating,
                "EPCAccepted": True if epc_rating else False,
                "TubeLines": self.extract_tube_lines(property_data.get('nearest_stations', [])),
                "Description": property_data.get('description', '')
            }
            
            return api_data
            
        except Exception as e:
            print(f"❌ Error mapping property data to API format: {str(e)}")
            raise e
    
    def upload_image_to_api(self, image_path):
        """Upload a single image to the API and return the media ID"""
        if not self.api_config['enabled']:
            return None
            
        try:
            if not os.path.exists(image_path):
                print(f"❌ Image file not found: {image_path}")
                return None
            
            upload_url = f"{self.api_config['base_url']}/api/Media/Upload" # Integrated endpoint
            
            # Prepare file for upload
            with open(image_path, 'rb') as img_file:
                files = {
                    'file': (os.path.basename(image_path), img_file, 'image/jpeg')
                }
                
                # Remove Content-Type from headers for file upload
                upload_headers = {k: v for k, v in self.api_headers.items() if k != 'Content-Type'}
                
                print(f"📤 Uploading image: {os.path.basename(image_path)}")
                
                response = requests.post(
                    upload_url,
                    files=files,
                    headers=upload_headers,
                    timeout=self.api_config['timeout']
                )
                
                if response.status_code == 200:
                    result = response.json()
                    media_id = result.get('id') or result.get('mediaId') or result.get('MediaId')
                    if media_id:
                        print(f"✅ Image uploaded successfully, Media ID: {media_id}")
                        return media_id
                    else:
                        print(f"⚠️ Image uploaded but no media ID returned: {result}")
                        return None
                else:
                    print(f"❌ Image upload failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ Error uploading image {image_path}: {str(e)}")
            return None
    
    def upload_property_images(self, property_data):
        """Upload all property images and return list of media IDs"""
        media_ids = []
        
        if not self.api_config['enabled']:
            return media_ids
        
        images = property_data.get('images', [])
        if not images:
            print("📷 No images to upload")
            return media_ids
        
        print(f"📤 Uploading {len(images)} images...")
        
        for i, image_data in enumerate(images, 1):
            try:
                local_path = image_data.get('local_path')
                if local_path and os.path.exists(local_path):
                    print(f"📤 Uploading image {i}/{len(images)}")
                    media_id = self.upload_image_to_api(local_path)
                    if media_id:
                        media_ids.append(media_id)
                    
                    # Be respectful with API calls
                    time.sleep(1)
                else:
                    print(f"⚠️ Image {i} not found: {local_path}")
                    
            except Exception as e:
                print(f"❌ Error processing image {i}: {str(e)}")
        
        print(f"✅ Successfully uploaded {len(media_ids)}/{len(images)} images")
        return media_ids
    
    def post_property_to_api(self, property_data):
        """Post property data to the API using the new API handler or fallback"""
        if self.api_handler and self.api_handler.enabled:
            # Use new API handler
            return self.api_handler.post_property(property_data)
        elif self.api_config.get('enabled', False):
            # Fallback to old method
            if not self.api_config.get('token'):
                return {"status": "disabled", "message": "No API token provided"}
        else:
            return {"status": "disabled", "message": "API posting disabled"}
        
        try:
            property_id = property_data.get('property_id', 'unknown')
            print(f"🚀 Posting property {property_id} to API...")
            
            # Map data to API format
            api_data = self.map_to_api_format(property_data)
            
            # Upload images first
            media_ids = self.upload_property_images(property_data)
            api_data['ListingMedias'] = media_ids
            
            # Post to API with retries
            listing_url = f"{self.api_config['base_url']}{self.api_config['listing_endpoint']}"
            
            for attempt in range(self.api_config['max_retries']):
                try:
                    print(f"📡 Attempting API post (attempt {attempt + 1}/{self.api_config['max_retries']})")
                    
                    response = requests.post(
                        listing_url,
                        json=api_data,
                        headers=self.api_headers,
                        timeout=self.api_config['timeout']
                    )
                    
                    if response.status_code in [200, 201]:
                        result = response.json()
                        listing_id = result.get('id') or result.get('listingId') or result.get('ListingId')
                        
                        print(f"✅ Property {property_id} posted successfully!")
                        if listing_id:
                            print(f"📋 Listing ID: {listing_id}")
                        
                        return {
                            "status": "success",
                            "listing_id": listing_id,
                            "message": "Property posted successfully",
                            "images_uploaded": len(media_ids),
                            "api_response": result
                        }
                    
                    elif response.status_code == 400:
                        print(f"❌ Bad request (400): {response.text}")
                        return {
                            "status": "error",
                            "message": f"Bad request: {response.text}",
                            "api_data": api_data
                        }
                    
                    elif response.status_code == 401:
                        print(f"❌ Unauthorized (401): Check API token")
                        return {
                            "status": "error", 
                            "message": "Unauthorized - check API token"
                        }
                    
                    else:
                        print(f"❌ API error {response.status_code}: {response.text}")
                        if attempt < self.api_config['max_retries'] - 1:
                            print(f"⏳ Retrying in {self.api_config['retry_delay']} seconds...")
                            time.sleep(self.api_config['retry_delay'])
                            continue
                        
                        return {
                            "status": "error",
                            "message": f"API error {response.status_code}: {response.text}"
                        }
                        
                except requests.exceptions.Timeout:
                    print(f"⏰ Request timeout (attempt {attempt + 1})")
                    if attempt < self.api_config['max_retries'] - 1:
                        time.sleep(self.api_config['retry_delay'])
                        continue
                    
                    return {
                        "status": "error",
                        "message": "Request timeout after all retries"
                    }
                
                except requests.exceptions.RequestException as e:
                    print(f"🌐 Network error (attempt {attempt + 1}): {str(e)}")
                    if attempt < self.api_config['max_retries'] - 1:
                        time.sleep(self.api_config['retry_delay'])
                        continue
                    
                    return {
                        "status": "error", 
                        "message": f"Network error: {str(e)}"
                    }
            
            return {
                "status": "error",
                "message": "All retry attempts failed"
            }
            
        except Exception as e:
            print(f"❌ Critical error posting to API: {str(e)}")
            return {
                "status": "error",
                "message": f"Critical error: {str(e)}"
            }

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def safe_find_element(self, xpath):
        """Safely find an element by xpath"""
        try:
            return self.driver.find_element(By.XPATH, xpath)
        except NoSuchElementException:
            return None
    
    def safe_find_elements(self, xpath):
        """Safely find elements by xpath"""
        try:
            return self.driver.find_elements(By.XPATH, xpath)
        except NoSuchElementException:
            return []
    
    def extract_text_safe(self, element):
        """Safely extract text from element"""
        if element:
            return element.text.strip()
        return ""
    
    def parse_rooms_info(self, rooms_elements):
        """Parse rooms information and create a dictionary"""
        rooms_dict = {}
        for element in rooms_elements:
            text = self.extract_text_safe(element)
            if text:
                # Extract number and type (e.g., "2 beds" -> {"beds": 2})
                match = re.match(r'(\d+)\s+(.+)', text)
                if match:
                    number = int(match.group(1))
                    room_type = match.group(2).lower()
                    rooms_dict[room_type] = number
        return rooms_dict
    
    def parse_further_details(self, details_elements):
        """Parse further details section with h6 as keys and p as values"""
        details_dict = {}
        for detail_element in details_elements:
            try:
                h6_element = detail_element.find_element(By.TAG_NAME, "h6")
                p_element = detail_element.find_element(By.TAG_NAME, "p")
                
                key = self.extract_text_safe(h6_element)
                value = self.extract_text_safe(p_element)
                
                if key and value:
                    details_dict[key] = value
            except NoSuchElementException:
                continue
        return details_dict
    
    def parse_nearest_stations(self, station_elements):
        """Parse nearest stations information"""
        stations_data = []
        for station_div in station_elements:
            try:
                # Get h6 elements and join their text
                h6_elements = station_div.find_elements(By.XPATH, ".//h6")
                station_info = " ".join([self.extract_text_safe(h6) for h6 in h6_elements])
                
                # Get map link
                link_element = station_div.find_element(By.XPATH, ".//a")
                map_link = link_element.get_attribute("href") if link_element else ""
                
                # Get station name from p element
                p_element = station_div.find_element(By.XPATH, ".//p")
                station_name = self.extract_text_safe(p_element)
                
                if station_info or map_link or station_name:
                    stations_data.append({
                        "station_info": station_info,
                        "map_link": map_link,
                        "station_name": station_name
                    })
            except NoSuchElementException:
                continue
        return stations_data
    
    def extract_key_features(self, features_element):
        """Extract key features from ul element"""
        features = []
        if features_element:
            li_elements = features_element.find_elements(By.TAG_NAME, "li")
            features = [self.extract_text_safe(li) for li in li_elements if self.extract_text_safe(li)]
        return features
    
    def get_epc_grade(self, rating):
        """Convert numeric EPC rating to letter grade"""
        try:
            rating = int(rating)
            if 92 <= rating <= 100:
                return f"A-{rating}"
            elif 81 <= rating <= 91:
                return f"B-{rating}"
            elif 69 <= rating <= 80:
                return f"C-{rating}"
            elif 55 <= rating <= 68:
                return f"D-{rating}"
            elif 39 <= rating <= 54:
                return f"E-{rating}"
            elif 21 <= rating <= 38:
                return f"F-{rating}"
            elif 1 <= rating <= 20:
                return f"G-{rating}"
            else:
                return f"Unknown-{rating}"
        except (ValueError, TypeError):
            return "Unknown"
    
    def extract_epc_rating(self):
        """Extract EPC rating from certificate image"""
        try:
            # Find the EPC certificate image
            epc_image = self.safe_find_element('//img[@alt="EER-certificate"]')
            
            if not epc_image:
                print("EPC certificate image not found")
                return {"current": "Not available", "potential": "Not available"}
            
            # Get the srcset attribute
            srcset = epc_image.get_attribute("srcset")
            
            if not srcset:
                # Try src attribute as fallback
                src = epc_image.get_attribute("src")
                if src:
                    srcset = src
                else:
                    print("No srcset or src found for EPC image")
                    return {"current": "Not available", "potential": "Not available"}
            
            print(f"EPC srcset found: {srcset}")
            
            # Extract the first URL from srcset (usually the largest resolution)
            # srcset format: "url 640w, url 750w, ..." 
            urls = srcset.split(',')
            target_url = urls[0].strip()
            
            # Remove the width descriptor (e.g., " 640w")
            if ' ' in target_url:
                target_url = target_url.split(' ')[0]
            
            print(f"Processing EPC URL: {target_url}")
            
            # Decode URL if it's encoded
            from urllib.parse import unquote
            decoded_url = unquote(target_url)
            
            print(f"Decoded EPC URL: {decoded_url}")
            
            # Extract the ratings from the URL
            # Looking for pattern like: /075/080.gif where 075 is current, 080 is potential
            import re
            
            # Pattern to match the ratings in the URL (last two numbers before .gif)
            pattern = r'/(\d{3})/(\d{3})\.gif'
            match = re.search(pattern, decoded_url)
            
            if match:
                current_rating = int(match.group(1))
                potential_rating = int(match.group(2))
                
                current_grade = self.get_epc_grade(current_rating)
                potential_grade = self.get_epc_grade(potential_rating)
                
                print(f"EPC Ratings - Current: {current_grade}, Potential: {potential_grade}")
                
                return {
                    "current": current_grade,
                    "potential": potential_grade
                }
            else:
                print("Could not extract ratings from EPC URL pattern")
                return {"current": "Could not parse", "potential": "Could not parse"}
                
        except Exception as e:
            print(f"Error extracting EPC rating: {str(e)}")
            return {"current": "Error", "potential": "Error"}
    
    def extract_agent_email(self):
        """Extract agent email from call element"""
        try:
            # Find the call element
            call_element = self.safe_find_element('//h2[contains(@id,"call-")]')
            
            if not call_element:
                print("Call element not found")
                return "Not available"
            
            # Get the text content
            call_text = self.extract_text_safe(call_element)
            
            if not call_text:
                print("No text found in call element")
                return "Not available"
            
            print(f"Call element text found: {call_text}")
            
            # Split the text and get the last word (agent/branch name)
            # Assuming the text might be like "Call Foxtons Bromley" or similar
            text_parts = call_text.split()
            if text_parts:
                last_word = text_parts[-1]  # Get the last word
                if last_word:
                    # Use the full last word as the name (e.g., "Bromley")
                    agent_name = last_word.lower()  # Convert to lowercase for email format
                    
                    # Construct email
                    agent_email = f"{agent_name}@foxtons.co.uk"
                    
                    print(f"Extracted agent email: {agent_email}")
                    return agent_email
                else:
                    print("Last word is empty")
                    return "Could not parse"
            else:
                print("No words found in call text")
                return "Could not parse"
                
        except Exception as e:
            print(f"Error extracting agent email: {str(e)}")
            return "Error"
    
    def download_image(self, img_url, property_id, img_index):
        """Download image and return local path"""
        try:
            # Create property-specific directory
            property_img_dir = os.path.join(self.images_dir, property_id)
            if not os.path.exists(property_img_dir):
                os.makedirs(property_img_dir)
            
            # Get image extension
            parsed_url = urlparse(img_url)
            img_name = f"image_{img_index:03d}.jpg"
            img_path = os.path.join(property_img_dir, img_name)
            
            # Download image
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(img_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                return os.path.abspath(img_path)
        except Exception as e:
            print(f"Error downloading image {img_url}: {str(e)}")
        return None
    
    def scrape_images(self, property_id):
        """Scrape and download property images"""
        images_data = []
        img_elements = self.safe_find_elements('//ul[@class="alice-carousel__stage"]/li[@class="alice-carousel__stage-item"]/img')
        
        for i, img_element in enumerate(img_elements):
            try:
                img_url = img_element.get_attribute("src")
                if img_url:
                    local_path = self.download_image(img_url, property_id, i + 1)
                    images_data.append({
                        "original_url": img_url,
                        "local_path": local_path
                    })
                    time.sleep(0.5)  # Be respectful with downloads
            except Exception as e:
                print(f"Error processing image {i}: {str(e)}")
        
        return images_data
    
    def expand_accordions(self):
        """Expand all accordion sections to load hidden content"""
        try:
            # First, perform comprehensive page scrolling to load all content
            print("📜 Performing comprehensive page scroll to load all content...")
            
            # Get initial page height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down in chunks to trigger lazy loading
            scroll_pause_time = 1
            current_position = 0
            scroll_increment = 1000  # Scroll 1000 pixels at a time
            
            while current_position < last_height:
                current_position += scroll_increment
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(scroll_pause_time)
                
                # Check if new content loaded
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > last_height:
                    last_height = new_height
                    print(f"📜 Page height increased to {new_height}px, continuing scroll...")
            
            # Final scroll to absolute bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)  # Wait for any final content to load
            
            # Then scroll back to top
            print("📜 Scrolling back to top...")
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)  # Wait for scroll to complete
            
            print("📜 Page scrolling completed, looking for accordion elements...")
            
            max_attempts = 5
            expanded_count = 0
            
            # Try multiple selectors for accordion elements
            accordion_selectors = [
                '//div[contains(@class, "MuiAccordion-root")]',  # Main accordion containers
                '//div[@class="MuiAccordionSummary-expandIconWrapper fxt-1fx8m19"]',  # Original selector
                '//div[contains(@class, "MuiAccordionSummary-root")]',  # Accordion summaries
                '//div[contains(@class, "MuiAccordionSummary-content")]'  # Accordion content areas
            ]
            
            for attempt in range(max_attempts):
                found_accordions = False
                
                # Try different selectors to find accordions
                for selector in accordion_selectors:
                    accordion_elements = self.safe_find_elements(selector)
                    
                    if accordion_elements:
                        print(f"Attempt {attempt + 1}: Found {len(accordion_elements)} elements with selector: {selector}")
                        found_accordions = True
                        break
                
                if not found_accordions:
                    print(f"No accordion elements found with any selector after {expanded_count} expansions")
                    break
                
                expanded_in_this_attempt = False
                
                for i, element in enumerate(accordion_elements):
                    try:
                        # Find the actual accordion container
                        accordion_container = None
                        if "MuiAccordion-root" in element.get_attribute("class"): # type: ignore
                            accordion_container = element
                        else:
                            try:
                                accordion_container = element.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiAccordion-root')]")
                            except:
                                accordion_container = element
                        
                        # Check if already expanded
                        is_expanded = False
                        try:
                            expanded_class = accordion_container.get_attribute("class")
                            if "Mui-expanded" in expanded_class: # type: ignore
                                is_expanded = True
                                print(f"Accordion {i+1} already expanded")
                                continue
                        except:
                            pass
                        
                        # Scroll into view
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", accordion_container)
                        time.sleep(1.5)
                        
                        # Try different click strategies
                        click_success = False
                        
                        # Strategy 1: Click the accordion summary area
                        try:
                            summary = accordion_container.find_element(By.XPATH, ".//div[contains(@class, 'MuiAccordionSummary-root')]")
                            if summary.is_displayed():
                                self.driver.execute_script("arguments[0].click();", summary)
                                time.sleep(2)
                                click_success = True
                                print(f"✅ Expanded accordion {i+1} via summary")
                        except Exception as e1:
                            print(f"Summary click failed for accordion {i+1}: {str(e1)}")
                        
                        # Strategy 2: Click the expand icon if summary failed
                        if not click_success:
                            try:
                                expand_icon = accordion_container.find_element(By.XPATH, ".//div[contains(@class, 'MuiAccordionSummary-expandIconWrapper')]")
                                if expand_icon.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", expand_icon)
                                    time.sleep(2)
                                    click_success = True
                                    print(f"✅ Expanded accordion {i+1} via expand icon")
                            except Exception as e2:
                                print(f"Expand icon click failed for accordion {i+1}: {str(e2)}")
                        
                        # Strategy 3: Click anywhere on the accordion container
                        if not click_success:
                            try:
                                self.driver.execute_script("arguments[0].click();", accordion_container)
                                time.sleep(2)
                                click_success = True
                                print(f"✅ Expanded accordion {i+1} via container")
                            except Exception as e3:
                                print(f"Container click failed for accordion {i+1}: {str(e3)}")
                        
                        if click_success:
                            expanded_count += 1
                            expanded_in_this_attempt = True
                            
                            # Verify expansion worked
                            try:
                                updated_class = accordion_container.get_attribute("class")
                                if "Mui-expanded" in updated_class: # type: ignore
                                    print(f"✅ Accordion {i+1} successfully expanded (verified)")
                                else:
                                    print(f"⚠️ Accordion {i+1} clicked but may not be expanded")
                            except:
                                pass
                            
                            break  # Exit inner loop and re-find elements
                        else:
                            print(f"❌ Failed to expand accordion {i+1} with all strategies")
                            
                    except Exception as e:
                        print(f"Error processing accordion {i+1}: {str(e)}")
                        continue
                
                if not expanded_in_this_attempt:
                    print("No more accordions to expand")
                    break
                
                time.sleep(1)
            
            print(f"Accordion expansion completed. Total expanded: {expanded_count}")
            time.sleep(3)
            self.verify_accordions_expanded()
            
        except Exception as e:
            print(f"Error expanding accordions: {str(e)}")
    
    def verify_accordions_expanded(self):
        """Verify that accordion content is now visible"""
        try:
            # Check for further details content
            details_elements = self.safe_find_elements('//div[@class="MuiBox-root fxt-4zmbs6"]//div[@class="MuiBox-root fxt-0"]')
            print(f"Found {len(details_elements)} further details sections after expansion")
            
            # Check for nearest stations content
            station_elements = self.safe_find_elements('//div[@class="MuiBox-root fxt-1ofqig9"]')
            print(f"Found {len(station_elements)} nearest stations sections after expansion")
            
            if len(details_elements) > 0 or len(station_elements) > 0:
                print("✅ Accordion content successfully loaded")
            else:
                print("⚠️ Warning: Expected accordion content not found - accordions may not have expanded properly")
                
        except Exception as e:
            print(f"Error verifying accordion expansion: {str(e)}")

    def scrape_property_details(self, url):
        """Scrape all property details from a single property page"""
        print(f"Scraping: {url}")
        
        # Initialize with basic data structure
        property_id = url.split('/')[-1] if '/' in url else "unknown"
        property_data = {
            "url": url,
            "scraped_at": datetime.now().isoformat(),
            "property_id": property_id,
            "scraping_status": "in_progress"
        }
        
        try:
            # Load the page with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.driver.get(url)
                    time.sleep(3)  # Wait for page to load
                    break
                except Exception as e:
                    print(f"Error loading page, attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(2)
            
            # Expand all accordion sections first
            self.expand_accordions()
            
            # Extract all the required information with individual try-catch blocks
            
            # Extract each field with individual error handling
            
            # Address
            try:
                address_element = self.safe_find_element('//h1[@class="MuiTypography-root MuiTypography-h2 fxt-ho8cj"]')
                property_data["address"] = self.extract_text_safe(address_element)
            except Exception as e:
                print(f"Error extracting address: {str(e)}")
                property_data["address"] = ""
            
            # Description
            try:
                description_element = self.safe_find_element('//p[@class="MuiTypography-root MuiTypography-body1 detailsText fxt-xypftu"]')
                property_data["description"] = self.extract_text_safe(description_element)
            except Exception as e:
                print(f"Error extracting description: {str(e)}")
                property_data["description"] = ""
            
            # Property Type
            try:
                property_type_element = self.safe_find_element('//p[@class="MuiTypography-root MuiTypography-body1 iconText fxt-1axgsrg"]')
                property_data["property_type"] = self.extract_text_safe(property_type_element)
            except Exception as e:
                print(f"Error extracting property type: {str(e)}")
                property_data["property_type"] = ""
            
            # Rooms Count and Type
            try:
                rooms_elements = self.safe_find_elements('//p[@class="MuiTypography-root MuiTypography-body1 iconText fxt-qktkd3"]')
                property_data["rooms"] = self.parse_rooms_info(rooms_elements)
            except Exception as e:
                print(f"Error extracting rooms info: {str(e)}")
                property_data["rooms"] = {}
            
            # Price
            try:
                price_element = self.safe_find_element('//h3[@class="MuiTypography-root MuiTypography-h3 weeklyRent fxt-ghi95u"]')
                property_data["price"] = self.extract_text_safe(price_element)
            except Exception as e:
                print(f"Error extracting price: {str(e)}")
                property_data["price"] = ""
            
            # Key Features
            try:
                features_element = self.safe_find_element('//div[@class="MuiBox-root fxt-l62wo3"]/ul')
                property_data["key_features"] = self.extract_key_features(features_element)
            except Exception as e:
                print(f"Error extracting key features: {str(e)}")
                property_data["key_features"] = []
            
            # Further Details
            try:
                details_elements = self.safe_find_elements('//div[@class="MuiBox-root fxt-4zmbs6"]//div[@class="MuiBox-root fxt-0"]')
                property_data["further_details"] = self.parse_further_details(details_elements)
            except Exception as e:
                print(f"Error extracting further details: {str(e)}")
                property_data["further_details"] = {}
            
            # Nearest Stations
            try:
                station_elements = self.safe_find_elements('//div[@class="MuiBox-root fxt-1ofqig9"]')
                property_data["nearest_stations"] = self.parse_nearest_stations(station_elements)
            except Exception as e:
                print(f"Error extracting nearest stations: {str(e)}")
                property_data["nearest_stations"] = []
            
            # Local Life
            try:
                local_life_element = self.safe_find_element('//p[@class="MuiTypography-root MuiTypography-body1 fxt-15piecj"]')
                property_data["local_life"] = self.extract_text_safe(local_life_element)
            except Exception as e:
                print(f"Error extracting local life: {str(e)}")
                property_data["local_life"] = ""
            
            # EPC Rating
            try:
                print(f"Extracting EPC rating for property {property_id}...")
                property_data["epc_rating"] = self.extract_epc_rating()
            except Exception as e:
                print(f"Error extracting EPC rating: {str(e)}")
                property_data["epc_rating"] = {"current": "Error", "potential": "Error"}
            
            # Agent Email
            try:
                print(f"Extracting agent email for property {property_id}...")
                property_data["agent_email"] = self.extract_agent_email()
            except Exception as e:
                print(f"Error extracting agent email: {str(e)}")
                property_data["agent_email"] = "Error"
            
            # Images
            try:
                print(f"Downloading images for property {property_id}...")
                property_data["images"] = self.scrape_images(property_id)
            except Exception as e:
                print(f"Error downloading images: {str(e)}")
                property_data["images"] = []
            
            property_data["scraping_status"] = "completed"
            print(f"Successfully scraped property {property_id}")
            
            # Post to API if enabled
            try:
                api_result = self.post_property_to_api(property_data)
                property_data["api_posting"] = api_result
                
                if api_result.get('status') == 'success':
                    property_data["api_listing_id"] = api_result.get('listing_id')
                    print(f"✅ Property {property_id} successfully posted to API")
                else:
                    print(f"⚠️ API posting result: {api_result.get('message', 'Unknown error')}")
                    
            except Exception as api_error:
                print(f"❌ API posting error for property {property_id}: {str(api_error)}")
                property_data["api_posting"] = {
                    "status": "error",
                    "message": str(api_error)
                }
            
            return property_data
            
        except Exception as e:
            print(f"Critical error scraping {url}: {str(e)}")
            property_data["scraping_status"] = "failed"
            property_data["error"] = str(e)
            property_data["error_type"] = type(e).__name__
            
            # Ensure all required fields exist with default values
            default_fields = {
                "address": "",
                "description": "",
                "property_type": "",
                "rooms": {},
                "price": "",
                "key_features": [],
                "further_details": {},
                "nearest_stations": [],
                "local_life": "",
                "epc_rating": {"current": "Not available", "potential": "Not available"},
                "agent_email": "Not available",
                "images": [],
                "api_posting": {"status": "skipped", "message": "Scraping failed"},
                "api_listing_id": None
            }
            
            for field, default_value in default_fields.items():
                if field not in property_data:
                    property_data[field] = default_value
            
            return property_data
    
    def load_existing_data(self):
        """Load existing scraped data using the data manager or fallback"""
        if self.data_manager:
            # Use new data manager
            if self.data_manager.load_data():
                print(f"📄 Loaded {len(self.data_manager.data)} existing records via Data Manager")
            else:
                print("⚠️ Failed to load data via Data Manager")
        else:
            # Fallback to old method
            if os.path.exists(self.output_file):
                try:
                    with open(self.output_file, 'r', encoding='utf-8') as f:
                        self.scraped_data = json.load(f)
                    print(f"📄 Loaded {len(self.scraped_data)} existing records from {self.output_file}")
                except (json.JSONDecodeError, IOError) as e:
                    print(f"⚠️ Could not load existing file {self.output_file}: {str(e)}")
                    print("🔄 Starting with empty dataset")
                    self.scraped_data = []
            else:
                print(f"📝 No existing file found. Starting fresh.")
                self.scraped_data = []
    
    def get_scraped_urls(self):
        """Get set of already scraped URLs to avoid duplicates"""
        if self.data_manager:
            return self.data_manager.get_scraped_urls()
        else:
            # Fallback to old method
            scraped_urls = set()
            for item in self.scraped_data:
                if 'url' in item and item['url']:
                    scraped_urls.add(item['url'])
            return scraped_urls
    
    def read_csv_urls(self):
        """Read URLs from CSV file, excluding already scraped ones"""
        urls = []
        scraped_urls = self.get_scraped_urls()
        skipped_count = 0
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if 'URL' in row and row['URL']:
                        url = row['URL']
                        if url not in scraped_urls:
                            urls.append(url)
                        else:
                            skipped_count += 1
        except Exception as e:
            print(f"Error reading CSV file: {str(e)}")
        
        print(f"📊 Found {len(urls)} new URLs to scrape (skipped {skipped_count} already scraped)")
        return urls
    
    def save_data(self):
        """Save scraped data using the data manager or fallback"""
        if self.data_manager:
            # Use new data manager
            if self.data_manager.save_data():
                print(f"✅ Successfully saved {len(self.data_manager.data)} records via Data Manager")
            else:
                print("❌ Failed to save data via Data Manager")
        else:
            # Fallback to old method
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # First, validate that our data can be serialized
                    json_str = json.dumps(self.scraped_data, indent=2, ensure_ascii=False, default=str)
                    
                    # Create backup filename
                    backup_file = f"{self.output_file}.backup"
                    
                    # Write to backup first
                    with open(backup_file, 'w', encoding='utf-8') as f:
                        f.write(json_str)
                    
                    # If backup successful, rename to main file
                    import shutil
                    shutil.move(backup_file, self.output_file)
                    
                    # Success - break out of retry loop
                    break
                    
                except (json.JSONEncodeError, TypeError) as e: # type: ignore
                    print(f"JSON serialization error on attempt {attempt + 1}: {str(e)}")
                    # Clean problematic data
                    self.clean_data_for_json()
                    if attempt == max_retries - 1:
                        print("Failed to save JSON after cleaning data")
                        
                except (IOError, OSError) as e:
                    print(f"File I/O error on attempt {attempt + 1}: {str(e)}")
                    time.sleep(1)  # Wait before retry
                    if attempt == max_retries - 1:
                        print("Failed to save data after multiple attempts")
                        
                except Exception as e:
                    print(f"Unexpected error saving data on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        print("Failed to save data due to unexpected error")

    def clean_data_for_json(self):
        """Clean data to ensure JSON serialization compatibility"""
        try:
            for i, item in enumerate(self.scraped_data):
                if isinstance(item, dict):
                    # Convert any non-serializable objects to strings
                    for key, value in item.items():
                        if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                            item[key] = str(value)
                        elif isinstance(value, list):
                            # Clean list items
                            item[key] = [str(v) if not isinstance(v, (str, int, float, bool, dict, type(None))) else v for v in value]
                        elif isinstance(value, dict):
                            # Recursively clean dictionary values
                            for k, v in value.items():
                                if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                                    value[k] = str(v)
        except Exception as e:
            print(f"Error cleaning data: {str(e)}")
    
    def scrape_all_properties(self, limit=None):
        """Scrape all properties from the CSV file"""
        # Load existing data first
        self.load_existing_data()
        
        # Get existing count from data manager or fallback
        existing_count = len(self.data_manager.data) if self.data_manager else len(self.scraped_data)
        urls = self.read_csv_urls()
        
        if limit:
            urls = urls[:limit]
        
        if len(urls) == 0:
            print("🎉 All properties already scraped! No new URLs to process.")
            return
        
        print(f"🚀 Starting to scrape {len(urls)} new URLs (existing: {existing_count} properties)")
        
        for i, url in enumerate(urls, 1):
            current_total = existing_count + i
            print(f"\n📍 Progress: {i}/{len(urls)} (Total: {current_total})")
            
            try:
                property_data = self.scrape_property_details(url)
                
                # Add to data manager or fallback
                if self.data_manager:
                    self.data_manager.add_record(property_data)
                else:
                    self.scraped_data.append(property_data)
                
                # Save data after each property
                self.save_data()
                
                # Get total count for display
                total_count = len(self.data_manager.data) if self.data_manager else len(self.scraped_data)
                print(f"💾 Data saved after property {i} (Total: {total_count})")
                
            except Exception as e:
                print(f"❌ Fatal error processing property {i} ({url}): {str(e)}")
                # Add a failed entry to maintain data structure
                failed_entry = {
                    "url": url,
                    "scraped_at": datetime.now().isoformat(),
                    "property_id": url.split('/')[-1] if '/' in url else "unknown",
                    "scraping_status": "fatal_error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "address": "",
                    "description": "",
                    "property_type": "",
                    "rooms": {},
                    "price": "",
                    "key_features": [],
                    "further_details": {},
                    "nearest_stations": [],
                    "local_life": "",
                    "epc_rating": {"current": "Not available", "potential": "Not available"},
                    "agent_email": "Not available",
                    "images": [],
                    "api_posting": {"status": "skipped", "message": "Fatal scraping error"},
                    "api_listing_id": None
                }
                # Add failed entry to data manager or fallback
                if self.data_manager:
                    self.data_manager.add_record(failed_entry)
                else:
                    self.scraped_data.append(failed_entry)
                
                # Still try to save data
                try:
                    self.save_data()
                    total_count = len(self.data_manager.data) if self.data_manager else len(self.scraped_data)
                    print(f"💾 Data saved after failed property {i} (Total: {total_count})")
                except Exception as save_error:
                    print(f"Failed to save data after error: {str(save_error)}")
            
            # Be respectful with requests
            time.sleep(2)
        
        # Final save
        self.save_data()
        
        # Calculate API statistics
        api_stats = self.calculate_api_statistics()
        
        # Get final count
        final_count = len(self.data_manager.data) if self.data_manager else len(self.scraped_data)
        print(f"\n🎉 Completed scraping! Total properties in database: {final_count}")
        print(f"📈 Added {len(urls)} new properties to existing {existing_count} records")
        
        print(f"\n📊 API Integration Summary:")
        print(f"  ✅ Successfully posted: {api_stats['success']} properties")
        print(f"  ❌ Failed to post: {api_stats['failed']} properties")
        print(f"  ⏭️ Skipped: {api_stats['skipped']} properties")
        print(f"  🖼️ Total images uploaded: {api_stats['images_uploaded']}")
        if api_stats['success'] > 0:
            print(f"  📋 Sample Listing IDs: {', '.join(map(str, api_stats['sample_listing_ids'][:5]))}")
    
    def calculate_api_statistics(self):
        """Calculate API posting statistics"""
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'images_uploaded': 0,
            'sample_listing_ids': []
        }
        
        # Get data from data manager or fallback
        data_to_check = self.data_manager.data if self.data_manager else self.scraped_data
        
        for property_data in data_to_check:
            api_posting = property_data.get('api_posting', {})
            api_status = api_posting.get('status', 'unknown')
            
            if api_status == 'success':
                stats['success'] += 1
                listing_id = property_data.get('api_listing_id')
                if listing_id and listing_id not in stats['sample_listing_ids']:
                    stats['sample_listing_ids'].append(listing_id)
                
                # Count images uploaded for this property
                images_count = api_posting.get('images_uploaded', 0)
                stats['images_uploaded'] += images_count
                
            elif api_status == 'error':
                stats['failed'] += 1
            else:
                stats['skipped'] += 1
        
        return stats

def main():
    # Configuration
    CSV_FILE = "foxtons_secondary_urls_collection.csv"  # Path to your CSV file
    IMAGES_DIR = "property_images"      # Directory to save images
    OUTPUT_FILE = "property_details.json"  # Output JSON file
    
    # Load API Configuration from separate file
    try:
        from api_config import get_api_config
        API_CONFIG = get_api_config()
    except ImportError:
        print("⚠️ api_config.py not found, using default configuration")
        # Fallback configuration
        API_CONFIG = {
            "base_url": "https://api.laddr.com",
            "listing_endpoint": "/api/Listing/Upsert",
            "media_upload_endpoint": "/api/Media/Upload",
            "token": "",  # You need to add your token here
            "user_id": "waqar@lexumsoft.com",
            "country_id": 1,
            "state_id": 1,
            "city_id": 1,
            "enabled": False,  # Disabled by default without config file
            "timeout": 60,
            "max_retries": 3,
            "retry_delay": 5
        }
    
    # Ensure we're in the right directory
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check if CSV file exists
    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file '{CSV_FILE}' not found in directory: {os.getcwd()}")
        print("Available files:")
        for file in os.listdir('.'):
            if file.endswith('.csv'):
                print(f"  - {file}")
        return
    
    # Display configuration
    print("🔧 Configuration:")
    print(f"  📁 CSV File: {CSV_FILE}")
    print(f"  🖼️ Images Directory: {IMAGES_DIR}")
    print(f"  📄 Output File: {OUTPUT_FILE}")
    print(f"  🌐 API Integration: {'Enabled' if API_CONFIG['enabled'] else 'Disabled'}")
    if API_CONFIG['enabled']:
        print(f"  🔗 API Base URL: {API_CONFIG['base_url']}")
        print(f"  👤 User ID: {API_CONFIG['user_id']}")
    
    # Initialize scraper
    scraper = PropertyDetailsScraper(
        csv_file_path=CSV_FILE,
        images_dir=IMAGES_DIR,
        output_file=OUTPUT_FILE,
        api_config=API_CONFIG
    )
    
    try:
        # Start scraping (you can add limit=5 for testing)
        # scraper.scrape_all_properties(limit=5)  # Test with 5 properties
        scraper.scrape_all_properties()  # Scrape all properties
    
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
        scraper.save_data()
    
    except Exception as e:
        print(f"Error: {str(e)}")
        scraper.save_data()
    
    finally:
        # Cleanup
        if hasattr(scraper, 'driver'):
            scraper.driver.quit()

if __name__ == "__main__":
    main() 