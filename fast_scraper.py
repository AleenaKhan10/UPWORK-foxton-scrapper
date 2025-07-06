import requests
from bs4 import BeautifulSoup
import csv
import logging
import time
from urllib.parse import urljoin
import random
import os
from datetime import datetime
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }

def get_csv_filename():
    data_dir = 'scraped_data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(data_dir, f'property_listings_{timestamp}.csv')

def save_urls_to_csv(urls, filename, mode='a'):
    try:
        if mode == 'a' and os.path.exists(filename):
            backup_filename = f"{filename}.backup"
            os.replace(filename, backup_filename)
        
        with open(filename, mode, newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if mode == 'w':
                writer.writerow(['URL', 'Source Page', 'Timestamp', 'Page Number'])
            for url in sorted(urls):
                writer.writerow([
                    url, 
                    urls[url]['source'], 
                    urls[url]['timestamp'],
                    urls[url]['page_number']
                ])
        
        if mode == 'a' and os.path.exists(f"{filename}.backup"):
            os.remove(f"{filename}.backup")
            
        logger.info(f"Successfully saved {len(urls)} URLs to {filename}")
    except Exception as e:
        logger.error(f"Error saving URLs to CSV: {e}")
        if os.path.exists(f"{filename}.backup"):
            os.replace(f"{filename}.backup", filename)
            logger.info("Restored from backup file")

def is_next_page_available(soup):
    try:
        # Check for next button
        next_button = soup.select_one('button[aria-label="Go to next page"]')
        if not next_button:
            return False
            
        # Check if button is disabled
        if 'disabled' in next_button.get('class', []):
            return False
            
        # Additional check for pagination numbers
        pagination = soup.select('ul.pagination li a')
        if not pagination:
            return False
            
        # Get all page numbers
        page_numbers = []
        for page in pagination:
            try:
                num = int(page.text.strip())
                page_numbers.append(num)
            except ValueError:
                continue
                
        if not page_numbers:
            return False
            
        # Check if current page is the last one
        current_page = None
        for page in pagination:
            if 'active' in page.get('class', []):
                try:
                    current_page = int(page.text.strip())
                    break
                except ValueError:
                    continue
                    
        if current_page is None:
            return False
            
        # If current page is less than max page, there are more pages
        return current_page < max(page_numbers)
        
    except Exception as e:
        logger.error(f"Error checking next page availability: {e}")
        return False

def extract_listing_urls(url, csv_filename):
    listing_urls = {}
    page = 1
    total_listings = 0
    consecutive_empty_pages = 0
    max_empty_pages = 3
    last_save_count = 0
    save_interval = 10
    session = requests.Session()
    
    try:
        logger.info(f"Processing URL: {url}")
        
        while True:
            try:
                # Construct page URL
                page_url = f"{url}?page={page}" if page > 1 else url
                logger.info(f"Fetching page {page}: {page_url}")
                
                # Make request
                response = session.get(page_url, headers=get_headers(), timeout=30)
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all listing links
                listing_elements = soup.select('section a')
                
                if not listing_elements:
                    consecutive_empty_pages += 1
                    logger.warning(f"No listings found on page {page} (consecutive empty pages: {consecutive_empty_pages})")
                    if consecutive_empty_pages >= max_empty_pages:
                        logger.info("Too many consecutive empty pages, stopping")
                        break
                    continue
                
                consecutive_empty_pages = 0
                
                # Process new URLs
                page_urls = {}
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for element in listing_elements:
                    href = element.get('href')
                    if href and 'foxtons.co.uk' in href:
                        full_url = urljoin('https://www.foxtons.co.uk', href)
                        page_urls[full_url] = {
                            'source': page_url,
                            'timestamp': current_time,
                            'page_number': page
                        }
                
                # Add new URLs to our set
                new_urls = {k: v for k, v in page_urls.items() if k not in listing_urls}
                listing_urls.update(new_urls)
                total_listings += len(new_urls)
                
                logger.info(f"Found {len(new_urls)} new listings on page {page}")
                
                # Save new URLs to CSV if we've found enough new ones
                if len(listing_urls) - last_save_count >= save_interval:
                    save_urls_to_csv(listing_urls, csv_filename, 'w' if page == 1 else 'a')
                    last_save_count = len(listing_urls)
                    logger.info(f"Progress saved: {len(listing_urls)} total URLs")
                
                # Check if next page exists
                if not is_next_page_available(soup):
                    logger.info("No more pages available - reached last page")
                    break
                
                # Move to next page
                page += 1
                
                # Random wait between pages (increased wait time)
                wait_time = random.uniform(3, 5)
                logger.info(f"Waiting {wait_time:.1f} seconds before next page...")
                time.sleep(wait_time)
                
            except requests.RequestException as e:
                logger.error(f"Request error on page {page}: {e}")
                # Wait longer on error
                time.sleep(random.uniform(5, 8))
                continue
            except Exception as e:
                logger.error(f"Error processing page {page}: {e}")
                break
        
        # Save any remaining URLs
        if len(listing_urls) > last_save_count:
            save_urls_to_csv(listing_urls, csv_filename, 'w' if page == 1 else 'a')
                
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
    
    logger.info(f"Total new listings found for {url}: {total_listings}")
    return listing_urls

def process_location_urls():
    all_listing_urls = {}
    csv_filename = get_csv_filename()
    
    try:
        with open('foxtons_urls.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            urls = [row['URL'] for row in reader]
        
        logger.info(f"Processing {len(urls)} location URLs")
        logger.info(f"Results will be saved to: {csv_filename}")
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing location {i}/{len(urls)}: {url}")
            listing_urls = extract_listing_urls(url, csv_filename)
            all_listing_urls.update(listing_urls)
            logger.info(f"Found {len(listing_urls)} total listings for {url}")
            
            if i < len(urls):
                wait_time = random.uniform(4, 6)
                logger.info(f"Waiting {wait_time:.1f} seconds before next location...")
                time.sleep(wait_time)
        
        logger.info(f"Successfully processed all locations. Total unique listings: {len(all_listing_urls)}")
        
    except Exception as e:
        logger.error(f"Error processing location URLs: {e}")

if __name__ == "__main__":
    process_location_urls() 