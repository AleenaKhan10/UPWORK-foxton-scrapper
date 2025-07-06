from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
import csv
import logging
import time
from urllib.parse import urljoin
import random
import os
from datetime import datetime

# Set up logging with more detailed format
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

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--start-maximized')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
    
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
    })
    return driver

def get_csv_filename():
    data_dir = 'scraped_data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return os.path.join(data_dir, 'property_listings.csv')

def load_existing_urls(filename):
    existing_urls = {}
    if os.path.exists(filename):
        try:
            with open(filename, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_urls[row['URL']] = {
                        'source': row['Source Page'],
                        'timestamp': row['Timestamp'],
                        'page_number': int(row['Page Number'])
                    }
            logger.info(f"Loaded {len(existing_urls)} existing URLs from {filename}")
        except Exception as e:
            logger.error(f"Error loading existing URLs: {e}")
    return existing_urls

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

def is_next_page_available(driver):
    try:
        # First check for "No result found" message
        try:
            no_results = driver.find_element(By.XPATH, '//h2[text()="No result found"]')
            if no_results:
                logger.info("Found 'No result found' message - no more results available")
                return False
        except NoSuchElementException:
            pass  # No "No result found" message, continue with normal checks
            
        # Check for next button
        next_button = driver.find_element(By.XPATH, '//button[@aria-label="Go to next page"]')
        if not next_button:
            return False
            
        # Check if button is disabled
        if 'disabled' in next_button.get_attribute('class'):
            return False
            
        # Check for listings
        listings = driver.find_elements(By.XPATH, "//section/a")
        if not listings:
            return False
            
        return True
    except NoSuchElementException:
        return False
    except Exception as e:
        logger.error(f"Error checking next page availability: {e}")
        return False

def extract_listing_urls(driver, url, csv_filename, existing_urls):
    listing_urls = existing_urls.copy()
    page = 1
    total_listings = 0
    consecutive_empty_pages = 0
    max_empty_pages = 3
    last_save_count = len(listing_urls)
    save_interval = 10
    max_retries = 3
    
    try:
        logger.info(f"Processing URL: {url}")
        driver.get(url)
        time.sleep(random.uniform(2, 4))
        
        # Check for "No result found" on first page
        try:
            no_results = driver.find_element(By.XPATH, '//h2[text()="No result found"]')
            if no_results:
                logger.info(f"No results found for URL: {url} - skipping to next URL")
                return listing_urls
        except NoSuchElementException:
            pass  # No "No result found" message, continue with normal processing
        
        while True:
            try:
                # Wait for listings to be visible
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//section/a"))
                )
                
                # Extract listing URLs
                listing_elements = driver.find_elements(By.XPATH, "//section/a")
                
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
                    try:
                        href = element.get_attribute('href')
                        if href and 'foxtons.co.uk' in href:
                            page_urls[href] = {
                                'source': f"{url}?page={page}",
                                'timestamp': current_time,
                                'page_number': page
                            }
                    except StaleElementReferenceException:
                        continue
                
                # Add new URLs to our set
                new_urls = {k: v for k, v in page_urls.items() if k not in listing_urls}
                listing_urls.update(new_urls)
                total_listings += len(new_urls)
                
                logger.info(f"Found {len(new_urls)} new listings on page {page}")
                
                # Save new URLs to CSV if we've found enough new ones
                if len(listing_urls) - last_save_count >= save_interval:
                    # Save all URLs to maintain complete data
                    save_urls_to_csv(listing_urls, csv_filename, 'w')
                    last_save_count = len(listing_urls)
                    logger.info(f"Progress saved: {len(listing_urls)} total URLs")
                
                # Check if next page exists
                if not is_next_page_available(driver):
                    logger.info("No more pages available - reached last page")
                    break
                
                # Try to click next page button with retries
                retry_count = 0
                while retry_count < max_retries:
                    try:
                        next_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Go to next page"]'))
                        )
                        # Scroll to the button
                        driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                        time.sleep(1)
                        
                        # Try to click using JavaScript if regular click fails
                        try:
                            next_button.click()
                        except ElementClickInterceptedException:
                            driver.execute_script("arguments[0].click();", next_button)
                        
                        # Wait for page load
                        time.sleep(2)
                        page += 1
                        break
                    except Exception as e:
                        retry_count += 1
                        logger.warning(f"Failed to navigate to next page (attempt {retry_count}/{max_retries}): {e}")
                        if retry_count < max_retries:
                            time.sleep(random.uniform(2, 4))
                            continue
                        else:
                            logger.error(f"Failed to navigate to next page after {max_retries} attempts, skipping to next page")
                            # Try to force navigation to next page by URL
                            try:
                                next_page_url = f"{url}?page={page + 1}"
                                driver.get(next_page_url)
                                time.sleep(2)
                                page += 1
                            except Exception as nav_error:
                                logger.error(f"Failed to force navigation to next page: {nav_error}")
                                break
                
            except TimeoutException:
                logger.error(f"Timeout waiting for elements on page {page}")
                # Try to continue with next page
                try:
                    no_results = driver.find_element(By.XPATH, '//h2[text()="No result found"]')
                    if no_results:
                        logger.info("Found 'No result found' message - no more results available")
                        return False
                except NoSuchElementException:
                    pass  # No "No result found" message, continue with normal checks

                try:
                    next_page_url = f"{url}?page={page + 1}"
                    driver.get(next_page_url)
                    time.sleep(2)
                    page += 1
                except Exception as nav_error:
                    logger.error(f"Failed to navigate to next page after timeout: {nav_error}")
                    break
            except Exception as e:
                logger.error(f"Error processing page {page}: {e}")
                # Try to continue with next page
                try:
                    next_page_url = f"{url}?page={page + 1}"
                    driver.get(next_page_url)
                    time.sleep(2)
                    page += 1
                except Exception as nav_error:
                    logger.error(f"Failed to navigate to next page after error: {nav_error}")
                    break
        
        # Save any remaining URLs
        if len(listing_urls) > last_save_count:
            save_urls_to_csv(listing_urls, csv_filename, 'w')
                
    except Exception as e:
        logger.error(f"Error processing URL {url}: {e}")
    
    logger.info(f"Total new listings found for {url}: {total_listings}")
    return listing_urls

def process_location_urls():
    driver = setup_driver()
    csv_filename = get_csv_filename()
    
    try:
        # Load existing URLs
        all_listing_urls = load_existing_urls(csv_filename)
        logger.info(f"Loaded {len(all_listing_urls)} existing URLs")
        
        with open('foxtons_urls.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            urls = [row['URL'] for row in reader]
        
        logger.info(f"Processing {len(urls)} location URLs")
        logger.info(f"Results will be saved to: {csv_filename}")
        
        for i, url in enumerate(urls, 1):
            logger.info(f"Processing location {i}/{len(urls)}: {url}")
            new_urls = extract_listing_urls(driver, url, csv_filename, all_listing_urls)
            if new_urls:
                all_listing_urls.update(new_urls)
                # Save after each location is processed
                save_urls_to_csv(all_listing_urls, csv_filename, 'w')
                logger.info(f"Updated total listings: {len(all_listing_urls)}")
            
            if i < len(urls):
                wait_time = random.uniform(2, 4)
                logger.info(f"Waiting {wait_time:.1f} seconds before next location...")
                time.sleep(wait_time)
        
        logger.info(f"Successfully processed all locations. Total unique listings: {len(all_listing_urls)}")
        
    except Exception as e:
        logger.error(f"Error processing location URLs: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    process_location_urls() 