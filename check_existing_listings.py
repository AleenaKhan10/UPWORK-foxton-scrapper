#!/usr/bin/env python3
"""
Check Existing Listings Module
Runs between secondary_urls_collection.py and listing_details.py
Checks existing listings in DB and JSON files, scrapes current data, and updates if changed.
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

class ExistingListingsChecker:
    def __init__(self, csv_file_path="foxtons_secondary_urls_collection.csv", json_file_path="property_details.json"):
        self.csv_file_path = csv_file_path
        self.json_file_path = json_file_path
        self.db_listings = []
        self.json_listings = []
        self.csv_urls = []
        self.updated_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
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

    def __del__(self):
        """Cleanup driver on object destruction"""
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
            self.cookies_handled = False
            print("✅ Browser initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing browser: {e}")
            raise e


    def handle_cookies_popup(self):
        """Handle cookies popup if it appears"""
        # Only check for cookies if we haven't handled them in this browser session
        if self.cookies_handled:
            return
            
        try:
            print("🍪 Checking for cookies popup...")
            
            # Wait up to 60 seconds for cookies popup to appear
            cookie_popup = WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Accept All') or contains(text(), 'Accept') or contains(text(), 'Allow All') or contains(text(), 'I Accept') or contains(text(), 'OK') or contains(text(), 'Got it')]"))
            )
            
            print("🍪 Cookies popup found, clicking 'Accept All'...")
            cookie_popup.click()
            print("✅ Cookies accepted successfully")
            
            # Mark cookies as handled for this browser session
            self.cookies_handled = True
            
            # Wait a moment for the popup to disappear
            time.sleep(2)
            
        except TimeoutException:
            print("ℹ️ No cookies popup found or already handled")
            # Mark as handled even if no popup found to avoid checking again
            self.cookies_handled = True
        except Exception as e:
            print(f"⚠️ Error handling cookies popup: {e}")
            # Continue anyway, don't let cookie issues stop the scraping


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
            print("🔍 Executing query to fetch listings...")
            
            # Get essential fields for comparison
            query = """
            SELECT ListingId, Description, Price, StreetAddress, PropertyTypeId, 
                   PostalCodeId, CreatedDate
            FROM [dbo].[Listings] 
            ORDER BY CreatedDate DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            print(f"📊 Database returned {len(rows)} listings")
            
            self.db_listings = []
            valid_descriptions = 0
            empty_descriptions = 0
            
            for i, row in enumerate(rows):
                listing = {
                    'listing_id': row[0],
                    'description': row[1] or '',
                    'price': row[2] or '',
                    'address': row[3] or '',
                    'property_type_id': row[4],
                    'postal_code_id': row[5],
                    'created_date': row[6],
                }
                self.db_listings.append(listing)
                
                # Count description statistics
                if listing['description'].strip():
                    valid_descriptions += 1
                else:
                    empty_descriptions += 1
                
                # Show progress for large datasets
                if len(rows) > 100 and (i + 1) % 50 == 0:
                    print(f"   📊 Processing... {i + 1}/{len(rows)} listings loaded")
            
            cursor.close()
            connection.close()
            
            print(f"✅ Successfully loaded {len(self.db_listings)} listings from database")
            print(f"📊 Database Statistics:")
            print(f"   Listings with descriptions: {valid_descriptions}")
            print(f"   Listings with empty descriptions: {empty_descriptions}")
            if len(self.db_listings) > 0:
                print(f"   Latest listing created: {self.db_listings[0]['created_date']}")
                print(f"   Oldest listing created: {self.db_listings[-1]['created_date']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error loading DB listings: {e}")
            print(f"   Error type: {type(e).__name__}")
            if connection:
                connection.close()
            return False

    def load_json_listings(self):
        """Load listings from JSON file"""
        print("📥 Loading listings from JSON file...")
        if not os.path.exists(self.json_file_path):
            print(f"⚠️ JSON file {self.json_file_path} not found")
            self.json_listings = []
            return True
        
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                self.json_listings = json.load(file)
            print(f"✅ Loaded {len(self.json_listings)} listings from JSON file")
            return True
        except Exception as e:
            print(f"❌ Error loading JSON listings: {e}")
            self.json_listings = []
            return False

    def load_csv_urls(self):
        """Load URLs from CSV file"""
        print("📥 Loading URLs from CSV file...")
        if not os.path.exists(self.csv_file_path):
            print(f"❌ CSV file {self.csv_file_path} not found")
            return False
        
        try:
            self.csv_urls = []
            with open(self.csv_file_path, 'r', encoding='utf-8') as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    if 'URL' in row and row['URL']:
                        self.csv_urls.append(row['URL'])
            
            print(f"✅ Loaded {len(self.csv_urls)} URLs from CSV file")
            return True
            
        except Exception as e:
            print(f"❌ Error loading CSV URLs: {e}")
            return False

    def find_listing_by_description(self, description):
        """Find DB listing by matching description using EXACT FULL matching only"""
        if not description or not description.strip():
            print(f"   ⚠️ Cannot search: Description is empty or None")
            return None
        
        description_clean = description.strip().lower()
        description_length = len(description_clean)
        
        print(f"   🔍 Searching for EXACT FULL description match...")
        print(f"   📝 Target description (first 100 chars): {description_clean[:100]}{'...' if len(description_clean) > 100 else ''}")
        print(f"   📏 Target description length: {description_length} characters")
        print(f"   📊 Searching through {len(self.db_listings)} database listings...")
        print(f"   🛡️ SAFETY: Using EXACT matching only - no partial matches accepted")
        
        exact_matches_found = 0
        partial_matches_found = 0
        
        # EXACT MATCH ONLY - Both descriptions must be 100% identical
        for i, db_listing in enumerate(self.db_listings):
            db_desc_clean = db_listing['description'].strip().lower()
            db_desc_length = len(db_desc_clean)
            
            # EXACT FULL MATCH - Both descriptions must be completely identical
            if db_desc_clean == description_clean:
                exact_matches_found += 1
                
                print(f"   ✅ EXACT FULL MATCH FOUND!")
                print(f"   🛡️ SAFETY VALIDATION:")
                print(f"     ✓ Length match: JSON={description_length} chars, DB={db_desc_length} chars")
                print(f"     ✓ Content match: 100% identical after normalization")
                print(f"     ✓ Match type: EXACT (not partial)")
                print(f"   📍 Match Details:")
                print(f"     Listing ID: {db_listing['listing_id']}")
                print(f"     Address: {db_listing['address'][:100]}{'...' if len(db_listing['address']) > 100 else ''}")
                print(f"     Created: {db_listing['created_date']}")
                print(f"     Position in DB: {i+1}/{len(self.db_listings)}")
                
                # Additional safety check - verify lengths match
                if description_length == db_desc_length:
                    print(f"   ✅ SAFETY CHECK PASSED: Exact length and content match")
                    
                    # Log the exact matches for transparency
                    print(f"   📋 Match Verification:")
                    print(f"     JSON desc: '{description_clean[:50]}{'...' if len(description_clean) > 50 else ''}'")
                    print(f"     DB desc:   '{db_desc_clean[:50]}{'...' if len(db_desc_clean) > 50 else ''}'")
                    
                    return db_listing
                else:
                    print(f"   ⚠️ SAFETY WARNING: Length mismatch despite string equality - skipping for safety")
                    continue
                    
            elif description_clean in db_desc_clean or db_desc_clean in description_clean:
                partial_matches_found += 1
        
        print(f"   ❌ No exact match found")
        print(f"   📊 Search Results:")
        print(f"     Exact matches: {exact_matches_found}")
        print(f"     Partial matches: {partial_matches_found} (IGNORED for safety)")
        print(f"   🛡️ SAFETY: Only exact matches are used - no risk of wrong property updates")
        return None

    def find_json_listing_by_url(self, url):
        """Find JSON listing by URL"""
        for json_listing in self.json_listings:
            if json_listing.get('url') == url:
                return json_listing
        return None

    def safe_find_element(self, xpath):
        """Safely find an element by xpath"""
        try:
            return self.driver.find_element(By.XPATH, xpath)
        except NoSuchElementException:
            return None

    def extract_text_safe(self, element):
        """Safely extract text from element"""
        if element:
            return element.text.strip()
        return ""

    def parse_price(self, price_str):
        """Extract numeric price from price string for database storage"""
        if not price_str:
            return None
        
        # Remove currency symbols, commas, spaces, and extract numbers
        price_cleaned = re.sub(r'[£$€,\s]', '', str(price_str))
        numbers = re.findall(r'\d+', price_cleaned)
        if numbers:
            try:
                # Return as integer for database bigint field
                return int(numbers[0])
            except ValueError:
                print(f"   ⚠️ Could not convert price '{price_str}' to integer")
                return None
        return None

    def parse_price_for_display(self, price_str):
        """Extract price string for display purposes"""
        if not price_str:
            return ""
        
        # Remove excess whitespace but keep currency symbols for display
        return str(price_str).strip()

    def scrape_current_price_and_description(self, url, max_retries=3):
        """Scrape current price and description from property page with retry logic"""
        print(f"   🌐 Attempting to scrape current data from website...")
        print(f"   🔗 Target URL: {url}")
        
        for attempt in range(max_retries):
            try:
                print(f"   📡 Attempt {attempt + 1}/{max_retries}: Loading page...")
                
                # Check if driver is still responsive
                if not self.driver:
                    print(f"   ⚠️ Driver not initialized, reinitializing...")
                    self.initialize_driver()
                
                # Load the page
                self.driver.get(url)
                time.sleep(3)
                print(f"   ✅ Page loaded successfully")

                                
                # Handle cookies popup if this is the first page load after browser restart
                self.handle_cookies_popup()
                
                # Extract description
                print(f"   🔍 Looking for description element...")
                description_element = self.safe_find_element('//p[@class="MuiTypography-root MuiTypography-body1 detailsText fxt-xypftu"]')
                current_description = self.extract_text_safe(description_element)
                
                if description_element:
                    print(f"   ✅ Description element found")
                    print(f"   📝 Description preview: {current_description[:100]}{'...' if len(current_description) > 100 else ''}")
                    print(f"   📏 Description length: {len(current_description)} characters")
                else:
                    print(f"   ⚠️ Description element not found on page")
                
                # Extract price
                print(f"   🔍 Looking for price element...")
                price_element = self.safe_find_element('//h3[@class="MuiTypography-root MuiTypography-h3 weeklyRent fxt-ghi95u"]')
                current_price = self.extract_text_safe(price_element)
                
                if price_element:
                    print(f"   ✅ Price element found")
                    print(f"   💰 Price found: '{current_price}'")
                else:
                    print(f"   ⚠️ Price element not found on page")
                
                scrape_time = datetime.now().isoformat()
                print(f"   ⏰ Scraping completed at: {scrape_time}")
                
                result = {
                    'description': current_description,
                    'price': current_price,
                    'scraped_at': scrape_time
                }
                
                print(f"   ✅ Successfully scraped data from website")
                return result
                
            except Exception as e:
                error_msg = str(e)
                print(f"   ❌ Attempt {attempt + 1}/{max_retries} failed: {error_msg}")
                
                # Check for specific timeout errors that require browser restart
                if ("HTTPConnectionPool" in error_msg and "Read timed out" in error_msg) or \
                   ("WebDriverException" in error_msg) or \
                   ("InvalidSessionIdException" in error_msg) or \
                   ("SessionNotCreatedException" in error_msg):
                    
                    print(f"   🔄 Browser timeout/error detected, restarting browser...")
                    self.close_driver()
                    time.sleep(2)  # Wait before reinitializing
                    
                    if attempt < max_retries - 1:  # Don't reinitialize on last attempt
                        try:
                            self.initialize_driver()
                            print(f"   ✅ Browser restarted successfully")
                        except Exception as init_error:
                            print(f"   ❌ Failed to reinitialize browser: {init_error}")
                            continue
                else:
                    # For other errors, just wait and retry
                    if attempt < max_retries - 1:
                        print(f"   ⏳ Waiting 2 seconds before retry...")
                        time.sleep(2)
        
        print(f"   ❌ Failed to scrape data after {max_retries} attempts")
        return None

    def validate_update_safety(self, listing_id, original_description, new_price, new_description):
        """Additional safety validation before database update"""
        print(f"   🛡️ FINAL SAFETY VALIDATION before database update...")
        print(f"   📋 Update Details:")
        print(f"     Listing ID: {listing_id}")
        print(f"     Original Description: {original_description[:100]}{'...' if len(original_description) > 100 else ''}")
        print(f"     New Price: {new_price}")
        print(f"     New Description: {new_description[:100]}{'...' if len(new_description) > 100 else ''}")
        
        # Safety checks
        safety_checks = []
        
        # Check 1: Listing ID is valid
        if listing_id and str(listing_id).isdigit():
            safety_checks.append("✓ Valid Listing ID")
        else:
            safety_checks.append("✗ Invalid Listing ID")
            
        # Check 2: New price is valid (integer or non-empty string)
        if new_price is not None and (isinstance(new_price, int) or str(new_price).strip()):
            safety_checks.append("✓ New price provided")
        else:
            safety_checks.append("✗ New price is empty or invalid")
            
        # Check 3: New description is not empty
        if new_description and str(new_description).strip():
            safety_checks.append("✓ New description provided")
        else:
            safety_checks.append("✗ New description is empty")
            
        # Check 4: Descriptions are similar length (safety check)
        if original_description and new_description:
            orig_len = len(original_description)
            new_len = len(new_description)
            length_diff = abs(orig_len - new_len)
            length_diff_percent = (length_diff / max(orig_len, new_len)) * 100 if max(orig_len, new_len) > 0 else 0
            
            if length_diff_percent < 50:  # Less than 50% difference
                safety_checks.append(f"✓ Description length similar ({orig_len} vs {new_len} chars)")
            else:
                safety_checks.append(f"⚠️ Large description length difference ({orig_len} vs {new_len} chars)")
        
        print(f"   🛡️ Safety Checks:")
        for check in safety_checks:
            print(f"     {check}")
        
        # Only proceed if basic safety checks pass
        failed_checks = [check for check in safety_checks if check.startswith("✗")]
        if failed_checks:
            print(f"   ❌ SAFETY VALIDATION FAILED - Update aborted")
            return False
        else:
            print(f"   ✅ SAFETY VALIDATION PASSED - Proceeding with update")
            return True

    def update_listing_in_db(self, listing_id, new_price, new_description, original_description=""):
        """Update listing in database via direct connection with safety validation"""
        print(f"💾 Preparing to update listing {listing_id} in database...")
        
        # Perform safety validation first
        if not self.validate_update_safety(listing_id, original_description, new_price, new_description):
            print(f"❌ Update aborted due to safety validation failure")
            return False
        
        connection = self.connect_to_database()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Update price and description
            query = """
            UPDATE [dbo].[Listings] 
            SET Price = %s, Description = %s, UpdatedDate = %s 
            WHERE ListingId = %s
            """
            
            current_time = datetime.now()
            print(f"   📝 Executing database update...")
            print(f"   📋 SQL Query: UPDATE Listings SET Price, Description, UpdatedDate WHERE ListingId = {listing_id}")
            
            cursor.execute(query, (new_price, new_description, current_time, listing_id))
            rows_affected = cursor.rowcount
            connection.commit()
            
            cursor.close()
            connection.close()
            
            print(f"   📊 Database Update Results:")
            print(f"     Rows affected: {rows_affected}")
            if rows_affected == 1:
                print(f"   ✅ Successfully updated listing {listing_id}")
                return True
            else:
                print(f"   ⚠️ Warning: Expected 1 row affected, got {rows_affected}")
                return False
            
        except Exception as e:
            print(f"❌ Error updating listing {listing_id}: {e}")
            print(f"   Error type: {type(e).__name__}")
            if connection:
                connection.close()
            return False

    def has_significant_change(self, old_price, new_price, old_description, new_description):
        """Check if there are significant changes between old and new data"""
        # Parse prices for comparison (returns integers or None)
        old_price_parsed = self.parse_price(old_price)
        new_price_parsed = self.parse_price(new_price)
        
        # Check price change - only if both prices were successfully parsed
        price_changed = False
        if old_price_parsed is not None and new_price_parsed is not None:
            price_changed = old_price_parsed != new_price_parsed
        elif old_price_parsed != new_price_parsed:  # One is None, other isn't
            price_changed = True
        
        # Check description change (normalize whitespace and case)
        old_desc_clean = re.sub(r'\s+', ' ', str(old_description or '').strip().lower())
        new_desc_clean = re.sub(r'\s+', ' ', str(new_description or '').strip().lower())
        description_changed = old_desc_clean != new_desc_clean
        
        return price_changed or description_changed

    def process_url(self, url, index, total):
        """Process a single URL to check for updates"""
        print(f"\n{'='*80}")
        print(f"📍 Processing URL {index}/{total}")
        print(f"🔗 URL: {url}")
        print(f"{'='*80}")
        
        try:
            # Find corresponding JSON listing
            print(f"🔍 Step 1: Looking for JSON listing...")
            json_listing = self.find_json_listing_by_url(url)
            if not json_listing:
                print(f"❌ No JSON listing found for URL: {url}")
                print(f"   This URL was not previously scraped or is missing from JSON file")
                self.skipped_count += 1
                return
            
            print(f"✅ Found JSON listing")
            
            # Get description from JSON listing
            json_description = json_listing.get('description', '')
            json_price = json_listing.get('price', '')
            json_address = json_listing.get('address', '')
            
            print(f"\n📄 JSON Listing Data:")
            print(f"   Address: {json_address[:100]}{'...' if len(json_address) > 100 else ''}")
            print(f"   Price: {json_price}")
            print(f"   Description: {json_description[:150]}{'...' if len(json_description) > 150 else ''}")
            print(f"   Description Length: {len(json_description)} characters")
            
            if not json_description:
                print(f"❌ No description in JSON listing - cannot match to DB")
                self.skipped_count += 1
                return
            
            # Find corresponding DB listing by description
            print(f"\n🔍 Step 2: Looking for matching DB listing by description...")
            db_listing = self.find_listing_by_description(json_description)
            if not db_listing:
                print(f"❌ No DB listing found with matching description")
                print(f"   Searched {len(self.db_listings)} DB listings")
                print(f"   This property may not have been successfully added to database")
                self.skipped_count += 1
                return
            
            print(f"✅ Found matching DB listing!")
            print(f"\n💾 Database Listing Data:")
            print(f"   Listing ID: {db_listing['listing_id']}")
            print(f"   Address: {db_listing['address'][:100]}{'...' if len(db_listing['address']) > 100 else ''}")
            print(f"   Price: {db_listing['price']}")
            print(f"   Description: {db_listing['description'][:150]}{'...' if len(db_listing['description']) > 150 else ''}")
            print(f"   Description Length: {len(db_listing['description'])} characters")
            print(f"   Created Date: {db_listing['created_date']}")
            
            # Scrape current data from website
            print(f"\n🔍 Step 3: Scraping current data from website...")
            current_data = self.scrape_current_price_and_description(url)
            if not current_data:
                print(f"❌ Failed to scrape current data from website")
                self.error_count += 1
                return
            
            print(f"✅ Successfully scraped current data")
            print(f"\n🌐 Current Website Data:")
            print(f"   Price: {current_data['price']}")
            print(f"   Description: {current_data['description'][:150]}{'...' if len(current_data['description']) > 150 else ''}")
            print(f"   Description Length: {len(current_data['description'])} characters")
            print(f"   Scraped At: {current_data['scraped_at']}")
            
            # Compare data
            print(f"\n🔍 Step 4: Comparing data for changes...")
            has_changes = self.has_significant_change(
                db_listing['price'],
                current_data['price'],
                db_listing['description'],
                current_data['description']
            )
            
            # Detailed comparison logging - compare parsed integer values
            old_price_parsed = self.parse_price(db_listing['price'])
            new_price_parsed = self.parse_price(current_data['price'])
            price_changed = old_price_parsed != new_price_parsed
            
            # Also get display versions for logging
            old_price_display = self.parse_price_for_display(db_listing['price'])
            new_price_display = self.parse_price_for_display(current_data['price'])
            
            old_desc_clean = re.sub(r'\s+', ' ', str(db_listing['description'] or '').strip().lower())
            new_desc_clean = re.sub(r'\s+', ' ', str(current_data['description'] or '').strip().lower())
            description_changed = old_desc_clean != new_desc_clean
            
            print(f"📊 Comparison Results:")
            print(f"   Price Comparison:")
            print(f"     DB Price: '{old_price_display}' → Parsed: {old_price_parsed}")
            print(f"     Website Price: '{new_price_display}' → Parsed: {new_price_parsed}")
            print(f"     Price Changed: {'YES' if price_changed else 'NO'}")
            print(f"   Description Comparison:")
            print(f"     DB Description Length: {len(old_desc_clean)} chars (normalized)")
            print(f"     Website Description Length: {len(new_desc_clean)} chars (normalized)")
            print(f"     Description Changed: {'YES' if description_changed else 'NO'}")
            print(f"   Overall Changes Detected: {'YES' if has_changes else 'NO'}")
            
            if has_changes:
                print(f"\n🔄 CHANGES DETECTED - Updating listing...")
                print(f"   Listing ID: {db_listing['listing_id']}")
                if price_changed:
                    print(f"   💰 Price Update: '{old_price_display}' → '{new_price_display}' (DB values: {old_price_parsed} → {new_price_parsed})")
                if description_changed:
                    print(f"   📝 Description Update: {len(old_desc_clean)} → {len(new_desc_clean)} chars")
                
                # Parse price to integer for database storage
                parsed_price = self.parse_price(current_data['price'])
                display_price = self.parse_price_for_display(current_data['price'])
                
                print(f"   🔢 Price Conversion:")
                print(f"     Raw price: '{current_data['price']}'")
                print(f"     Parsed for DB: {parsed_price}")
                print(f"     Display format: '{display_price}'")
                
                if parsed_price is None:
                    print(f"   ❌ Invalid price format - skipping update")
                    self.error_count += 1
                else:
                    # Update in database with safety validation
                    if self.update_listing_in_db(
                        db_listing['listing_id'],
                        parsed_price,  # Use parsed integer price
                        current_data['description'],
                        db_listing['description']  # Pass original description for safety validation
                    ):
                        self.updated_count += 1
                        print(f"✅ Successfully updated listing {db_listing['listing_id']} in database")
                    else:
                        print(f"❌ Failed to update listing {db_listing['listing_id']} in database")
                        self.error_count += 1
            else:
                print(f"\n✅ NO CHANGES DETECTED - Skipping update")
                print(f"   Listing ID {db_listing['listing_id']} is already up-to-date")
                self.skipped_count += 1
                
        except Exception as e:
            print(f"\n❌ ERROR processing URL {url}: {str(e)}")
            print(f"   Error Type: {type(e).__name__}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            self.error_count += 1

    def run_check(self, limit=None):
        """Main method to run the existing listings check"""
        print("🚀 Starting existing listings check...")
        print("=" * 60)
        
        # Load data from all sources
        if not self.load_db_listings():
            print("❌ Failed to load DB listings")
            return False
        
        if not self.load_json_listings():
            print("❌ Failed to load JSON listings")
            return False
        
        if not self.load_csv_urls():
            print("❌ Failed to load CSV URLs")
            return False
        
        print(f"\n📊 Data Summary:")
        print(f"   DB Listings: {len(self.db_listings)}")
        print(f"   JSON Listings: {len(self.json_listings)}")
        print(f"   CSV URLs: {len(self.csv_urls)}")
        
        # Process URLs
        urls_to_process = self.csv_urls
        if limit:
            urls_to_process = urls_to_process[:limit]
            print(f"   Limited to: {len(urls_to_process)} URLs")
        
        print(f"\n🔄 Processing {len(urls_to_process)} URLs...")
        print("=" * 60)
        
        start_time = time.time()
        
        for i, url in enumerate(urls_to_process, 1):
            self.process_url(url, i, len(urls_to_process))
            
            # Be respectful with requests
            time.sleep(2)
        
        end_time = time.time()
        
        # Print detailed summary
        print("\n" + "=" * 80)
        print("📈 FINAL DETAILED SUMMARY")
        print("=" * 80)
        
        total_processed = self.updated_count + self.skipped_count + self.error_count
        
        print(f"📊 Processing Results:")
        print(f"   🔄 Updated listings: {self.updated_count}")
        print(f"   ⏭️ Skipped listings (no changes): {self.skipped_count}")
        print(f"   ❌ Error listings: {self.error_count}")
        print(f"   📋 Total processed: {total_processed}")
        print(f"   📁 Total URLs in CSV: {len(urls_to_process)}")
        
        print(f"\n⏱️ Performance Metrics:")
        print(f"   Total time: {end_time - start_time:.2f} seconds")
        print(f"   Average per URL: {(end_time - start_time) / len(urls_to_process):.1f} seconds")
        if self.updated_count > 0:
            print(f"   Time per update: {(end_time - start_time) / self.updated_count:.1f} seconds")
        
        print(f"\n📈 Success Rates:")
        if len(urls_to_process) > 0:
            print(f"   Processing success: {((self.updated_count + self.skipped_count) / len(urls_to_process) * 100):.1f}%")
            print(f"   Update rate: {(self.updated_count / len(urls_to_process) * 100):.1f}%")
            print(f"   Error rate: {(self.error_count / len(urls_to_process) * 100):.1f}%")
        
        print(f"\n💾 Database Information:")
        print(f"   DB listings loaded: {len(self.db_listings)}")
        print(f"   JSON listings loaded: {len(self.json_listings)}")
        
        if self.updated_count > 0:
            print(f"\n🎉 Successfully updated {self.updated_count} listing(s) in database!")
        else:
            print(f"\n✅ All listings are up-to-date - no updates needed!")
        
        print("=" * 80)
        
        return True


def main():
    """Main function to run the existing listings checker"""
    # Configuration
    CSV_FILE = "foxtons_secondary_urls_collection.csv"
    JSON_FILE = "property_details.json"
    
    # Ensure we're in the right directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Check if required files exist
    if not os.path.exists(CSV_FILE):
        print(f"❌ CSV file '{CSV_FILE}' not found")
        return
    
    print(f"📋 Using CSV file: {CSV_FILE}")
    print(f"📄 Using JSON file: {JSON_FILE}")
    
    # Initialize checker
    checker = ExistingListingsChecker(
        csv_file_path=CSV_FILE,
        json_file_path=JSON_FILE
    )
    
    try:
        # Run the check (you can add limit=10 for testing)
        checker.run_check()
        
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        
    finally:
        # Cleanup
        if hasattr(checker, 'driver'):
            checker.driver.quit()


if __name__ == "__main__":
    main()