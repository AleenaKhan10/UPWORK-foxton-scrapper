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
import db_api_call
import pymssql
from db_config import DB_CONFIG

class PropertyDetailsScraper:
    def __init__(self, csv_file_path, images_dir="property_images", output_file="property_details.json"):
        self.csv_file_path = csv_file_path
        self.images_dir = images_dir
        self.output_file = output_file
        self.scraped_data = []
        self.db_listings = []
        
        
        # Load existing data if file exists
        self.load_existing_data()
        
        # Create images directory if it doesn't exist
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        
        # Setup Chrome options for stability
        self.chrome_options = Options()
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        # self.chrome_options.add_argument("--headless")  # Uncomment to run headless
        
        self.driver = None
        self.wait = None
        self.initialize_driver()


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
    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass

    def initialize_driver(self):
        """Initialize Chrome driver"""
        try:
            if self.driver:
                self.close_driver()
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            print("✅ Browser initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing browser: {e}")
            raise e

    def close_driver(self):
        """Safely close the Chrome driver"""
        try:
            if self.driver:
                self.driver.quit()
                print("🔄 Browser closed")
        except Exception as e:
            print(f"⚠️ Error closing browser: {e}")
        finally:
            self.driver = None
            self.wait = None

    def connect_to_database(self):
        """Establish connection to Azure SQL Database"""
        try:
            print(f"Connecting to {DB_CONFIG['server']}...")
            connection = pymssql.connect(
                server=DB_CONFIG['server'],
                database=DB_CONFIG['database'],
                user=DB_CONFIG['username'],
                password=DB_CONFIG['password'],
                port=DB_CONFIG['port']
            )
            print("✓ Successfully connected to Azure SQL Database")
            return connection
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
            return None

    def load_db_listings(self):
        """Load all listings from database"""
        print("📥 Loading listings from database...")
        connection = self.connect_to_database()
        if not connection:
            print("❌ Failed to connect to database")
            return False
        
        try:
            cursor = connection.cursor()
            # Get essential fields for comparison
            query = """
            SELECT ListingId, Description, StreetAddress, CreatedDate
            FROM [dbo].[Listings] 
            ORDER BY CreatedDate DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            self.db_listings = []
            for row in rows:
                listing = {
                    'listing_id': row[0],
                    'description': row[1] or '',
                    'address': row[2] or '',
                    'created_date': row[3]
                }
                self.db_listings.append(listing)
            
            cursor.close()
            connection.close()
            print(f"✅ Loaded {len(self.db_listings)} listings from database")
            return True
            
        except Exception as e:
            print(f"❌ Error loading DB listings: {e}")
            if connection:
                connection.close()
            return False

    def find_listing_by_description(self, description):
        """Find DB listing by matching description"""
        if not description or not description.strip():
            return None
        
        description_clean = description.strip().lower()
        
        # Try exact match
        for db_listing in self.db_listings:
            if db_listing['description'].strip().lower() == description_clean:
                return db_listing
        
        return None

    def find_json_listing_by_url(self, url):
        """Find JSON listing by URL"""
        for json_listing in self.scraped_data:
            if json_listing.get('url') == url:
                return json_listing
        return None
    
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
                tube_lines = db_api_call.get_all_tube_lines()
                all_lines= tube_lines[1].get("data")
                # Find the tube line id whose name matches the station name (case-insensitive, strip whitespace)
                matching_tube_line_id = None
                if station_name and all_lines:
                    for tube_line in all_lines:
                        tube_line_name = tube_line.get("tubeLineName") or tube_line.get("name")
                        if tube_line_name and tube_line_name.strip().lower() == station_name.strip().lower():
                            matching_tube_line_id = tube_line.get("tubeLineId") or tube_line.get("id")
                            break
                
                if station_info or map_link or station_name:
                    stations_data.append({
                        "station_info": station_info,
                        "map_link": map_link,
                        "station_name": station_name,
                        "tube_line_id": matching_tube_line_id
                    })
            except NoSuchElementException:
                continue
        try:
            station_id = ''
            for station in stations_data:
                if station.get("tube_line_id"):
                    station_id += ','+ str(station.get("tube_line_id"))
            station_id = station_id[1:]
            print(f"Station ID: {station_id}")
        except Exception as e:
            print(f"Error extracting station ID: {str(e)}")
            station_id = ''
        return stations_data, station_id
    
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
        floor_plan_button = self.safe_find_element('//button[.//text()="Floorplan"]')
        if floor_plan_button:
            self.driver.execute_script("arguments[0].click();", floor_plan_button)
            time.sleep(5)
            floor_plan_element = self.safe_find_element('//img[@alt="floor-plan"]')
            img_elements.append(floor_plan_element)
            time.sleep(1)
        
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
                    # Check if driver is still responsive
                    if not self.driver:
                        print(f"⚠️ Driver not initialized, reinitializing...")
                        self.initialize_driver()
                    
                    self.driver.get(url)
                    time.sleep(3)  # Wait for page to load
                    break
                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ Error loading page, attempt {attempt + 1}/{max_retries}: {error_msg}")
                    
                    # Check for specific timeout errors that require browser restart
                    if ("HTTPConnectionPool" in error_msg and "Read timed out" in error_msg) or \
                       ("WebDriverException" in error_msg) or \
                       ("InvalidSessionIdException" in error_msg) or \
                       ("SessionNotCreatedException" in error_msg):
                        
                        print(f"🔄 Browser timeout/error detected, restarting browser (attempt {attempt + 1}/{max_retries})")
                        self.close_driver()
                        time.sleep(2)  # Wait before reinitializing
                        
                        if attempt < max_retries - 1:  # Don't reinitialize on last attempt
                            try:
                                self.initialize_driver()
                            except Exception as init_error:
                                print(f"❌ Failed to reinitialize browser: {init_error}")
                                if attempt == max_retries - 1:
                                    raise e
                                continue
                        else:
                            raise e
                    else:
                        # For other errors, just wait and retry
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
                local_authority = property_data["further_details"].get("Local Authority")
                if 'The City of' in local_authority:
                    local_authority = local_authority.split(' ')[3].strip()
                elif '(' in local_authority:
                    local_authority = local_authority.split('(')[0].strip()

                
                print(f"Local authority: {local_authority}")
                stateids = db_api_call.get_states_by_country_id()
                state_ids = stateids[1].get("data")
                for state in state_ids:
                    if state.get("stateName") == local_authority:
                        property_data["state_id"] = state.get("stateId")
                        break
                if not property_data.get("state_id"):
                    print(f"State ID not found for {local_authority}")
                    property_data["state_id"] = 0
            except Exception as e:
                print(f"Error extracting further details: {str(e)}")
                property_data["further_details"] = {}
            
            # Nearest Stations
            try:
                station_elements = self.safe_find_elements('//div[@class="MuiBox-root fxt-1ofqig9"]')
                stations_data, station_id = self.parse_nearest_stations(station_elements)
                property_data["nearest_stations"] = stations_data
                property_data["station_id"] = station_id
                
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

            return property_data 
            
        except Exception as e:
            print(f"Error scraping property {property_id}: {str(e)}")
            return None
    
    def load_existing_data(self):
        """Load existing scraped data if the output file exists"""
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
        scraped_urls = set()
        for item in self.scraped_data:
            if 'url' in item and item['url']:
                scraped_urls.add(item['url'])
        return scraped_urls
    
    def read_csv_urls(self):
        """Read URLs from CSV file, checking both JSON and DB for existing data"""
        urls_to_scrape = []
        skipped_count = 0
        already_in_db_count = 0
        new_urls_count = 0
        json_not_in_db_count = 0
        
        # Load database listings for comparison
        print("🔄 Checking database for existing listings...")
        if not self.load_db_listings():
            print("⚠️ Could not load DB listings, falling back to JSON-only check")
            # Fallback to original behavior if DB connection fails
            return self.read_csv_urls_fallback()
        
        try:
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if 'URL' in row and row['URL']:
                        url = row['URL']
                        
                        # Check if URL exists in JSON file
                        json_listing = self.find_json_listing_by_url(url)
                        
                        if json_listing:
                            # URL exists in JSON, check if it's in DB
                            json_description = json_listing.get('description', '')
                            if json_description:
                                db_listing = self.find_listing_by_description(json_description)
                                if db_listing:
                                    # Already in DB, skip
                                    print(f"✅ Skipping {url} - already in DB (ID: {db_listing['listing_id']})")
                                    already_in_db_count += 1
                                    skipped_count += 1
                                else:
                                    # In JSON but not in DB, need to scrape again
                                    print(f"🔄 Adding {url} - in JSON but not in DB, will re-scrape")
                                    urls_to_scrape.append(url)
                                    json_not_in_db_count += 1
                            else:
                                # JSON listing has no description, need to scrape again
                                print(f"🔄 Adding {url} - JSON listing has no description, will re-scrape")
                                urls_to_scrape.append(url)
                                json_not_in_db_count += 1
                        else:
                            # URL not in JSON, definitely need to scrape
                            urls_to_scrape.append(url)
                            new_urls_count += 1
                            
        except Exception as e:
            print(f"❌ Error reading CSV file: {str(e)}")
            return []
        
        print(f"\n📊 URL Processing Summary:")
        print(f"   ✅ Already in DB (skipped): {already_in_db_count}")
        print(f"   🔄 In JSON but not DB (will re-scrape): {json_not_in_db_count}")
        print(f"   🆕 New URLs (not in JSON): {new_urls_count}")
        print(f"   📋 Total URLs to scrape: {len(urls_to_scrape)}")
        print(f"   ⏭️ Total skipped: {skipped_count}")
        
        return urls_to_scrape

    def read_csv_urls_fallback(self):
        """Fallback method if DB connection fails - original behavior"""
        print("⚠️ Using fallback method (JSON-only check)")
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
        """Save scraped data to JSON file with enhanced error handling"""
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
        existing_count = len(self.scraped_data)
        urls = self.read_csv_urls()
        
        if limit:
            urls = urls[:limit]
        
        if len(urls) == 0:
            print("🎉 All properties already processed! No URLs need scraping.")
            print("   All URLs are either already in database or failed to load from CSV.")
            return
        
        print(f"🚀 Starting to scrape {len(urls)} URLs (includes new URLs and JSON entries not in DB)")
        print(f"   JSON file currently has: {existing_count} properties")
        
        for i, url in enumerate(urls, 1):
            current_total = existing_count + i
            print(f"\n📍 Progress: {i}/{len(urls)} (Total: {current_total})")
            
            try:
                property_data = self.scrape_property_details(url)
                if property_data is None:
                    print(f"Property data is None for {url}")
                    continue
                self.scraped_data.append(property_data)
                
                # Save data after each property
                self.save_data()

                # Upsert listing to API
                try:
                    result = db_api_call.upsert_listing(property_data)
                    if result is not None:
                        status_code, response = result
                        if status_code == 200:
                            print(f"Listing {property_data.get('api_listing_id')} upserted successfully")
                        elif status_code == 401:
                            print(f"Listing {property_data.get('api_listing_id')} upsert failed with status {status_code}: {response}")
                            print("Refreshing token")
                            db_api_call.refresh_token()
                            result = db_api_call.upsert_listing(property_data)
                            if result is not None:
                                status_code, response = result
                                if status_code == 200:
                                    print(f"Listing {property_data.get('api_listing_id')} upserted successfully")
                                else:
                                    print(f"Listing {property_data.get('api_listing_id')} upsert failed with status {status_code}: {response}")
                            else:
                                print(f"Listing {property_data.get('api_listing_id')} upsert failed: API returned None") 
                    else:
                        print(f"Listing {property_data.get('api_listing_id')} upsert failed: API returned None")
                except Exception as e:
                    print(f"Error upserting listing: {str(e)}")

                print(f"💾 Data saved after property {i} (Total: {len(self.scraped_data)})")
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Fatal error processing property {i} ({url}): {error_msg}")
                
                # Check if this is a browser timeout/error that requires restart
                if ("HTTPConnectionPool" in error_msg and "Read timed out" in error_msg) or \
                   ("WebDriverException" in error_msg) or \
                   ("InvalidSessionIdException" in error_msg) or \
                   ("SessionNotCreatedException" in error_msg):
                    
                    print(f"🔄 Browser error detected, restarting browser for next property...")
                    self.close_driver()
                    time.sleep(3)  # Wait before reinitializing
                    
                    try:
                        self.initialize_driver()
                        print(f"✅ Browser restarted successfully")
                    except Exception as init_error:
                        print(f"❌ Failed to restart browser: {init_error}")
                
                # Add a failed entry to maintain data structure
                failed_entry = {
                    "url": url,
                    "scraped_at": datetime.now().isoformat(),
                    "property_id": url.split('/')[-1] if '/' in url else "unknown",
                    "scraping_status": "fatal_error",
                    "error": error_msg,
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
                self.scraped_data.append(failed_entry)
                
                # Still try to save data
                try:
                    self.save_data()
                    print(f"💾 Data saved after failed property {i} (Total: {len(self.scraped_data)})")
                except Exception as save_error:
                    print(f"Failed to save data after error: {str(save_error)}")
            
            # Be respectful with requests
            time.sleep(2)
        
        # Final save
        self.save_data()
    
    def calculate_api_statistics(self):
        """Calculate API posting statistics"""
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'images_uploaded': 0,
            'sample_listing_ids': []
        }
        
        for property_data in self.scraped_data:
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

    
    # Initialize scraper
    scraper = PropertyDetailsScraper(
        csv_file_path=CSV_FILE,
        images_dir=IMAGES_DIR,
        output_file=OUTPUT_FILE
    )
    
    try:
        scraper.scrape_all_properties() 
    
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